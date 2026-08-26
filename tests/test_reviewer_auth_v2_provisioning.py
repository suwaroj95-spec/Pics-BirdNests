from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from tools import generate_expert_review_v2_tokens as provision


ROOT = Path(__file__).resolve().parents[1]
TOKEN_A = "TOKEN_A_EXAMPLE_NOT_REAL"
TOKEN_B = "TOKEN_B_EXAMPLE_NOT_REAL"


class DeterministicTokens:
    def __init__(self, values: list[str]) -> None:
        self.values = values
        self.index = 0

    def __call__(self) -> str:
        value = self.values[self.index]
        self.index += 1
        return value


class ReviewerAuthV2ProvisioningTests(unittest.TestCase):
    def setUp(self) -> None:
        self._cleanup_dirs: list[Path] = []

    def tearDown(self) -> None:
        for path in reversed(self._cleanup_dirs):
            shutil.rmtree(path, ignore_errors=True)

    def external_dir(self) -> Path:
        path = external_temp_parent() / f"erv2_token_test_{uuid.uuid4().hex}"
        path.mkdir()
        self._cleanup_dirs.append(path)
        return path

    def generate_valid_bundle(self, target: Path) -> dict[str, object]:
        return provision.generate_bundle(
            target,
            token_factory=DeterministicTokens([TOKEN_A, TOKEN_B]),
            repo_root=ROOT,
        )

    def test_output_path_inside_repo_rejected(self) -> None:
        inside = ROOT / "tmp" / "token-output"
        with self.assertRaises(provision.ProvisioningError) as ctx:
            provision.resolve_output_dir(inside, ROOT)
        self.assertEqual("OUTPUT_DIRECTORY_INSIDE_REPOSITORY", ctx.exception.code)

    def test_repository_root_itself_rejected(self) -> None:
        with self.assertRaises(provision.ProvisioningError) as ctx:
            provision.resolve_output_dir(ROOT, ROOT)
        self.assertEqual("OUTPUT_DIRECTORY_INSIDE_REPOSITORY", ctx.exception.code)

    def test_child_of_repo_rejected(self) -> None:
        with self.assertRaises(provision.ProvisioningError) as ctx:
            provision.generate_bundle(
                ROOT / "docs" / "token-output",
                token_factory=DeterministicTokens([TOKEN_A, TOKEN_B]),
                repo_root=ROOT,
            )
        self.assertEqual("OUTPUT_DIRECTORY_INSIDE_REPOSITORY", ctx.exception.code)

    def test_external_temp_directory_accepted(self) -> None:
        target = self.external_dir() / "fresh"
        result = self.generate_valid_bundle(target)
        self.assertTrue(result["ok"])
        self.assertTrue((target / provision.PROPERTY_FILE).exists())

    def test_exactly_two_tokens_generated(self) -> None:
        bundle = provision.build_token_bundle(DeterministicTokens([TOKEN_A, TOKEN_B]))
        self.assertEqual({"REV_A", "REV_B"}, set(bundle["tokens"]))  # type: ignore[arg-type]

    def test_reviewer_tokens_differ(self) -> None:
        bundle = provision.build_token_bundle(DeterministicTokens([TOKEN_A, TOKEN_B]))
        tokens = bundle["tokens"]
        self.assertNotEqual(tokens["REV_A"], tokens["REV_B"])  # type: ignore[index]

    def test_default_generation_uses_256_bits_or_more(self) -> None:
        self.assertEqual("secrets.token_urlsafe", provision.TOKEN_ALGORITHM)
        self.assertGreaterEqual(provision.TOKEN_ENTROPY_BITS, 256)

    def test_hashes_are_sha256_lowercase_hex(self) -> None:
        digest = provision.sha256_token(TOKEN_A)
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual(digest, digest.lower())

    def test_property_json_contains_exactly_two_hash_keys(self) -> None:
        target = self.external_dir() / "fresh"
        self.generate_valid_bundle(target)
        data = json.loads((target / provision.PROPERTY_FILE).read_text(encoding="utf-8"))
        self.assertEqual(2, len(data))
        self.assertTrue(all(provision.is_lower_hex_sha256(key) for key in data))

    def test_mappings_resolve_to_rev_a_and_rev_b(self) -> None:
        target = self.external_dir() / "fresh"
        self.generate_valid_bundle(target)
        data = json.loads((target / provision.PROPERTY_FILE).read_text(encoding="utf-8"))
        self.assertEqual({"REV_A", "REV_B"}, {value["reviewer_id"] for value in data.values()})

    def test_raw_token_a_absent_from_property_json(self) -> None:
        target = self.external_dir() / "fresh"
        self.generate_valid_bundle(target)
        text = (target / provision.PROPERTY_FILE).read_text(encoding="utf-8")
        self.assertNotIn(TOKEN_A, text)

    def test_raw_token_b_absent_from_property_json(self) -> None:
        target = self.external_dir() / "fresh"
        self.generate_valid_bundle(target)
        text = (target / provision.PROPERTY_FILE).read_text(encoding="utf-8")
        self.assertNotIn(TOKEN_B, text)

    def test_raw_tokens_never_printed(self) -> None:
        target = self.external_dir() / "fresh"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = self.generate_valid_bundle(target)
            provision.print_result(result)
        printed = out.getvalue()
        self.assertNotIn(TOKEN_A, printed)
        self.assertNotIn(TOKEN_B, printed)

    def test_existing_non_empty_output_directory_rejected(self) -> None:
        target = self.external_dir()
        (target / "existing.txt").write_text("occupied", encoding="utf-8")
        with self.assertRaises(provision.ProvisioningError) as ctx:
            self.generate_valid_bundle(target)
        self.assertEqual("OUTPUT_DIRECTORY_NOT_EMPTY", ctx.exception.code)

    def test_validator_detects_changed_token(self) -> None:
        target = self.external_dir() / "fresh"
        self.generate_valid_bundle(target)
        (target / provision.TOKEN_FILES["REV_A"]).write_text("CHANGED_TOKEN_NOT_REAL\n", encoding="utf-8")
        with self.assertRaises(provision.ProvisioningError) as ctx:
            provision.validate_bundle(target, repo_root=ROOT)
        self.assertEqual("PROPERTY_HASH_MISMATCH", ctx.exception.code)

    def test_validator_detects_changed_hash(self) -> None:
        target = self.external_dir() / "fresh"
        self.generate_valid_bundle(target)
        data = json.loads((target / provision.PROPERTY_FILE).read_text(encoding="utf-8"))
        first = next(iter(data))
        data["0" * 64] = data.pop(first)
        (target / provision.PROPERTY_FILE).write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(provision.ProvisioningError) as ctx:
            provision.validate_bundle(target, repo_root=ROOT)
        self.assertEqual("PROPERTY_HASH_MISMATCH", ctx.exception.code)

    def test_validator_detects_missing_reviewer(self) -> None:
        target = self.external_dir() / "fresh"
        self.generate_valid_bundle(target)
        data = json.loads((target / provision.PROPERTY_FILE).read_text(encoding="utf-8"))
        first = next(iter(data))
        data[first]["reviewer_id"] = "REV_A"
        (target / provision.PROPERTY_FILE).write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(provision.ProvisioningError) as ctx:
            provision.validate_bundle(target, repo_root=ROOT)
        self.assertEqual("PROPERTY_REVIEWER_MISSING", ctx.exception.code)

    def test_validator_passes_valid_bundle(self) -> None:
        target = self.external_dir() / "fresh"
        self.generate_valid_bundle(target)
        result = provision.validate_bundle(target, repo_root=ROOT)
        self.assertTrue(result["ok"])
        self.assertEqual("ERV2_REVIEWER_TOKEN_MAP_JSON", result["script_property_name"])

    def test_no_external_dependency_added(self) -> None:
        source = (ROOT / "tools" / "generate_expert_review_v2_tokens.py").read_text(encoding="utf-8")
        self.assertNotIn("requests", source)
        self.assertNotIn("cryptography", source)
        self.assertNotIn("numpy", source)
        self.assertNotIn("pandas", source)
        self.assertNotRegex(source, re.compile(r"^\s*from\s+(requests|cryptography|numpy|pandas)\b", re.MULTILINE))

    def test_cli_does_not_expose_deterministic_token_option(self) -> None:
        help_text = io.StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(help_text):
            provision.parse_args(["--help"])
        self.assertNotIn("deterministic", help_text.getvalue().lower())
        self.assertNotIn("seed", help_text.getvalue().lower())


def external_temp_parent() -> Path:
    candidates: list[Path] = []
    configured = os.environ.get("ERV2_TEST_EXTERNAL_TMP")
    if configured:
        candidates.append(Path(configured))
    session_id = os.environ.get("CODEX_SESSION_ID")
    visual_root = Path.home() / ".codex" / "visualizations"
    if session_id and visual_root.exists():
        candidates.extend(visual_root.glob(f"*/*/*/{session_id}"))
    candidates.append(Path(tempfile.gettempdir()))

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            if resolved == ROOT or ROOT in resolved.parents:
                continue
            resolved.mkdir(parents=True, exist_ok=True)
            probe = resolved / ".erv2_write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return resolved
        except OSError:
            continue
    raise RuntimeError("No writable external temporary directory available for provisioning tests.")


if __name__ == "__main__":
    unittest.main()
