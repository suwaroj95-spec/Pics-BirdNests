# Google Sheets Integration Setup

This page adds a Google Apps Script bridge for the Expert Review website:

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

## Deploy Or Update Apps Script

1. Open the existing Apps Script project bound to the prepared Google Sheet.
2. Copy `google-apps-script/Code.gs` into `Code.gs`.
3. Copy `google-apps-script/appsscript.json` into the Apps Script manifest if it is not already present.
4. Replace `PASTE_TARGET_SPREADSHEET_ID_HERE` in `Code.gs` with the private target spreadsheet ID.
5. Save the Apps Script project.
6. Create a new Apps Script version.
7. Edit the existing Web App deployment and point it to the new version.
8. Keep the existing Web App `/exec` URL. The review frontend embeds that production endpoint.

Updating `Code.gs` in this repository does not update the already deployed Apps Script Web App. The deployed Web App is versioned; update the existing deployment to a new version so the URL/deployment ID stays the same.

The public review page does not store Google secrets or tokens. The Web App URL is public by design; write access is controlled by the Apps Script deployment, strict experiment validation, duplicate protections, and cloud-state conflict checks in `Code.gs`.

## Reviewer Workflow

Open:

`https://suwaroj95-spec.github.io/Pics-BirdNests/anchor-review-small-16-32-64-128/`

In `Export -> Google Sheet Sync`:

1. Enter the reviewer name.
2. Click `Load Cloud Progress` to recover a saved session from another browser/device.
3. Add optional notes if useful.
4. Use `Save Progress to Google Sheet` or `Submit Final Review`.

The reviewer no longer pastes the Apps Script endpoint. Reviewer name, notes, session ID, base cloud-state timestamp, and sync timestamps are stored in a separate browser localStorage key ending with `:sheets:v1`. The existing review-progress localStorage key is unchanged.

## Save Progress

`Save Progress to Google Sheet` upserts one row in `ReviewSessions`.

It does not write 1,400 rows to `ReviewResults`.

It stores a compact cloud resume state in `review_state_json`, not the full result table. The compact state contains card indexes for F/P/U plus `completedPages` timestamps:

```json
{
  "version": 1,
  "f": [3, 17],
  "p": [121],
  "u": [88],
  "completedPages": {
    "1": "2026-08-13T06:00:00.000Z"
  },
  "updatedAt": "2026-08-13T06:12:00.000Z"
}
```

The session row includes:

- identity fields
- started/saved timestamps
- page/card counts
- reviewed pages
- accepted / false positive / pairing error / uncertain / remaining counts
- `submission_status = IN_PROGRESS`
- `client_version`
- `review_state_json`
- `review_state_updated_at`
- `review_state_version`
- `reviewer_notes`

If another device has saved a newer cloud state for the same session, Apps Script rejects the save with `STALE_REVIEW_STATE`. The frontend then offers either loading the newer Google Sheet state or explicitly overwriting it with this browser's current progress.

## Load Cloud Progress

`Load Cloud Progress` uses the embedded production endpoint and reviewer name to call `LOAD_PROGRESS`.

Lookup order:

1. Exact `session_id`, if known.
2. Latest matching reviewer/package/model/checkpoint/threshold session.
3. Prefer `IN_PROGRESS` over `SUBMITTED` when both exist.
4. Sort by `review_state_updated_at` or `last_saved_at`.

The frontend never silently overwrites local progress. If local state is empty, the reviewer can restore cloud progress with one click. If local and cloud states differ, the panel shows timestamps and asks whether to use Google Sheet progress or keep this browser's progress.

When Cloud Resume loads an existing session, the frontend adopts the cloud `sessionId`. Subsequent saves continue updating the same `ReviewSessions` row.

## Submit Final Review

`Submit Final Review` writes/updates the `ReviewSessions` row and writes exactly 1,400 rows to `ReviewResults`.

Duplicate handling is session-safe:

- If `ReviewResults` already has rows for the same `session_id`, Apps Script rejects the submit.
- The frontend then asks for explicit confirmation.
- On confirmed re-submit, Apps Script deletes prior rows for that `session_id` and rewrites the 1,400 rows.

Final submit also stores the latest compact review state in `ReviewSessions`.

If pages are incomplete, the frontend requires confirmation before final submission. Incomplete blank cards remain `NOT_REVIEWED`; the UI does not silently treat them as complete.

## Sheet Columns

`ReviewSessions` expected columns:

`session_id, reviewer_name, package_id, model_profile, checkpoint_sha256, threshold, manifest_identifier, started_at, last_saved_at, submitted_at, page_count, card_count, reviewed_pages, completed_cards, accepted, false_positive, pairing_error, uncertain, remaining, submission_status, client_version, review_state_json, review_state_updated_at, review_state_version, reviewer_notes`

`ReviewResults` expected columns:

`session_id, reviewer_name, package_id, model_profile, checkpoint_sha256, threshold, manifest_identifier, card_id, card_index, page, position, source_id, prediction_id, score, bbox_x1, bbox_y1, bbox_x2, bbox_y2, reviewer_selection, review_status, final_classification, page_completed, page_completed_at, review_updated_at, submitted_at`

`ensureColumns()` adds missing required columns automatically.

## Validation

Apps Script rejects:

- malformed JSON
- missing reviewer name
- package/model/checkpoint/threshold mismatch
- wrong `page_count` or `card_count`
- compact card indexes outside `1..1400`
- final submit with a result count other than 1,400
- unknown `final_classification`
- duplicate final submit for the same `session_id` unless `overwriteResults=true`
- stale cloud-state writes unless `forceOverwriteState=true`

The `Config` sheet is read for expected values. If a value is missing there, `Code.gs` uses the fixed expected identity constants as a deployment guard.

## Manual Test Checklist

1. Open the review page.
2. Enter reviewer name.
3. Mark at least one page complete and set sample F/P/U selections.
4. Click `Save Progress to Google Sheet`.
5. Confirm `ReviewSessions` contains or updates one row for the `session_id`.
6. Confirm `review_state_json` contains compact F/P/U card indexes and completed pages.
7. In another browser/device, enter the same reviewer name and click `Load Cloud Progress`.
8. Restore the cloud session and confirm F/P/U and completed pages return.
9. Test stale-save protection by saving from one browser, then trying to save older progress from another browser.
10. Complete all 70 pages, or intentionally confirm incomplete final submit for a test session.
11. Click `Submit Final Review`.
12. Confirm `ReviewSessions.submission_status = SUBMITTED`.
13. Confirm `ReviewResults` has exactly 1,400 rows for the same `session_id`.
14. Download JSON and validate it with `tools/import_structured_expert_review_results.py`.

## Known Limitations

- GitHub Pages is static, so direct secure writes to Google Sheets are not used.
- The Web App URL is public by design; this is not strong authentication.
- The frontend can embed the public `/exec` endpoint, but the private Spreadsheet ID must remain in Apps Script only.
- If Apps Script, network, or Google permissions fail, localStorage autosave and JSON export remain the recovery paths.
