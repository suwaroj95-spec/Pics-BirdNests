from __future__ import annotations

import csv
import hashlib
import json
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


TERMINOLOGY = "MODEL_ONLY_MARKER_ABSENT"
DISCLAIMER = "Engineering comparison only - not expert-confirmed"
LEFT_PANEL_HEADING = "RAW IMAGE (NO OVERLAY)"
RIGHT_PANEL_HEADING = "ORIGINAL MARKER IMAGE + MODEL LOCATION GUIDE"
LAYOUT_VERSION = "raw-left_marker-plus-model-guide-right_v2"
CYAN = (0, 220, 255)
BLACK = (20, 24, 32)
GRAY = (105, 112, 125)
LINE = (210, 215, 225)


@dataclass(frozen=True)
class ContactSheetRecord:
    card_id: str
    source_id: str
    score_display: str
    threshold_string: str
    comparison_status: str
    page_number: int
    page_position: int
    raw_image_path: str
    marker_image_path: str
    box: tuple[float, float, float, float]
    crop: tuple[int, int, int, int]

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "ContactSheetRecord":
        return cls(
            card_id=row["card_id"],
            source_id=row["source_id"],
            score_display=row["score_display"],
            threshold_string=row["primary_threshold_string"],
            comparison_status=row["comparison_status"],
            page_number=int(row["contact_sheet_page"]),
            page_position=int(row["page_card_position"]),
            raw_image_path=row["raw_image_path"],
            marker_image_path=row["marker_image_path"],
            box=(
                float(row["merged_box_x1"]),
                float(row["merged_box_y1"]),
                float(row["merged_box_x2"]),
                float(row["merged_box_y2"]),
            ),
            crop=(
                int(row["final_crop_x1"]),
                int(row["final_crop_y1"]),
                int(row["final_crop_x2"]),
                int(row["final_crop_y2"]),
            ),
        )


def load_records(path: Path) -> list[ContactSheetRecord]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [ContactSheetRecord.from_row(row) for row in csv.DictReader(handle)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_font(size: int) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "DejaVuSans.ttf", "tahoma.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_12 = text_font(12)
FONT_14 = text_font(14)
FONT_18 = text_font(18)
FONT_28 = text_font(28)


def crop_and_resize(image: Image.Image, crop: tuple[int, int, int, int], panel_size: int = 360) -> Image.Image:
    return image.crop(crop).copy().resize((panel_size, panel_size), Image.Resampling.LANCZOS)


def draw_model_guide(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    crop: tuple[int, int, int, int],
    scale: float,
    offset: tuple[int, int],
) -> None:
    ox, oy = offset
    crop_x1, crop_y1, _crop_x2, _crop_y2 = crop
    box_x1, box_y1, box_x2, box_y2 = box
    x1 = ox + (box_x1 - crop_x1) * scale
    y1 = oy + (box_y1 - crop_y1) * scale
    x2 = ox + (box_x2 - crop_x1) * scale
    y2 = oy + (box_y2 - crop_y1) * scale
    draw.rectangle((x1, y1, x2, y2), outline=CYAN, width=3)
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    draw.line((cx - 8, cy, cx + 8, cy), fill=CYAN, width=2)
    draw.line((cx, cy - 8, cx, cy + 8), fill=CYAN, width=2)


def render_contact_card(record: ContactSheetRecord, raw_image: Image.Image, marker_image: Image.Image) -> Image.Image:
    panel = 360
    raw_crop = crop_and_resize(raw_image, record.crop, panel)
    marker_crop = crop_and_resize(marker_image, record.crop, panel)

    card = Image.new("RGB", (900, 560), "white")
    draw = ImageDraw.Draw(card)
    draw.rectangle((0, 0, 899, 559), outline=LINE, width=1)
    draw.text((18, 12), f"{record.card_id}  {TERMINOLOGY}", fill=BLACK, font=FONT_18)
    draw.text(
        (18, 38),
        f"Source {record.source_id}  score {record.score_display}  threshold {record.threshold_string}  {record.comparison_status}",
        fill=BLACK,
        font=FONT_14,
    )
    draw.text((18, 58), f"Page {record.page_number:03d} pos {record.page_position:02d}   {DISCLAIMER}", fill=GRAY, font=FONT_12)
    draw.text((18, 82), LEFT_PANEL_HEADING, fill=BLACK, font=FONT_14)
    draw.text((468, 82), RIGHT_PANEL_HEADING, fill=BLACK, font=FONT_14)
    card.paste(raw_crop, (18, 104))
    card.paste(marker_crop, (468, 104))

    scale = panel / max(1, record.crop[2] - record.crop[0])
    draw_model_guide(draw, record.box, record.crop, scale, (468, 104))

    box_x1, box_y1, box_x2, box_y2 = record.box
    crop_x1, crop_y1, crop_x2, crop_y2 = record.crop
    draw.text((18, 474), f"box x1={box_x1:.1f} y1={box_y1:.1f} x2={box_x2:.1f} y2={box_y2:.1f}", fill=BLACK, font=FONT_14)
    draw.text((18, 496), f"crop {crop_x1},{crop_y1} - {crop_x2},{crop_y2}", fill=BLACK, font=FONT_14)
    return card


def render_contact_card_from_paths(project_root: Path, record: ContactSheetRecord) -> Image.Image:
    raw_path = project_root / record.raw_image_path
    marker_path = project_root / record.marker_image_path
    with Image.open(raw_path).convert("RGB") as raw, Image.open(marker_path).convert("RGB") as marker:
        return render_contact_card(record, raw, marker)


def save_contact_cards(project_root: Path, records: list[ContactSheetRecord], cards_dir: Path) -> list[Path]:
    cards_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for record in records:
        path = cards_dir / f"{record.card_id}.jpg"
        render_contact_card_from_paths(project_root, record).save(path, "JPEG", quality=88, optimize=True)
        paths.append(path)
    return paths


def render_page(
    card_paths: list[Path],
    title: str,
    threshold: str,
    page_num: int,
    page_count: int,
    total_cards: int,
    out_path: Path,
    source_range: str,
) -> None:
    page = Image.new("RGB", (3508, 2480), "white")
    draw = ImageDraw.Draw(page)
    draw.text((80, 42), title, fill=BLACK, font=FONT_28)
    draw.text((80, 78), f"Threshold {threshold} | page {page_num}/{page_count} | total cards {total_cards} | sources {source_range}", fill=BLACK, font=FONT_18)
    draw.text((80, 104), "Legend: left raw crop has no overlay | right marker crop preserves source markers; cyan = model location guide", fill=GRAY, font=FONT_14)
    card_w, card_h = 820, 430
    x0, y0 = 80, 145
    gap_x, gap_y = 35, 28
    for i, path in enumerate(card_paths):
        with Image.open(path).convert("RGB") as card:
            thumb = card.resize((card_w, card_h), Image.Resampling.LANCZOS)
        col, row = i % 4, i // 4
        page.paste(thumb, (x0 + col * (card_w + gap_x), y0 + row * (card_h + gap_y)))
    draw.text((80, 2430), "Engineering prototype comparison; not production-final", fill=GRAY, font=FONT_14)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    page.save(out_path, "PNG")


def render_pages(
    records: list[ContactSheetRecord],
    card_paths: list[Path],
    pages_dir: Path,
    filename_prefix: str,
    threshold: str,
    title: str,
) -> list[Path]:
    pages_dir.mkdir(parents=True, exist_ok=True)
    out_paths: list[Path] = []
    page_count = (len(card_paths) + 19) // 20
    for page_num in range(1, page_count + 1):
        start, end = (page_num - 1) * 20, page_num * 20
        chunk_paths = card_paths[start:end]
        chunk_records = records[start:end]
        sources = [record.source_id for record in chunk_records]
        source_range = "" if not sources else f"{sources[0]} to {sources[-1]}"
        out_path = pages_dir / f"{filename_prefix}_page_{page_num:03d}.png"
        render_page(chunk_paths, title, threshold, page_num, page_count, len(card_paths), out_path, source_range)
        out_paths.append(out_path)
    return out_paths


def assert_order_preserved(records: list[ContactSheetRecord], expected_ids: Iterable[str]) -> None:
    actual = [record.card_id for record in records]
    expected = list(expected_ids)
    if actual != expected:
        raise ValueError("record identity/order changed")


def update_public_manifest(manifest_path: Path, project_root: Path, generated_at: str | None = None) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generated_at"] = generated_at or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    manifest["layout_version"] = LAYOUT_VERSION
    manifest["panel_semantics"] = {
        "left": LEFT_PANEL_HEADING,
        "right": RIGHT_PANEL_HEADING,
    }
    for group in ("primary", "comparison"):
        for page in manifest["sets"][group]["pages"]:
            public_path = page["public_path"]
            path = project_root / "docs" / "contact-sheets" / public_path
            page["size_bytes"] = path.stat().st_size
            page["sha256"] = sha256(path)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def render_record_set(
    project_root: Path,
    records_csv: Path,
    cards_dir: Path,
    pages_dir: Path,
    filename_prefix: str,
    threshold: str,
    title: str,
    only_card_id: str | None = None,
) -> dict[str, object]:
    records = load_records(records_csv)
    if only_card_id:
        records = [record for record in records if record.card_id == only_card_id]
        if not records:
            raise ValueError(f"card id not found: {only_card_id}")
    expected_ids = [record.card_id for record in records]
    assert_order_preserved(records, expected_ids)
    card_paths = save_contact_cards(project_root, records, cards_dir)
    page_paths = render_pages(records, card_paths, pages_dir, filename_prefix, threshold, title)
    return {
        "records": len(records),
        "cards": len(card_paths),
        "pages": len(page_paths),
        "first_card": records[0].card_id if records else None,
        "last_card": records[-1].card_id if records else None,
        "page_paths": [str(path) for path in page_paths],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render sanitized public BirdNests contact sheet pages from frozen CSV inputs.")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--records-csv", type=Path, required=True)
    parser.add_argument("--cards-dir", type=Path, required=True)
    parser.add_argument("--pages-dir", type=Path, required=True)
    parser.add_argument("--filename-prefix", required=True)
    parser.add_argument("--threshold", required=True)
    parser.add_argument("--title", default=f"Faster R-CNN Prototype - {TERMINOLOGY}")
    parser.add_argument("--only-card-id")
    args = parser.parse_args()
    result = render_record_set(
        project_root=args.project_root,
        records_csv=args.records_csv,
        cards_dir=args.cards_dir,
        pages_dir=args.pages_dir,
        filename_prefix=args.filename_prefix,
        threshold=args.threshold,
        title=args.title,
        only_card_id=args.only_card_id,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
