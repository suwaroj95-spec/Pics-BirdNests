# Apps Script v2 Asset Layer Readiness

ASSET_LAYER_STATUS: PASS

This scoped extension adds a private Google Drive reviewer-asset verification and serving layer to the isolated Expert Review v2 backend. It does not deploy, does not start Expert Review, does not activate reviewers, and does not write review labels.

## Folder Configuration Strategy

Production Drive folder lookup is server-side only through Script Properties:

- `ERV2_REVIEW_ASSET_FOLDER_ID`

The expected later configured value is not hardcoded in source code. Missing configuration fails closed with `ASSET_FOLDER_NOT_CONFIGURED`.

Expected folder name is checked server-side:

- `EXPERT-REVIEW-R1_ReviewerAssets_Private`

Wrong folder identity fails closed with `ASSET_FOLDER_NAME_MISMATCH`.

## Inventory Verification Strategy

Added admin/editor function:

- `verifyExpertReviewV2DriveAssetInventory()`

This is not a reviewer-facing endpoint. It verifies:

- expected frozen cases = 1169
- Drive folder file count = 1169
- exact folder name
- exact filename identity `<case_id>.jpg`
- no missing files
- no unexpected files
- no duplicate filenames
- acceptable JPEG MIME

It returns a structured result and performs no Google Sheet mutation.

## Full SHA Batch Strategy

Added resumable admin/editor functions:

- `verifyExpertReviewV2DriveAssetHashesBatch()`
- `resetExpertReviewV2DriveAssetVerification()`

The batch verifier uses conservative batches of 75 cases per invocation. It persists only cursor/count progress in Script Properties:

- `ERV2_ASSET_VERIFY_CURSOR`
- `ERV2_ASSET_VERIFY_PASS_COUNT`
- `ERV2_ASSET_VERIFY_FAIL_COUNT`
- `ERV2_ASSET_VERIFY_MISMATCH_COUNT`
- `ERV2_ASSET_VERIFY_MISSING_COUNT`
- `ERV2_ASSET_VERIFY_DUPLICATE_COUNT`
- `ERV2_ASSET_VERIFY_INVALID_MIME_COUNT`
- `ERV2_ASSET_VERIFY_INTERNAL_ERROR_COUNT`
- `ERV2_ASSET_VERIFY_FOLDER_ID`
- `ERV2_ASSET_VERIFY_STARTED_AT`

It does not store a full 1169-file map in Script Properties.

Each checked case derives `case_id + ".jpg"`, requires exactly one Drive match, hashes the blob bytes with SHA-256, and compares against `ReviewCases.asset_sha256`.

The hash batch verifier is protected by Script Lock across cursor/counter reads, batch processing, and cursor/counter writes. Verification progress is bound to the first configured folder ID via `ERV2_ASSET_VERIFY_FOLDER_ID`; a later folder change fails closed with `ASSET_VERIFICATION_STATE_MISMATCH` until the admin reset function clears verifier state.

Final states are explicit:

- `DRIVE_ASSET_FULL_SHA256_VERIFIED` when all 1169 files are processed and cumulative failures are zero.
- `DRIVE_ASSET_FULL_SHA256_FAILED` when all 1169 files are processed and any cumulative failure exists.
- `DRIVE_ASSET_SHA256_BATCH_IN_PROGRESS` while cases remain.

Failure category fields are cumulative. Per-invocation diagnostic failures are returned as `batch_failures`.

## Asset-Serving Flow

Added reviewer action:

- `V2_GET_CASE_ASSET`

Flow:

1. v2 launch/config gate
2. server-side reviewer identity resolution
3. reviewer active/mode validation
4. exact assignment validation
5. exact private Drive filename lookup
6. JPEG MIME validation
7. per-request SHA-256 verification against `ReviewCases.asset_sha256`
8. base64 image-byte response

The action loads one requested case image per call. Bootstrap remains metadata-only and does not preload images.

## Authorization Ordering

Reviewer identity is resolved through the existing server-side token-hash architecture. The browser-supplied `reviewer_id` is not trusted.

Assignment is checked before Drive lookup. Tests verify an unassigned request returns `CASE_NOT_ASSIGNED` before a Drive file lookup occurs.

## Privacy Guarantees

Reviewer asset responses include only:

- `case_id`
- `mime_type`
- `data_base64`

Reviewer responses do not include:

- Drive folder ID
- Drive file ID
- Drive URL
- webViewLink
- asset SHA
- source asset ref
- local path
- ResearcherCaseMeta
- prediction score
- bbox
- stratum
- E22 classification

The reviewer-safe bootstrap/load case payload was tightened to exclude `asset_sha256` and `review_asset_ref`.

Reviewers are not granted access to the Drive folder. Apps Script uses server-side Drive access and returns only authorized case image bytes.

No Drive sharing permissions are changed by code.

## Per-Request Hash Verification

`V2_GET_CASE_ASSET` computes SHA-256 over the Drive blob bytes before returning image data. A mismatch fails closed with `ASSET_INTEGRITY_MISMATCH`.

This check remains present even though a full admin batch verifier also exists.

## Performance Approach

Reviewer asset retrieval is lazy and one-image-per-request.

The full 1169-file SHA verification is split into resumable batches to avoid unsafe monolithic Apps Script execution.

## Tests

Command:

```text
python -m unittest tests.test_apps_script_v2_backend tests.test_expert_review_v2_import_script
```

Result:

```text
Ran 15 tests
OK
```

The extended local harness uses fake Spreadsheet, Drive folder/file/blob, and Script Properties objects. It does not access live Google Drive.

Covered checks include:

- missing folder property fails closed
- expected private folder identity accepted
- wrong folder identity rejected
- exact case filename resolves
- missing asset rejected
- duplicate filename rejected
- invalid MIME rejected
- hash mismatch rejected
- hash match accepted
- unassigned reviewer rejected before asset read
- REV_A can access A-assigned mocked case
- REV_B can access B-assigned mocked case
- Drive file ID not exposed
- Drive URL not exposed
- folder ID not exposed
- asset SHA not exposed
- ResearcherCaseMeta not exposed
- blocked launch state prevents production asset action
- inventory verifier detects missing/extra/duplicate
- batch hash verification is resumable
- cumulative hash failure counters survive later batches
- final success and failure states are unambiguous
- hash batch progress is Script Lock protected
- folder identity changes during verification fail closed
- reset clears cursor, counters, timestamps, and folder identity
- legacy v1 behavior remains unchanged
- existing v2 backend tests continue passing

## Remaining Blockers

- Do not run the live Drive inventory verifier until ChatGPT reviews this report.
- Do not run the live full SHA batch verifier until inventory verification is approved.
- `ERV2_REVIEW_ASSET_FOLDER_ID` still must be configured in Script Properties before real Drive verification.
- Production reviewer auth tokens still must be provisioned securely.
- Reviewers remain inactive.
- `launch_gate_status` remains expected to be `BLOCKED`.
- `review_start_enabled` remains expected to be `FALSE`.
- No deployment has occurred.

## Final Checklist

ASSET_LAYER_STATUS: PASS

FILES_CHANGED:

- `docs/anchor-review-small-16-32-64-128/google-apps-script/ExpertReviewV2.gs`
- `tests/apps_script_v2_backend_harness.js`
- `tests/test_apps_script_v2_backend.py`
- `apps_script_v2_asset_layer_readiness.md`

INVENTORY_VERIFIER: YES

EXPECTED_DRIVE_FILES: 1169

FULL_SHA_BATCH_VERIFIER: YES

ASSET_ACTION: V2_GET_CASE_ASSET

AUTH_BEFORE_DRIVE_ACCESS: PASS

ASSIGNMENT_BEFORE_DRIVE_ACCESS: PASS

PER_REQUEST_SHA_CHECK: PASS

DRIVE_IDS_EXPOSED: NO

DRIVE_URLS_EXPOSED: NO

RESEARCHER_METADATA_EXPOSED: NO

LIVE_DRIVE_WRITES: NO

LIVE_SHEET_WRITES: NO

LAUNCH_GATE_CHANGED: NO

REVIEW_START_CHANGED: NO

REVIEWERS_ACTIVATED: NO

REVIEW_LABELS_WRITTEN: NO

DEPLOYED: NO

TESTS:

- `python -m unittest tests.test_apps_script_v2_backend tests.test_expert_review_v2_import_script`
- PASS, 15 tests

REMAINING_BLOCKERS:

- ChatGPT review of this report
- Script Property `ERV2_REVIEW_ASSET_FOLDER_ID`
- approved live inventory verifier run
- approved resumable live SHA verifier run
- production reviewer auth provisioning
- reviewer UI v2
- deployment and launch-gate review
