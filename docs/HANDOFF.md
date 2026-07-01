# HANDOFF

## 1. Final Goal

Build a clean, traceable red-marker training dataset for Pics-BirdNests from the original LINE image batch, without modifying source images. The current intended training-ready artifact is the V2 final red batch:

`D:\Pics-BirdNests\Staging_Final_Red_16_to_186_V2`

This V2 batch has passed review-aware red-marker preflight and is safe to proceed to red Ground Truth generation.

## 2. Completed Work

### Dataset reconciliation and staging

- Created approved reconciliation materializer:
  - `tools/materialize_approved_reconciliation.py`
  - `tests/test_materialize_approved_reconciliation.py`
- Materialized reconciled original-name staging folder:
  - `New_RawPics_birdnest_1_reconciled`
- Approved exclusions:
  - `S__3956902_2.jpg`
  - `S__10690658_1.jpg`

### Importer preflight and review helpers

- Ran importer preflight on reconciled batch:
  - `tmp/line_sorted_import/preflight_20260701_084102`
- Created marker review queue exporter:
  - `tools/export_marker_review_queue.py`
  - `tests/test_export_marker_review_queue.py`
- Created review queue audit:
  - `tmp/line_sorted_import/review_queue_audit_20260701_102159`

### Unresolved pair integrity audit

- Created unresolved-pair integrity audit:
  - `tools/audit_unresolved_pair_integrity.py`
  - `tests/test_audit_unresolved_pair_integrity.py`
- Latest audit output:
  - `tmp/line_sorted_import/unresolved_pair_integrity_20260701_104122`
- Result:
  - 26 unresolved `BOTH_MARKER_LIKE` pairs
  - 3 exact duplicate pairs
  - 23 distinct-image marker-role review pairs

### V1 final red batch

- Created V1 final training resolution:
  - `docs/final_training_resolution_20260701.csv`
- Created/updated final batch materializer:
  - `tools/materialize_final_trainable_red_batch.py`
  - `tests/test_materialize_final_trainable_red_batch.py`
- V1 final staging folder:
  - `Staging_Final_Red_16_to_189`
- V1 result:
  - 174 pairs
  - 348 files
  - IDs 16-189
  - pair 95 role-swapped in V1

### V2 final red batch

- Created V2 final training resolution:
  - `docs/final_training_resolution_20260701_v2.csv`
- V2 quarantines:
  - `17, 72, 74, 83, 85, 87, 88, 89, 93, 95, 100, 101, 102`
- V2 output:
  - `Staging_Final_Red_16_to_186_V2`
- V2 result:
  - 171 pairs
  - 342 files
  - IDs 16-186
  - no role-swap decisions remain
  - pair 95 is quarantined

### Red-marker preflight

- Created review-aware red-marker preflight:
  - `tools/preflight_red_marker_batch.py`
  - `tests/test_preflight_red_marker_batch.py`
- Created V2 raw-red review resolution:
  - `docs/red_marker_preflight_review_resolution_20260701_v2.csv`
- Latest V2 preflight:
  - `tmp/red_marker_preflight_v2/run_20260701_150941`
- V2 preflight result:
  - 171 pairs
  - 342 files
  - `SAFE_MARKER_PAIR`: 158
  - `APPROVED_RAW_RED_CONTENT`: 13
  - blocking exceptions: 0
  - `safe_to_proceed_to_red_ground_truth`: true
  - no Ground Truth created

## 3. Remaining Work

Recommended next steps, in order:

1. Create red Ground Truth generation support for `Staging_Final_Red_16_to_186_V2`.
2. Use `tmp/red_marker_preflight_v2/run_20260701_150941` as the preflight gate.
3. Generate red-marker labels only after verifying the preflight summary still reports zero blocking exceptions.
4. Run crop generation only after red Ground Truth manifests are created and audited.
5. Run split/training steps only after crop and lineage audits pass.

Do not go back to V1 for training unless explicitly requested. V1 is an archived intermediate artifact.

## 4. Invariants and Do-Not-Change Rules

- Do not modify original LINE images.
- Do not modify `RawPics`.
- Do not modify `New_RawPics_birdnest_1`.
- Do not modify `New_RawPics_birdnest_1_reconciled`.
- Do not modify V1 staging folder `Staging_Final_Red_16_to_189`.
- Do not modify V2 staging folder `Staging_Final_Red_16_to_186_V2` unless a future task explicitly requests a new copy-only materialization.
- Do not alter frozen source plan:
  - `tmp/line_sorted_import/preflight_20260701_084102/rename_plan.csv`
- Do not re-sort and re-pair images after exclusions.
- Preserve original frozen pair membership from `rename_plan.csv`.
- Use V2 IDs 16-186 for the current final red training batch.
- Keep red marker policy unchanged:
  - HSV red detection uses lower and upper hue regions.
  - minimum component area is 20 px.
  - one connected marker component equals one dirty spot.
  - no automatic merge of separate components.
  - raw enclosing-circle radius remains authoritative later.
  - clamp 16-50 is preview-only later.
- The 13 `APPROVED_RAW_RED_CONTENT` cases are approved by composite provenance key:
  - `original_pair_sequence + source_filename + raw_source_sha256`
  - SHA alone is not unique enough.

## 5. Verification Commands Already Run

Latest full test run:

```powershell
cd D:\Pics-BirdNests
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Result:

```text
Ran 188 tests in 146.511s
OK (skipped=1)
```

Latest V2 red-marker preflight command:

```powershell
cd D:\Pics-BirdNests
.\.venv\Scripts\python.exe .\tools\preflight_red_marker_batch.py `
  --input-dir "D:\Pics-BirdNests\Staging_Final_Red_16_to_186_V2" `
  --review-resolution-csv "D:\Pics-BirdNests\docs\red_marker_preflight_review_resolution_20260701_v2.csv"
```

Result folder:

`tmp/red_marker_preflight_v2/run_20260701_150941`

Summary:

```json
{
  "total_pair_count": 171,
  "total_image_file_count": 342,
  "expected_id_start": 16,
  "expected_id_end": 186,
  "safe_pair_count": 158,
  "exception_count": 0,
  "status_counts": {
    "SAFE_MARKER_PAIR": 158,
    "APPROVED_RAW_RED_CONTENT": 13
  },
  "estimated_dirty_spot_count": 5467,
  "ground_truth_created": false,
  "safe_to_proceed_to_red_ground_truth": true
}
```

## 6. Known Risks and Notes

- The git worktree contains many untracked files and generated artifacts. Some may predate this handoff.
- `New_RawPics_birdnest_1/` is untracked but is an input/source folder. Do not casually add it to git.
- `tmp/` contains audit and preflight artifacts. Decide deliberately which artifacts should be committed, if any.
- V2 red preflight is green, but Ground Truth generation has not been implemented or run for the V2 red batch.
- V2 approval of raw red content depends on the composite provenance CSV. Do not replace this with SHA-only matching.
- The repeated SHA `dec0bfcb1c7d...` appears twice in the review resolution by design:
  - V1 ID 83 -> V2 ID 83 -> original pair 69 -> `S__10690609_0.jpg`
  - V1 ID 84 -> V2 ID 84 -> original pair 70 -> `S__10690609_1.jpg`

## 7. Git Status and Commit Guidance

Current `git status --short` shows many untracked files, including source/staging folders, docs, tools, tests, and `tmp` outputs.

High-value code/docs to consider committing:

- `docs/final_training_resolution_20260701.csv`
- `docs/final_training_resolution_20260701_v2.csv`
- `docs/red_marker_preflight_review_resolution_20260701_v2.csv`
- `docs/HANDOFF.md`
- `tools/materialize_approved_reconciliation.py`
- `tools/export_marker_review_queue.py`
- `tools/audit_unresolved_pair_integrity.py`
- `tools/materialize_final_trainable_red_batch.py`
- `tools/preflight_red_marker_batch.py`
- related tests under `tests/`

Generated artifacts to consider separately:

- `Staging_Final_Red_16_to_186_V2/`
- `Staging_Final_Red_16_to_189/`
- `New_RawPics_birdnest_1_reconciled/`
- `tmp/approved_reconciliation/`
- `tmp/final_training_red_batch/`
- `tmp/final_training_red_batch_v2/`
- `tmp/red_marker_preflight/`
- `tmp/red_marker_preflight_v2/`
- other `tmp/line_*` audit folders

Recommendation: do not make one broad commit with every untracked file. First decide whether large image folders and `tmp` outputs belong in git. A safer commit would stage only scoped code, docs, tests, and selected lightweight audit manifests/reports. Leave raw image folders and large generated staging folders out unless the repository policy explicitly wants them versioned.
