from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np


POSITIVE_CLASS = "dirty_positive"
NEGATIVE_CLASS = "clean_negative"
VALID_LABELS = {POSITIVE_CLASS, NEGATIVE_CLASS}
PRIMARY_CSV_OUTPUTS = [
    "source_error_profile.csv",
    "source_priority_ranking.csv",
    "error_atlas_manifest.csv",
    "error_group_statistics.csv",
    "selected_error_examples.csv",
]
STATS = [
    "grayscale_mean",
    "grayscale_std",
    "grayscale_p05",
    "grayscale_p95",
    "hsv_saturation_mean",
    "hsv_value_mean",
    "laplacian_variance",
    "edge_pixel_fraction",
]


class AtlasError(RuntimeError):
    pass


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_output_empty(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise AtlasError(f"Output directory already contains files: {output_dir}")


def numeric_sort(value: str) -> tuple[int, str]:
    return (int(value), value) if value.isdigit() else (10**9, value)


def error_type(true_label: str, prediction: str) -> str:
    if true_label == POSITIVE_CLASS and prediction == POSITIVE_CLASS:
        return "true_positive"
    if true_label == NEGATIVE_CLASS and prediction == NEGATIVE_CLASS:
        return "true_negative"
    if true_label == NEGATIVE_CLASS and prediction == POSITIVE_CLASS:
        return "false_positive"
    if true_label == POSITIVE_CLASS and prediction == NEGATIVE_CLASS:
        return "false_negative"
    raise AtlasError(f"Invalid true/prediction labels: {true_label}, {prediction}")


def threshold_margin(kind: str, probability: float, threshold: float) -> float:
    if kind == "false_positive":
        return probability - threshold
    if kind == "false_negative":
        return threshold - probability
    return abs(probability - threshold)


def descriptive_stats(image: np.ndarray) -> dict[str, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
    lap = cv2.Laplacian(gray, cv2.CV_32F)
    sobel_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(sobel_x, sobel_y)
    return {
        "grayscale_mean": float(gray.mean()),
        "grayscale_std": float(gray.std()),
        "grayscale_p05": float(np.percentile(gray, 5)),
        "grayscale_p95": float(np.percentile(gray, 95)),
        "hsv_saturation_mean": float((hsv[:, :, 1] / 255.0).mean()),
        "hsv_value_mean": float((hsv[:, :, 2] / 255.0).mean()),
        "laplacian_variance": float(lap.var()),
        "edge_pixel_fraction": float(np.mean(mag > 0.12)),
    }


def safe_crop_path(crops_dir: Path, crop_path_text: str) -> Path:
    root = crops_dir.resolve()
    path = (root / crop_path_text).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise AtlasError(f"Crop path is outside Crops directory: {crop_path_text}") from exc
    return path


def load_and_validate(crops_dir: Path, robustness_dir: Path, lineage_manifest: Path, marker_audit_dir: Path) -> dict[str, Any]:
    marker_summary_path = marker_audit_dir / "marker_leakage_summary.json"
    marker_summary = json.loads(marker_summary_path.read_text(encoding="utf-8"))
    if marker_summary.get("decision") != "SAFE_TO_TRAIN":
        raise AtlasError("Marker leakage decision is not SAFE_TO_TRAIN")
    if int(marker_summary.get("marker_like_count", -1)) != 0:
        raise AtlasError("marker_like_count is not zero")

    _, lineage_rows = read_csv(lineage_manifest)
    lineage_by_path: dict[str, dict[str, str]] = {}
    for row in lineage_rows:
        crop_path = row.get("output_file", "")
        if crop_path in lineage_by_path:
            raise AtlasError(f"Lineage crop path is duplicated: {crop_path}")
        lineage_by_path[crop_path] = row

    _, assignments = read_csv(robustness_dir / "fold_assignments.csv")
    _, predictions = read_csv(robustness_dir / "sourcewise_predictions.csv")
    _, metrics = read_csv(robustness_dir / "sourcewise_metrics.csv")
    robustness_summary = json.loads((robustness_dir / "sourcewise_summary.json").read_text(encoding="utf-8"))

    fold_sources: dict[str, set[str]] = defaultdict(set)
    for row in assignments:
        if row.get("test_source_count") != "1":
            raise AtlasError(f"Fold {row.get('fold_id')} does not have exactly one outer test source")
        fold_sources[row["fold_id"]].add(row["outer_test_image_id"])
    if any(len(sources) != 1 for sources in fold_sources.values()):
        raise AtlasError("At least one fold has multiple outer test sources")
    outer_sources = [row["outer_test_image_id"] for row in assignments]
    if len(set(outer_sources)) != len(outer_sources):
        raise AtlasError("A source image appears more than once as outer test")

    metric_by_source = {row["outer_test_image_id"]: row for row in metrics}
    threshold_by_fold = {row["fold_id"]: row["selected_threshold"] for row in metrics}
    seen_crops: set[str] = set()
    manifest_rows: list[dict[str, Any]] = []
    for row in predictions:
        crop_path_text = row["crop_path"]
        if crop_path_text in seen_crops:
            raise AtlasError(f"Crop appears in more than one outer-test fold: {crop_path_text}")
        seen_crops.add(crop_path_text)
        if row["crop_label"] not in VALID_LABELS or row["prediction"] not in VALID_LABELS:
            raise AtlasError(f"Invalid prediction labels for crop: {crop_path_text}")
        if row["selected_threshold"] != threshold_by_fold.get(row["fold_id"]):
            raise AtlasError(f"Prediction threshold does not match fold threshold: {crop_path_text}")
        lineage = lineage_by_path.get(crop_path_text)
        if lineage is None:
            raise AtlasError(f"Prediction crop path not found in lineage: {crop_path_text}")
        image_id = lineage.get("resolved_image_id", "")
        if not image_id or image_id != row["outer_test_image_id"]:
            raise AtlasError(f"Prediction crop does not map to exactly one matching source image: {crop_path_text}")
        crop_path = safe_crop_path(crops_dir, crop_path_text)
        if not crop_path.exists():
            raise AtlasError(f"Missing crop file: {crop_path_text}")
        image = cv2.imread(str(crop_path), cv2.IMREAD_COLOR)
        if image is None:
            raise AtlasError(f"Unreadable crop file: {crop_path_text}")

        kind = error_type(row["crop_label"], row["prediction"])
        probability = float(row["probability_dirty_positive"])
        threshold = float(row["selected_threshold"])
        stats = descriptive_stats(image)
        manifest_row: dict[str, Any] = {
            "fold_id": row["fold_id"],
            "image_id": image_id,
            "crop_path": crop_path_text,
            "dataset_split": lineage.get("dataset_split", ""),
            "crop_label": row["crop_label"],
            "prediction": row["prediction"],
            "error_type": kind,
            "probability_dirty_positive": f"{probability:.8f}",
            "selected_threshold": f"{threshold:.2f}",
            "threshold_margin": f"{threshold_margin(kind, probability, threshold):.8f}",
            "selected_for_contact_sheet": "false",
            "contact_sheet_path": "",
            "_abs_path": str(crop_path),
        }
        manifest_row.update({key: f"{value:.8f}" for key, value in stats.items()})
        manifest_rows.append(manifest_row)

    return {
        "manifest_rows": manifest_rows,
        "metric_by_source": metric_by_source,
        "marker_summary": marker_summary,
        "robustness_summary": robustness_summary,
        "input_hashes": {
            "fold_assignments": file_sha256(robustness_dir / "fold_assignments.csv"),
            "fold_threshold_selection": file_sha256(robustness_dir / "fold_threshold_selection.csv"),
            "sourcewise_metrics": file_sha256(robustness_dir / "sourcewise_metrics.csv"),
            "sourcewise_predictions": file_sha256(robustness_dir / "sourcewise_predictions.csv"),
            "sourcewise_summary": file_sha256(robustness_dir / "sourcewise_summary.json"),
            "crop_lineage_manifest": file_sha256(lineage_manifest),
            "marker_leakage_summary": file_sha256(marker_summary_path),
        },
    }


def rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def build_profiles(manifest_rows: list[dict[str, Any]], metric_by_source: dict[str, dict[str, str]]) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in manifest_rows:
        grouped[str(row["image_id"])].append(row)
    profiles: list[dict[str, Any]] = []
    for image_id, rows in grouped.items():
        counts = Counter(row["error_type"] for row in rows)
        label_counts = Counter(row["crop_label"] for row in rows)
        metric = metric_by_source[image_id]
        fp_rate = rate(counts["false_positive"], label_counts[NEGATIVE_CLASS])
        fn_rate = rate(counts["false_negative"], label_counts[POSITIVE_CLASS])
        f1 = float(metric["f1_dirty_positive"]) if metric["f1_dirty_positive"] else 0.0
        risk = (0.50 * fn_rate) + (0.25 * fp_rate) + (0.25 * (1 - f1))
        profiles.append(
            {
                "image_id": image_id,
                "test_crop_count": len(rows),
                "dirty_positive_count": label_counts[POSITIVE_CLASS],
                "clean_negative_count": label_counts[NEGATIVE_CLASS],
                "selected_threshold": metric["selected_threshold"],
                "accuracy": metric["accuracy"],
                "precision_dirty_positive": metric["precision_dirty_positive"],
                "recall_dirty_positive": metric["recall_dirty_positive"],
                "f1_dirty_positive": metric["f1_dirty_positive"],
                "true_positive_count": counts["true_positive"],
                "true_negative_count": counts["true_negative"],
                "false_positive_count": counts["false_positive"],
                "false_negative_count": counts["false_negative"],
                "false_positive_rate": f"{fp_rate:.8f}",
                "false_negative_rate": f"{fn_rate:.8f}",
                "business_risk_score": f"{risk:.8f}",
            }
        )

    under = sorted(profiles, key=lambda r: (-float(r["false_negative_rate"]), -int(r["false_negative_count"]), float(r["f1_dirty_positive"]), numeric_sort(r["image_id"])))
    over = sorted(profiles, key=lambda r: (-float(r["false_positive_rate"]), -int(r["false_positive_count"]), float(r["f1_dirty_positive"]), numeric_sort(r["image_id"])))
    overall = sorted(profiles, key=lambda r: (-float(r["business_risk_score"]), numeric_sort(r["image_id"])))
    for rank, row in enumerate(under, start=1):
        row["under_detection_rank"] = rank
    for rank, row in enumerate(over, start=1):
        row["over_flagging_rank"] = rank
    for rank, row in enumerate(overall, start=1):
        row["overall_business_risk_rank"] = rank
    return profiles, [r["image_id"] for r in under], [r["image_id"] for r in over], [r["image_id"] for r in overall]


def build_group_stats(manifest_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in manifest_rows:
        grouped[(row["image_id"], row["error_type"])].append(row)
    rows: list[dict[str, Any]] = []
    for image_id in sorted({row["image_id"] for row in manifest_rows}, key=numeric_sort):
        for group in ["true_positive", "false_negative", "true_negative", "false_positive"]:
            members = grouped[(image_id, group)]
            out: dict[str, Any] = {"image_id": image_id, "comparison_group": group, "crop_count": len(members)}
            for stat in STATS:
                values = [float(row[stat]) for row in members]
                out[f"{stat}_avg"] = "" if not values else f"{float(np.mean(values)):.8f}"
            rows.append(out)
    return rows


def contact_sheet(samples: list[dict[str, Any]], output_path: Path, title: str) -> None:
    thumbs = []
    cell_w, cell_h = 190, 160
    for row in samples:
        image = cv2.imread(str(row["_abs_path"]), cv2.IMREAD_COLOR)
        if image is None:
            raise AtlasError(f"Could not reload sample: {row['crop_path']}")
        image = cv2.resize(image, (128, 128), interpolation=cv2.INTER_AREA)
        canvas = np.full((cell_h, cell_w, 3), 245, dtype=np.uint8)
        canvas[:128, :128] = image
        lines = [
            Path(str(row["crop_path"])).name,
            f"T:{row['crop_label']} P:{row['prediction']}",
            f"p={row['probability_dirty_positive']} t={row['selected_threshold']}",
            f"m={row['threshold_margin']}",
        ]
        y = 14
        for text in lines:
            cv2.putText(canvas, text[:28], (3, y), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (0, 0, 0), 1, cv2.LINE_AA)
            y += 13
        thumbs.append(canvas)
    if not thumbs:
        return
    cols = min(4, len(thumbs))
    rows = int(np.ceil(len(thumbs) / cols))
    sheet = np.full((rows * cell_h + 28, cols * cell_w, 3), 255, dtype=np.uint8)
    cv2.putText(sheet, title[:90], (4, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    for index, thumb in enumerate(thumbs):
        y = 28 + (index // cols) * cell_h
        x = (index % cols) * cell_w
        sheet[y : y + cell_h, x : x + cell_w] = thumb
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), sheet):
        raise AtlasError(f"Could not write contact sheet: {output_path}")


def select_contact_examples(manifest_rows: list[dict[str, Any]], selected_sources: list[str], output_dir: Path, limit: int) -> list[dict[str, Any]]:
    by_source_group: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in manifest_rows:
        by_source_group[(row["image_id"], row["error_type"])].append(row)
    selected_rows: list[dict[str, Any]] = []
    contact_dir = output_dir / "contact_sheets"
    for image_id in selected_sources:
        for group, max_count in [("false_negative", limit), ("false_positive", limit), ("true_positive", 8), ("true_negative", 8)]:
            samples = sorted(by_source_group[(image_id, group)], key=lambda r: -float(r["threshold_margin"]))[:max_count]
            if not samples:
                continue
            sheet_path = contact_dir / f"source_{image_id}_{group}.jpg"
            rel_sheet = str(sheet_path)
            contact_sheet(samples, sheet_path, f"source {image_id} {group}")
            for row in samples:
                row["selected_for_contact_sheet"] = "true"
                row["contact_sheet_path"] = rel_sheet
                if group in {"false_negative", "false_positive"}:
                    selected_rows.append(
                        {
                            "image_id": image_id,
                            "crop_path": row["crop_path"],
                            "error_type": row["error_type"],
                            "crop_label": row["crop_label"],
                            "prediction": row["prediction"],
                            "probability_dirty_positive": row["probability_dirty_positive"],
                            "selected_threshold": row["selected_threshold"],
                            "threshold_margin": row["threshold_margin"],
                            "selection_reason": "selected high-priority source; sorted by largest threshold margin",
                            "contact_sheet_path": rel_sheet,
                        }
                    )
    return selected_rows


def diagnosis(profiles: list[dict[str, Any]]) -> str:
    thresholds = [float(row["selected_threshold"]) for row in profiles]
    fp_rates = [float(row["false_positive_rate"]) for row in profiles]
    fn_rates = [float(row["false_negative_rate"]) for row in profiles]
    if max(thresholds) - min(thresholds) >= 0.50 and (max(fp_rates) > 0.50 or max(fn_rates) > 0.40):
        return "MIXED_OR_INCONCLUSIVE"
    if max(fn_rates) > 0.40:
        return "CROP_POLICY_OR_LABEL_BOUNDARY_DOMINANT"
    if max(fp_rates) > 0.50:
        return "VISUAL_DOMAIN_SHIFT_DOMINANT"
    return "MIXED_OR_INCONCLUSIVE"


def report_text(summary: dict[str, Any], profiles: list[dict[str, Any]], group_stats: list[dict[str, Any]]) -> str:
    under = summary["top_under_detection_sources"]
    over = summary["top_over_flagging_sources"]
    overall = summary["top_business_risk_sources"]
    margin_rows = [p for p in profiles]
    threshold_values = [float(p["selected_threshold"]) for p in profiles]
    return f"""# Source-wise Error Atlas

## Objective and Scope
วิเคราะห์ error แบบ crop-level จาก sourcewise robustness output เดิมเท่านั้น ไม่มีการ train/retrain model และไม่เปลี่ยน threshold หรือ feature

## Preflight
marker leakage decision = {summary['marker_leakage_decision']}, marker_like_count = {summary['marker_like_count']}; crop paths และ fold/source mapping ผ่าน preflight

## Error Totals
- true_positive: {summary['true_positive_count']}
- true_negative: {summary['true_negative_count']}
- false_positive: {summary['false_positive_count']}
- false_negative: {summary['false_negative_count']}

## Rankings
- Under-detection top 5: {', '.join(under)}
- Over-flagging top 5: {', '.join(over)}
- Overall business-risk top 5: {', '.join(overall)}

Business risk score = 0.50 * false_negative_rate + 0.25 * false_positive_rate + 0.25 * (1 - f1_dirty_positive)

## Threshold Variability
selected threshold range = {min(threshold_values):.2f} to {max(threshold_values):.2f}; variability นี้ชี้ว่า threshold transfer ระหว่าง source ยังไม่นิ่ง

## Error-confidence Margin
ใช้ margin เพื่อจัดลำดับตัวอย่าง review เท่านั้น: false_positive ใช้ probability - threshold และ false_negative ใช้ threshold - probability

## Image-only Descriptive Statistics
คำนวณ grayscale, HSV saturation/value, Laplacian variance และ edge fraction จาก crop pixels เท่านั้น เพื่อใช้ตั้งสมมติฐานเรื่อง lighting/background/edge/context ไม่ใช่ feature training ใหม่

## Contact Sheets
สร้างเฉพาะ source ที่ถูกเลือกจาก top 5 ของ business risk, under-detection และ over-flagging; path อยู่ใน contact_sheets/

## Observed Facts
- วิเคราะห์ predictions ทั้งหมด {summary['prediction_count']} rows
- source ที่มี business risk สูงสุด: {overall[0] if overall else 'n/a'}
- มีทั้ง false_positive และ false_negative ในหลาย source จึงไม่ใช่ pattern เดี่ยวที่อธิบายได้ง่าย

## Evidence-supported Hypotheses
- Possible threshold-transfer issue จาก threshold range ที่กว้าง
- Possible visual/domain-shift issue ใน source ที่ over-flagging สูง
- Possible crop-policy or label-boundary issue ใน source ที่ under-detection สูงและมี high-margin false negative

## Unresolved Questions
- ต้องดู contact sheets ด้วยคนเพื่อแยกว่า error เกิดจาก lighting/background, crop context, หรือ label-boundary
- ยังไม่ควรสรุปเป็น whole-image quality หรือ PASS/FAIL decision

## Final Diagnosis
{summary['final_diagnosis']}

## Exact Next Recommendation
A. Collect more independent source images
B. Review crop-policy and label-boundary cases
C. Standardize capture/lighting/background conditions
D. Design a later feature/model experiment after error review

No source image, crop, label, Ground Truth, or split manifest was modified.
No model was trained or retrained.
No Blue Marker or annotation metadata was used as a model feature.
This analysis does not produce bird-nest PASS/FAIL decisions.
"""


PROFILE_COLUMNS = [
    "image_id", "test_crop_count", "dirty_positive_count", "clean_negative_count", "selected_threshold", "accuracy",
    "precision_dirty_positive", "recall_dirty_positive", "f1_dirty_positive", "true_positive_count", "true_negative_count",
    "false_positive_count", "false_negative_count", "false_positive_rate", "false_negative_rate", "business_risk_score",
    "under_detection_rank", "over_flagging_rank", "overall_business_risk_rank",
]
PRIORITY_COLUMNS = ["image_id", "business_risk_score", "overall_business_risk_rank", "under_detection_rank", "over_flagging_rank", "false_negative_rate", "false_positive_rate", "f1_dirty_positive", "priority_reason"]
MANIFEST_COLUMNS = ["fold_id", "image_id", "crop_path", "dataset_split", "crop_label", "prediction", "error_type", "probability_dirty_positive", "selected_threshold", "threshold_margin", *STATS, "selected_for_contact_sheet", "contact_sheet_path"]
GROUP_COLUMNS = ["image_id", "comparison_group", "crop_count", *(f"{stat}_avg" for stat in STATS)]
SELECTED_COLUMNS = ["image_id", "crop_path", "error_type", "crop_label", "prediction", "probability_dirty_positive", "selected_threshold", "threshold_margin", "selection_reason", "contact_sheet_path"]


def build_atlas(crops_dir: Path, robustness_dir: Path, lineage_manifest: Path, marker_audit_dir: Path, output_dir: Path, max_samples_per_error_group: int, enforce_empty_output: bool = True) -> dict[str, Any]:
    if enforce_empty_output:
        ensure_output_empty(output_dir)
    data = load_and_validate(crops_dir, robustness_dir, lineage_manifest, marker_audit_dir)
    manifest_rows = data["manifest_rows"]
    profiles, under, over, overall = build_profiles(manifest_rows, data["metric_by_source"])
    selected_sources = sorted(set(overall[:5] + under[:5] + over[:5]), key=numeric_sort)
    output_dir.mkdir(parents=True, exist_ok=False)
    selected_examples = select_contact_examples(manifest_rows, selected_sources, output_dir, max_samples_per_error_group)
    group_stats = build_group_stats(manifest_rows)

    priority_rows = []
    by_id = {row["image_id"]: row for row in profiles}
    for image_id in sorted(by_id, key=lambda source: int(by_id[source]["overall_business_risk_rank"])):
        row = by_id[image_id]
        reasons = []
        if int(row["overall_business_risk_rank"]) <= 5:
            reasons.append("top overall business risk")
        if int(row["under_detection_rank"]) <= 5:
            reasons.append("top under-detection")
        if int(row["over_flagging_rank"]) <= 5:
            reasons.append("top over-flagging")
        priority_rows.append({**{col: row[col] for col in PRIORITY_COLUMNS if col != "priority_reason"}, "priority_reason": "; ".join(reasons) or "lower priority"})

    source_profile_path = output_dir / "source_error_profile.csv"
    priority_path = output_dir / "source_priority_ranking.csv"
    manifest_path = output_dir / "error_atlas_manifest.csv"
    group_path = output_dir / "error_group_statistics.csv"
    selected_path = output_dir / "selected_error_examples.csv"
    write_csv(source_profile_path, PROFILE_COLUMNS, sorted(profiles, key=lambda r: numeric_sort(r["image_id"])))
    write_csv(priority_path, PRIORITY_COLUMNS, priority_rows)
    public_manifest = [{key: row.get(key, "") for key in MANIFEST_COLUMNS} for row in manifest_rows]
    write_csv(manifest_path, MANIFEST_COLUMNS, public_manifest)
    write_csv(group_path, GROUP_COLUMNS, group_stats)
    write_csv(selected_path, SELECTED_COLUMNS, selected_examples)

    counts = Counter(row["error_type"] for row in manifest_rows)
    summary = {
        "source_image_count": len(profiles),
        "prediction_count": len(manifest_rows),
        "false_positive_count": counts["false_positive"],
        "false_negative_count": counts["false_negative"],
        "true_positive_count": counts["true_positive"],
        "true_negative_count": counts["true_negative"],
        "top_business_risk_sources": overall[:5],
        "top_under_detection_sources": under[:5],
        "top_over_flagging_sources": over[:5],
        "contact_sheet_source_count": len(selected_sources),
        "contact_sheet_error_example_count": len(selected_examples),
        "marker_leakage_decision": data["marker_summary"]["decision"],
        "marker_like_count": data["marker_summary"]["marker_like_count"],
        "final_diagnosis": diagnosis(profiles),
        "input_file_hashes": data["input_hashes"],
        "output_hash_scope": "primary_csv_artifacts_only",
        "output_file_hashes": {
            "source_error_profile.csv": file_sha256(source_profile_path),
            "source_priority_ranking.csv": file_sha256(priority_path),
            "error_atlas_manifest.csv": file_sha256(manifest_path),
            "error_group_statistics.csv": file_sha256(group_path),
            "selected_error_examples.csv": file_sha256(selected_path),
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    (output_dir / "error_atlas_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / "error_atlas_report.md").write_text(report_text(summary, profiles, group_stats), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build source-wise error atlas from existing robustness predictions.")
    parser.add_argument("--crops-dir", type=Path, required=True)
    parser.add_argument("--robustness-dir", type=Path, required=True)
    parser.add_argument("--lineage-manifest", type=Path, required=True)
    parser.add_argument("--marker-audit-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-samples-per-error-group", type=int, default=16)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        summary = build_atlas(args.crops_dir, args.robustness_dir, args.lineage_manifest, args.marker_audit_dir, args.output_dir, args.max_samples_per_error_group)
    except AtlasError as exc:
        raise SystemExit(f"BLOCKED_INPUT_VALIDATION: {exc}") from exc
    print(f"Source-wise error atlas complete: {args.output_dir.resolve()}")
    print(f"Predictions analyzed: {summary['prediction_count']}")
    print(f"Errors: FP={summary['false_positive_count']} FN={summary['false_negative_count']}")
    print(f"Diagnosis: {summary['final_diagnosis']}")


if __name__ == "__main__":
    main()
