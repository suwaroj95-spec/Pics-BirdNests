# BirdNests Prototype v1 Company Handoff

Status: Engineering Prototype.

The repository contains a frozen Faster R-CNN Prototype for dirty-spot detection in bird-nest imagery, sanitized Contact Sheets, public documentation and a stable inference command contract.

## Start Here

1. Read `MODEL_CARD.md`.
2. Install from `INSTALLATION.md`.
3. Review `INFERENCE_CONTRACT.md`.
4. Obtain the checkpoint from the later GitHub Release asset listed in `checkpoint_release_manifest.json`.
5. Run `tools/run_prototype_inference.py` only after installing the model runtime.

## Release Downloads

- Release page: https://github.com/suwaroj95-spec/Pics-BirdNests/releases/tag/v0.1.0-prototype
- `final_checkpoint.pt`: https://github.com/suwaroj95-spec/Pics-BirdNests/releases/download/v0.1.0-prototype/final_checkpoint.pt
- `birdnests_prototype_v1_company_handoff.zip`: https://github.com/suwaroj95-spec/Pics-BirdNests/releases/download/v0.1.0-prototype/birdnests_prototype_v1_company_handoff.zip
- `SHA256SUMS.txt`: https://github.com/suwaroj95-spec/Pics-BirdNests/releases/download/v0.1.0-prototype/SHA256SUMS.txt

## Key Facts

- Approved Prototype data scope: 240 raw/marker pairs.
- Validation sources: 36.
- Validation model-input tiles: 432.
- Primary threshold: 0.125.
- Primary Recall: 70.99%.
- Primary `MODEL_ONLY_MARKER_ABSENT`: 1785.
- Comparison threshold: 0.175.
- Comparison `MODEL_ONLY_MARKER_ABSENT`: 405.

This handoff intentionally excludes raw datasets, marker datasets, local caches, optimizer states and checkpoints from regular Git.
