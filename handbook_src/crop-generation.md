# Crop Generation Workflow

## Executable

`crop_clean_patches.py`

## Purpose

สร้าง `clean_negative` และ `dirty_positive` crop patches จาก `RawPics` พร้อม metadata สำหรับ traceability

## Safe Command

```powershell
.\.venv\Scripts\python.exe crop_clean_patches.py --raw-dir RawPics --output-dir Crops
```

Default behavior keeps existing output files.

## Risky Flag

`--clear-output` deletes previous generated `.jpg` files in `clean_negative` and `dirty_positive`, plus `.png`/`.jpg` files in `debug_masks` under the selected output directory.

ใช้เมื่อ output directory นั้น disposable หรือ backup แล้วเท่านั้น

## Key Output

`Crops/metadata.csv` มี columns เช่น `source_id`, `source_image`, `marked_image`, `output_file`, `label`, `dirty_spot_id`, `generation_method`
