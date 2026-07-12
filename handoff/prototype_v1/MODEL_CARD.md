# Model Card: BirdNests Faster R-CNN Engineering Prototype

## Intended Use

Engineering review of dirty-spot candidate detections in bird-nest images.

## Out-of-Scope Use

Production automation, expert-confirmed quality decisions, medical/food-safety certification, or guaranteed detection.

## Model Architecture

- Family: Faster R-CNN
- Architecture: FasterRCNN_MobileNetV3-Large-FPN
- Classes: 2 (`background`, `dirty_spot_candidate`)
- Maturity: Engineering Prototype

## Dataset And Evaluation Scope

- Approved Prototype dataset scope: 240 raw/marker pairs.
- Validation sources: 36.
- Validation model-input tiles: 432.
- Do not state that all 240 pairs were training images.

## Operating Points

- Primary: threshold 0.125, Recall 70.99%, `MODEL_ONLY_MARKER_ABSENT` 1785.
- Comparison: threshold 0.175, `MODEL_ONLY_MARKER_ABSENT` 405.

## Terminology

`MODEL_ONLY_MARKER_ABSENT` means a merged model prediction at the frozen threshold that does not match the original marker-derived Ground Truth under the frozen matching rule. It is not a confirmed false positive and not an expert-confirmed dirty spot.

## Limitations

Marker incompleteness may exist but must not be assumed for an individual point. The Prototype is not production-ready. Contact Sheets require human review.

## Ethical And Operational Considerations

Keep raw/marker datasets private unless explicitly approved. Treat public Contact Sheet images as publication-sensitive evidence.

## Version Identity

- Version: `prototype_v1`
- Checkpoint SHA256: `660b59465e1514f39eae79c4a53d2cc4181c0d829bd1365be853c6260b0def5c`
- Python: 3.12.5
- PyTorch: 2.8.0
- Torchvision: 0.23.0
