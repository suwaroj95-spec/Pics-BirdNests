# Structured Expert Review Result Format

This static review site exports the Small Anchor expert review as CSV or JSON. The preferred Phase 8 input is the structured JSON or CSV export from this page.

## Identity

Importers must validate these fields before accepting a file:

- `reviewSchemaVersion`: `1.0.0`
- `packageId`: `package_a_small_anchor_0125`
- `modelProfile`: `small_16_32_64_128`
- `checkpointSha256`: `e9f4d2e1b8530662fd3390165419008647c7d9baaf80e8a2d3cc4108b22fa7c0`
- `threshold`: `0.125`
- `manifestIdentifier`: the `card_manifest_sha256:...` value in `data/review-data.json`

Reject files from another package, checkpoint, threshold, or manifest.

## Reviewer Selection

- blank: accepted only when `pageCompleted=true`
- `F`: false positive
- `P`: pairing error
- `U`: uncertain

Blank cards on unfinished pages remain `NOT_REVIEWED`.

## Final Classification

- completed page + blank: `HUMAN_ACCEPTED_TRUE_POSITIVE`
- `F`: `FALSE_POSITIVE_BY_EXPERT`
- `P`: `PAIRING_ERROR`
- `U`: `UNRESOLVED`
- incomplete page + blank: `NOT_REVIEWED`

## Required Per-Card Fields

- `cardId`
- `cardIndex`
- `page`
- `position`
- `sourceId`
- `predictionId`
- `score`
- `bboxX1`
- `bboxY1`
- `bboxX2`
- `bboxY2`
- `reviewerSelection`
- `reviewStatus`
- `finalClassification`
- `pageCompleted`
- `pageCompletedAt`
- `exportedAt`

The JSON export contains a top-level `summary` and `results` array. The CSV export contains one row per card with the same card-level fields.

## Phase 8 Use

Place the exported `small_anchor_0125_expert_review_results.json` or `.csv` in the Phase 8 incoming review folder. Phase 8 should prefer this structured file and keep the older image-page review path only as a fallback for legacy reviewed PNG pages.
