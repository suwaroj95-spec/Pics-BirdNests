from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEWER_IDS = ("REV_A", "REV_B")
SCRIPT_PROPERTY_NAME = "ERV2_REVIEWER_TOKEN_MAP_JSON"
TOKEN_ALGORITHM = "secrets.token_urlsafe"
TOKEN_ENTROPY_BYTES = 32
TOKEN_ENTROPY_BITS = TOKEN_ENTROPY_BYTES * 8
HASH_ALGORITHM = "SHA-256"

TOKEN_FILES = {
    "REV_A": "REV_A_ACCESS_TOKEN.txt",
    "REV_B": "REV_B_ACCESS_TOKEN.txt",
}
PROPERTY_FILE = "ERV2_REVIEWER_TOKEN_MAP_JSON.txt"
AUDIT_FILE = "token_provisioning_audit.json"


class ProvisioningError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def resolve_output_dir(output_dir: str | Path, repo_root: Path = REPO_ROOT) -> Path:
    raw = Path(output_dir)
    if not raw.is_absolute():
        raise ProvisioningError("OUTPUT_DIRECTORY_NOT_ABSOLUTE", "Output directory must be an absolute path.")
    resolved = raw.resolve()
    root = repo_root.resolve()
    if resolved == root or root in resolved.parents:
        raise ProvisioningError("OUTPUT_DIRECTORY_INSIDE_REPOSITORY", "Output directory must be outside the repository.")
    return resolved


def sha256_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_ENTROPY_BYTES)


def build_token_bundle(token_factory: Callable[[], str] = generate_token) -> dict[str, object]:
    tokens = {reviewer_id: token_factory() for reviewer_id in REVIEWER_IDS}
    if not all(tokens.values()) or tokens["REV_A"] == tokens["REV_B"]:
        raise ProvisioningError("TOKEN_GENERATION_FAILED", "Generated reviewer tokens must be non-empty and unique.")
    token_hashes = {reviewer_id: sha256_token(token) for reviewer_id, token in tokens.items()}
    property_map = {
        token_hashes[reviewer_id]: {"reviewer_id": reviewer_id}
        for reviewer_id in REVIEWER_IDS
    }
    return {
        "tokens": tokens,
        "token_hashes": token_hashes,
        "property_map": property_map,
    }


def ensure_fresh_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        if not output_dir.is_dir():
            raise ProvisioningError("OUTPUT_PATH_NOT_DIRECTORY", "Output path exists but is not a directory.")
        if any(output_dir.iterdir()):
            raise ProvisioningError("OUTPUT_DIRECTORY_NOT_EMPTY", "Output directory must be fresh and empty.")
    else:
        output_dir.mkdir(parents=True)
    restrict_permissions(output_dir, directory=True)


def restrict_permissions(path: Path, directory: bool = False) -> None:
    if os.name == "posix":
        path.chmod(stat.S_IRWXU if directory else stat.S_IRUSR | stat.S_IWUSR)
    else:
        if directory:
            return
        path.chmod(stat.S_IREAD | stat.S_IWRITE)


def write_private_file(path: Path, contents: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    with os.fdopen(os.open(path, flags, 0o600), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(contents)
    restrict_permissions(path)


def create_audit(token_hashes: dict[str, str]) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "token_algorithm": TOKEN_ALGORITHM,
        "token_entropy_bits": TOKEN_ENTROPY_BITS,
        "hash_algorithm": HASH_ALGORITHM,
        "reviewer_ids": list(REVIEWER_IDS),
        "token_hashes": token_hashes,
        "script_property_name": SCRIPT_PROPERTY_NAME,
        "file_permission_note": (
            "The tool attempts owner-only permissions where supported by the OS. "
            "On Windows, Python standard-library chmod cannot safely author full ACLs."
        ),
    }


def generate_bundle(
    output_dir: str | Path,
    token_factory: Callable[[], str] = generate_token,
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    target = resolve_output_dir(output_dir, repo_root)
    ensure_fresh_output_dir(target)
    bundle = build_token_bundle(token_factory)
    tokens = bundle["tokens"]
    token_hashes = bundle["token_hashes"]
    property_map = bundle["property_map"]

    assert isinstance(tokens, dict)
    assert isinstance(token_hashes, dict)
    assert isinstance(property_map, dict)

    for reviewer_id, filename in TOKEN_FILES.items():
        write_private_file(target / filename, str(tokens[reviewer_id]) + "\n")

    property_json = json.dumps(property_map, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    for token in tokens.values():
        if str(token) in property_json:
            raise ProvisioningError("RAW_TOKEN_IN_PROPERTY_JSON", "Raw token must not appear in Script Property JSON.")
    write_private_file(target / PROPERTY_FILE, property_json + "\n")

    audit = create_audit({reviewer_id: str(token_hashes[reviewer_id]) for reviewer_id in REVIEWER_IDS})
    write_private_file(target / AUDIT_FILE, json.dumps(audit, ensure_ascii=True, indent=2, sort_keys=True) + "\n")

    return {
        "ok": True,
        "output_dir": str(target),
        "reviewer_ids": list(REVIEWER_IDS),
        "token_hashes": {reviewer_id: str(token_hashes[reviewer_id]) for reviewer_id in REVIEWER_IDS},
        "files": [TOKEN_FILES["REV_A"], TOKEN_FILES["REV_B"], PROPERTY_FILE, AUDIT_FILE],
    }


def validate_bundle(output_dir: str | Path, repo_root: Path = REPO_ROOT) -> dict[str, object]:
    target = resolve_output_dir(output_dir, repo_root)
    tokens: dict[str, str] = {}
    for reviewer_id, filename in TOKEN_FILES.items():
        path = target / filename
        if not path.exists():
            raise ProvisioningError("TOKEN_FILE_MISSING", f"Missing token file for {reviewer_id}.")
        token = path.read_text(encoding="utf-8").strip()
        if not token:
            raise ProvisioningError("TOKEN_EMPTY", f"Token for {reviewer_id} is empty.")
        tokens[reviewer_id] = token
    if tokens["REV_A"] == tokens["REV_B"]:
        raise ProvisioningError("TOKENS_NOT_UNIQUE", "Reviewer tokens must differ.")

    property_path = target / PROPERTY_FILE
    audit_path = target / AUDIT_FILE
    if not property_path.exists():
        raise ProvisioningError("PROPERTY_JSON_MISSING", "Script Property JSON file is missing.")
    if not audit_path.exists():
        raise ProvisioningError("AUDIT_FILE_MISSING", "Audit file is missing.")

    property_json = property_path.read_text(encoding="utf-8")
    for token in tokens.values():
        if token in property_json:
            raise ProvisioningError("RAW_TOKEN_IN_PROPERTY_JSON", "Raw token found in Script Property JSON.")
    try:
        property_map = json.loads(property_json)
    except json.JSONDecodeError as error:
        raise ProvisioningError("PROPERTY_JSON_INVALID", "Script Property JSON is invalid.") from error

    expected_hashes = {reviewer_id: sha256_token(token) for reviewer_id, token in tokens.items()}
    if set(property_map.keys()) != set(expected_hashes.values()):
        raise ProvisioningError("PROPERTY_HASH_MISMATCH", "Script Property hash keys do not match token files.")
    for token_hash, value in property_map.items():
        if not is_lower_hex_sha256(token_hash):
            raise ProvisioningError("PROPERTY_HASH_INVALID", "Script Property hash key is not lowercase SHA-256 hex.")
        if not isinstance(value, dict) or value.get("reviewer_id") not in REVIEWER_IDS:
            raise ProvisioningError("PROPERTY_REVIEWER_INVALID", "Script Property reviewer mapping is invalid.")
    mapped_reviewers = {value["reviewer_id"] for value in property_map.values()}
    if mapped_reviewers != set(REVIEWER_IDS):
        raise ProvisioningError("PROPERTY_REVIEWER_MISSING", "Script Property must contain exactly REV_A and REV_B.")

    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ProvisioningError("AUDIT_JSON_INVALID", "Audit JSON is invalid.") from error
    if audit.get("token_algorithm") != TOKEN_ALGORITHM:
        raise ProvisioningError("AUDIT_TOKEN_ALGORITHM_INVALID", "Audit token algorithm metadata is invalid.")
    if audit.get("token_entropy_bits") != TOKEN_ENTROPY_BITS:
        raise ProvisioningError("AUDIT_TOKEN_ENTROPY_INVALID", "Audit token entropy metadata is invalid.")
    if audit.get("hash_algorithm") != HASH_ALGORITHM:
        raise ProvisioningError("AUDIT_HASH_ALGORITHM_INVALID", "Audit hash algorithm metadata is invalid.")
    if audit.get("script_property_name") != SCRIPT_PROPERTY_NAME:
        raise ProvisioningError("AUDIT_SCRIPT_PROPERTY_INVALID", "Audit Script Property metadata is invalid.")
    if set(audit.get("reviewer_ids", [])) != set(REVIEWER_IDS):
        raise ProvisioningError("AUDIT_REVIEWER_IDS_INVALID", "Audit reviewer_ids metadata is invalid.")

    return {
        "ok": True,
        "output_dir": str(target),
        "reviewer_ids": list(REVIEWER_IDS),
        "token_hashes": expected_hashes,
        "script_property_name": SCRIPT_PROPERTY_NAME,
    }


def is_lower_hex_sha256(value: str) -> bool:
    return len(value) == 64 and value == value.lower() and all(char in "0123456789abcdef" for char in value)


def print_result(result: dict[str, object]) -> None:
    print("status=PASS")
    print(f"output_dir={result['output_dir']}")
    print("reviewer_ids=" + ",".join(result["reviewer_ids"]))  # type: ignore[index]
    hashes = result["token_hashes"]  # type: ignore[assignment]
    assert isinstance(hashes, dict)
    for reviewer_id in REVIEWER_IDS:
        print(f"{reviewer_id}_sha256={hashes[reviewer_id]}")
    if "files" in result:
        print("files=" + ",".join(result["files"]))  # type: ignore[index]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate or validate Expert Review v2 reviewer token bundle.")
    parser.add_argument("--output-dir", required=True, help="Absolute private directory outside the repository.")
    parser.add_argument("--validate-bundle", action="store_true", help="Validate an existing private bundle without printing raw tokens.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = validate_bundle(args.output_dir) if args.validate_bundle else generate_bundle(args.output_dir)
    except ProvisioningError as error:
        print(f"status=FAIL code={error.code}", file=sys.stderr)
        return 1
    print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
