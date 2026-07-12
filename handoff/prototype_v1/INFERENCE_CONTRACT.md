# Inference Contract

Entry point:

```powershell
python .\tools\run_prototype_inference.py --input <file-or-directory> --output <output-dir> --checkpoint <final_checkpoint.pt> --config .\handoff\prototype_v1\prototype_runtime_config.json --threshold 0.125 --device cpu --save-json predictions.json --save-preview previews
```

## Input

- Supported formats: JPG, JPEG, PNG, BMP, TIFF, WEBP.
- Color mode: input is converted to RGB.
- Input may be one file or a directory of supported image files.
- Images keep their original dimensions.
- Tiling uses the frozen tile size and overlap from the runtime config.
- Unsupported inputs fail before checkpoint loading.

## Output JSON Schema

- `schema_version`
- `model_version`
- `checkpoint_sha256`
- `source_file`
- `source_width`
- `source_height`
- `threshold`
- `coordinate_system`
- `predictions[]`
- `prediction_id`
- `score`
- `x1`, `y1`, `x2`, `y2`
- `center_x`, `center_y`
- `runtime_warnings`

Coordinates are pixel coordinates in the original source image, origin at top-left. Normal output uses a source filename, not an absolute local path.

## Preview Output

Preview boxes use cyan annotation, include the threshold label, and carry the engineering Prototype disclaimer. Preview output does not imply Ground Truth.
