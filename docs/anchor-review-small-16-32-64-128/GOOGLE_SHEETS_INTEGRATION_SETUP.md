# Google Sheets Integration Setup

This page adds an optional Google Apps Script bridge for the Expert Review website:

`GitHub Pages review page -> Apps Script Web App -> Google Sheet`

JSON and CSV export remain available. JSON is still the trusted portable backup for Phase 8 recovery/import.

## Target Sheet

Use the prepared private Google Sheet for this review run. Do not commit its spreadsheet ID or edit URL to the public repository.

- Spreadsheet ID: paste the private target Sheet ID into `SPREADSHEET_ID` in `google-apps-script/Code.gs` while deploying Apps Script.
- Required tabs: `ReviewResults`, `ReviewSessions`, `Config`

Expected experiment identity:

- `package_id`: `package_a_small_anchor_0125`
- `model_profile`: `small_16_32_64_128`
- `checkpoint_sha256`: `e9f4d2e1b8530662fd3390165419008647c7d9baaf80e8a2d3cc4108b22fa7c0`
- `threshold`: `0.125`
- `card_count`: `1400`
- `page_count`: `70`

## Deploy Apps Script

1. Open the target Google Sheet.
2. Select `Extensions -> Apps Script`.
3. Copy `google-apps-script/Code.gs` into `Code.gs`.
4. Copy `google-apps-script/appsscript.json` into the Apps Script manifest.
5. Replace `PASTE_TARGET_SPREADSHEET_ID_HERE` in `Code.gs` with the private target spreadsheet ID.
6. Deploy with `Deploy -> New deployment -> Web app`.
7. Use these settings:
   - Execute as: `Me`
   - Who has access: `Anyone`
8. Copy the Web App `/exec` URL after deployment.

The public review page does not store Google secrets or tokens. The deployed Web App URL is not a secret; write access is controlled by the Apps Script deployment and the validation in `Code.gs`.

## Configure The Review Page

Open:

`https://suwaroj95-spec.github.io/Pics-BirdNests/anchor-review-small-16-32-64-128/`

In `ผลตรวจ / Export -> Google Sheet Sync`:

1. Paste the deployed Apps Script Web App URL.
2. Enter the reviewer name.
3. Add optional notes if useful.
4. Use `Save Progress to Google Sheet` or `Submit Final Review`.

The endpoint URL, reviewer name, notes, session ID, and sync timestamps are stored in a separate browser localStorage key ending with `:sheets:v1`. The existing review-progress localStorage key is unchanged.

## Submission Behavior

### Save Progress

`Save Progress to Google Sheet` upserts one row in `ReviewSessions`.

It does not write 1,400 rows to `ReviewResults`.

The session row includes:

- identity fields
- started/saved timestamps
- page/card counts
- reviewed pages
- accepted / false positive / pairing error / uncertain / remaining counts
- `submission_status = IN_PROGRESS`
- client version

### Submit Final Review

`Submit Final Review` writes/updates the `ReviewSessions` row and writes 1,400 rows to `ReviewResults`.

Duplicate handling is session-safe:

- If `ReviewResults` already has rows for the same `session_id`, Apps Script rejects the submit.
- The frontend then asks for explicit confirmation.
- On confirmed re-submit, Apps Script deletes prior rows for that `session_id` and rewrites the 1,400 rows.

If pages are incomplete, the frontend requires confirmation before final submission. Incomplete blank cards remain `NOT_REVIEWED`; the UI does not silently treat them as complete.

## Sheet Columns

`ReviewSessions` expected columns:

`session_id, reviewer_name, package_id, model_profile, checkpoint_sha256, threshold, manifest_identifier, started_at, last_saved_at, submitted_at, page_count, card_count, reviewed_pages, completed_cards, accepted, false_positive, pairing_error, uncertain, remaining, submission_status, client_version`

`ReviewResults` expected columns:

`session_id, reviewer_name, package_id, model_profile, checkpoint_sha256, threshold, manifest_identifier, card_id, card_index, page, position, source_id, prediction_id, score, bbox_x1, bbox_y1, bbox_x2, bbox_y2, reviewer_selection, review_status, final_classification, page_completed, page_completed_at, review_updated_at, submitted_at`

If a prepared `ReviewSessions` sheet already contains an optional `reviewer_notes` column, the Apps Script will populate it. Otherwise notes stay in the submitted payload only.

## Validation

Apps Script rejects:

- malformed JSON
- missing `session_id`
- missing `reviewer_name`
- package/model/checkpoint/threshold mismatch
- wrong `page_count` or `card_count`
- final submit with a result count other than 1,400
- unknown `final_classification`
- duplicate final submit for the same `session_id` unless `overwriteResults=true`

The `Config` sheet is read for expected values. If a value is missing there, `Code.gs` uses the fixed expected identity constants as a deployment guard.

## Manual Test Checklist

1. Open the review page.
2. Paste the Apps Script Web App URL and reviewer name.
3. Mark at least one page complete.
4. Click `Save Progress to Google Sheet`.
5. Confirm `ReviewSessions` contains or updates one row for the `session_id`.
6. Complete all 70 pages, or intentionally confirm incomplete final submit for a test session.
7. Click `Submit Final Review`.
8. Confirm `ReviewSessions.submission_status = SUBMITTED`.
9. Confirm `ReviewResults` has exactly 1,400 rows for the same `session_id`.
10. Download JSON and validate it with `tools/import_structured_expert_review_results.py`.

## Known Limitations

- GitHub Pages is static, so direct secure writes to Google Sheets are not used.
- The Web App URL is public by design; this is not strong authentication.
- Protection comes from Apps Script deployment permissions, exact experiment-identity validation, and duplicate-session safeguards.
- If Apps Script, network, or Google permissions fail, use the existing JSON export as the recovery artifact.
