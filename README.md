# BirdNests Faster R-CNN Prototype

This repository contains the BirdNests engineering Prototype for dirty-spot detection in bird-nest images. The current handoff state includes a frozen Faster R-CNN engineering Prototype, verified evaluation policy, sanitized Contact Sheets, and GitHub Pages documentation.

This is an engineering Prototype, not a production-ready system and not an expert-confirmed detector.

## Current Status

- Prototype status: `FASTER_RCNN_PILOT_PROMISING`
- Frozen configuration: `PROTOTYPE_CONFIGURATION_FROZEN`
- Approved dataset scope: 240 raw/marker pairs incorporated into the Prototype data pipeline
- Validation scope: 36 sources, 432 model-input tiles
- Primary operating point: threshold `0.125`, Recall `70.99%`, `MODEL_ONLY_MARKER_ABSENT` = 1,785
- Comparison operating point: threshold `0.175`, `MODEL_ONLY_MARKER_ABSENT` = 405
- Sanitized public Contact Sheet viewer: `docs/contact-sheets/index.html`

The 240 approved pairs are the approved Prototype dataset scope. Do not describe all 240 pairs as training images.

## Dataset Summary

The dataset status page reports the completed Prototype data scope:

- 512 received files
- 480 usable files
- 240 valid raw/marker pairs
- 32 excluded files
- 7,115 verified marker points
- 3 completed data sets

See `docs/dataset-cleansing-status.html`.

## Model Summary

The Prototype uses Faster R-CNN with a MobileNetV3-Large-FPN backbone and 2 classes: background and dirty-spot candidate. The selected checkpoint is the frozen final checkpoint from the controlled CUDA pilot run.

The primary threshold `0.125` is recall-prioritized for review. The comparison threshold `0.175` provides a lower-workload reference point. `MODEL_ONLY_MARKER_ABSENT` means a merged model prediction that does not match the original marker-derived Ground Truth under the frozen matching rule. It does not mean confirmed false positive or confirmed dirty spot.

## Documentation Links

- Gateway: `docs/index.html`
- Workflow infographic: `docs/birdnests-workflow-infographic.html`
- Dataset status: `docs/dataset-cleansing-status.html`
- Model Prototype infographic: `docs/birdnests-model-prototype-infographic.html`
- Sanitized Contact Sheet viewer: `docs/contact-sheets/index.html`
- Company handoff package: `handoff/prototype_v1/README_HANDOFF.md`

## Quick Start Paths

For documentation review, open `docs/index.html` locally or through GitHub Pages after publication.

For engineering handoff, start with:

```powershell
Get-Content .\handoff\prototype_v1\README_HANDOFF.md
Get-Content .\handoff\prototype_v1\INSTALLATION.md
Get-Content .\handoff\prototype_v1\INFERENCE_CONTRACT.md
```

## Environment Installation

Core project utilities remain in `InstallKit/requirements-core.txt`.

The model runtime requirements are split into:

- `InstallKit/requirements-model-common.txt`
- `InstallKit/requirements-model-cuda.txt`

Use the official PyTorch selector for the exact CUDA build that matches the target machine. Do not assume CUDA wheels can be installed from the default PyPI index.

## Stable Inference Entry Point

The supported entry point is:

```powershell
python .\tools\run_prototype_inference.py `
  --input .\path\to\image-or-directory `
  --output .\prototype_inference_output `
  --checkpoint .\path\to\final_checkpoint.pt `
  --config .\handoff\prototype_v1\prototype_runtime_config.json `
  --threshold 0.125 `
  --device cpu `
  --save-json predictions.json `
  --save-preview previews
```

The wrapper validates arguments without loading the checkpoint. It loads PyTorch and the checkpoint only when actual inference is requested.

## Contact Sheet Viewer

The public viewer uses sanitized page images and a sanitized manifest only:

- `docs/contact-sheets/index.html`
- `docs/contact-sheets/contact-sheet-manifest.json`
- `docs/contact-sheets/pages/primary/`
- `docs/contact-sheets/pages/comparison/`

The Contact Sheet is for engineering review. It is not expert-confirmed Ground Truth.

## Checkpoint Distribution Policy

Do not commit checkpoint files to regular Git and do not copy them into `docs/`.

The authoritative frozen checkpoint should be distributed later as a GitHub Release asset:

```text
final_checkpoint.pt
```

SHA256:

```text
660b59465e1514f39eae79c4a53d2cc4181c0d829bd1365be853c6260b0def5c
```

## Limitations

- Engineering Prototype only; not production-ready.
- Contact Sheet labels are model-vs-marker review states, not expert decisions.
- Marker incompleteness is a possible limitation but must not be assumed for any individual point.
- CUDA memory and production throughput require further benchmarking.
- Publication of image-derived Contact Sheet pages requires owner authorization even when privacy sanitization passes.

## Repository And Data-Publication Policy

The repository is public after publication. Public Contact Sheet images are accessible to anyone who knows or discovers the URL. Raw images, marker images, local datasets, caches, temporary runs, checkpoints, optimizer states, and secrets must not be committed unless explicitly approved and documented.

## Tests And Validation

Focused non-inference tests cover inference CLI validation, output schema construction, and public Contact Sheet manifest/link checks:

```powershell
python -m unittest tests.test_run_prototype_inference tests.test_contact_sheet_public_manifest -v
```

These tests do not load the checkpoint, run inference, or require CUDA.

## Company Handoff Package

The package lives at:

```text
handoff/prototype_v1/
```
