from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / "docs" / "anchor-review-small-16-32-64-128" / "data" / "review-data.json"
PHASE8_DIR = ROOT / "tmp" / "fasterrcnn_anchor_workflow" / "phase_08_human_review_ingestion"
OUT_DIR = PHASE8_DIR / "structured_review_results"


REQUIRED_FIELDS = {
    "cardId",
    "cardIndex",
    "page",
    "position",
    "sourceId",
    "predictionId",
    "score",
    "bboxX1",
    "bboxY1",
    "bboxX2",
    "bboxY2",
    "reviewerSelection",
    "reviewStatus",
    "finalClassification",
    "pageCompleted",
    "exportedAt",
}

VALID_SELECTIONS = {"", "F", "P", "U"}
VALID_CLASSIFICATIONS = {
    "HUMAN_ACCEPTED_TRUE_POSITIVE",
    "FALSE_POSITIVE_BY_EXPERT",
    "PAIRING_ERROR",
    "UNRESOLVED",
    "NOT_REVIEWED",
}


def read_review_data() -> dict[str, Any]:
    return json.loads(SITE_DATA.read_text(encoding="utf-8"))


def load_input(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload, list(payload.get("results", []))
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        first = rows[0] if rows else {}
        payload = {
            "reviewSchemaVersion": first.get("reviewSchemaVersion"),
            "packageId": first.get("packageId"),
            "modelProfile": first.get("modelProfile"),
            "checkpointSha256": first.get("checkpointSha256"),
            "threshold": first.get("threshold"),
            "manifestIdentifier": first.get("manifestIdentifier"),
            "results": rows,
        }
        return payload, rows
    raise ValueError("Input must be .json or .csv")


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def validate_identity(payload: dict[str, Any], review_data: dict[str, Any]) -> list[str]:
    expected = {
        "reviewSchemaVersion": review_data["reviewSchemaVersion"],
        "packageId": review_data["canonicalGalleryPackage"],
        "modelProfile": review_data["experiment"]["modelProfile"],
        "checkpointSha256": review_data["experiment"]["checkpointSha256"],
        "threshold": review_data["experiment"]["threshold"],
        "manifestIdentifier": review_data["manifestIdentifier"],
    }
    errors = []
    for field, expected_value in expected.items():
        if str(payload.get(field)) != str(expected_value):
            errors.append(f"{field} mismatch: expected {expected_value}, found {payload.get(field)}")
    return errors


def validate_rows(rows: list[dict[str, Any]], review_data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    errors = []
    expected_cards = {card["cardId"]: card for card in review_data["cards"]}
    normalized = []
    if len(rows) != len(expected_cards):
        errors.append(f"card count mismatch: expected {len(expected_cards)}, found {len(rows)}")
    seen = set()
    for row in rows:
        missing = sorted(REQUIRED_FIELDS - set(row))
        if missing:
            errors.append(f"{row.get('cardId', '<missing cardId>')} missing fields: {', '.join(missing)}")
            continue
        card_id = str(row["cardId"])
        card = expected_cards.get(card_id)
        if card is None:
            errors.append(f"{card_id} is not in canonical review manifest")
            continue
        if card_id in seen:
            errors.append(f"{card_id} appears more than once")
        seen.add(card_id)
        selection = str(row.get("reviewerSelection", ""))
        classification = str(row.get("finalClassification", ""))
        if selection not in VALID_SELECTIONS:
            errors.append(f"{card_id} has invalid reviewerSelection {selection}")
        if classification not in VALID_CLASSIFICATIONS:
            errors.append(f"{card_id} has invalid finalClassification {classification}")
        normalized.append(
            {
                "cardId": card_id,
                "cardIndex": int(row["cardIndex"]),
                "page": int(row["page"]),
                "position": int(row["position"]),
                "sourceId": str(row["sourceId"]),
                "predictionId": str(row["predictionId"]),
                "score": float(row["score"]),
                "bboxX1": float(row["bboxX1"]),
                "bboxY1": float(row["bboxY1"]),
                "bboxX2": float(row["bboxX2"]),
                "bboxY2": float(row["bboxY2"]),
                "reviewerSelection": selection,
                "reviewStatus": str(row["reviewStatus"]),
                "finalClassification": classification,
                "pageCompleted": normalize_bool(row["pageCompleted"]),
                "pageCompletedAt": str(row.get("pageCompletedAt", "")),
                "exportedAt": str(row["exportedAt"]),
            }
        )
    return normalized, errors


def write_outputs(rows: list[dict[str, Any]], payload: dict[str, Any], source: Path) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    imported_at = datetime.now(timezone.utc).isoformat()
    normalized_csv = OUT_DIR / "structured_expert_review_results_normalized.csv"
    normalized_json = OUT_DIR / "structured_expert_review_results_normalized.json"
    report_json = OUT_DIR / "structured_expert_review_import_report.json"
    fields = list(rows[0].keys()) if rows else []
    with normalized_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    normalized_json.write_text(json.dumps({"source": str(source), "importedAt": imported_at, "results": rows}, indent=2), encoding="utf-8")
    summary = {
        "status": "STRUCTURED_REVIEW_RESULTS_IMPORTED",
        "source": str(source),
        "importedAt": imported_at,
        "cardCount": len(rows),
        "packageId": payload.get("packageId"),
        "manifestIdentifier": payload.get("manifestIdentifier"),
        "normalizedCsv": str(normalized_csv),
        "normalizedJson": str(normalized_json),
    }
    report_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and normalize structured Pics-BirdNests expert review results.")
    parser.add_argument("input", type=Path, help="Exported small-anchor expert review .json or .csv")
    parser.add_argument("--validate-only", action="store_true", help="Validate without writing Phase 8 normalized outputs")
    args = parser.parse_args()

    review_data = read_review_data()
    payload, rows = load_input(args.input)
    errors = validate_identity(payload, review_data)
    normalized, row_errors = validate_rows(rows, review_data)
    errors.extend(row_errors)
    if errors:
        print(json.dumps({"status": "STRUCTURED_REVIEW_RESULTS_REJECTED", "errors": errors[:100]}, indent=2))
        return 2
    if args.validate_only:
        print(json.dumps({"status": "STRUCTURED_REVIEW_RESULTS_VALID", "cardCount": len(normalized)}, indent=2))
        return 0
    print(json.dumps(write_outputs(normalized, payload, args.input), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
