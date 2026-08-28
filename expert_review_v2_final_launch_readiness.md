# EXPERT-REVIEW-R1 Final Launch Readiness

## CURRENT_STATE

Remote baseline inspected locally: `5e6875110d2bbaf60c27ae92b701fc90f68248e8`.

The verified pre-launch state is ready for a minimal launch mutation: `1169` cases, `1461` total assignments, `1169` REV_A assignments, `292` REV_B assignments, `1169 / 1169` assets inventory-verified, `1169 / 1169` assets SHA-verified, `0` asset failures, production token map provisioned, reviewer UI v2 deployed and reachable, and production authentication smoke-tested by the researcher.

The researcher-provided final read-only checker result is treated as manually captured live execution evidence, not as an independently reproduced Codex run.

## CONTROLLED_AUTH_TEST

PASS

The manually captured controlled authentication smoke test verified:

- Invalid fake token returned `UNAUTHORIZED_REVIEWER`.
- Valid production REV_A token returned `REVIEWER_INACTIVE` while REV_A remained inactive.
- Valid production REV_B token returned `REVIEWER_INACTIVE` while REV_B remained inactive.
- No case or image was exposed in any inactive/unauthorized path.
- `ReviewResponses` and `ReviewSessionsV2` remained at `0` data rows.
- Configuration was restored to `launch_gate_status = BLOCKED` and `review_start_enabled = FALSE`.

## BACKEND_LAUNCH_CONTRACT

Production v2 requests enter `erv2Dispatch_()`, which reads the spreadsheet, required v2 sheets, `ConfigV2`, reviewer identity, assignments, cases, responses, and sessions. For non-dry-run reviewer requests, `erv2ValidateConfigV2_()` requires:

| ConfigV2 field | Required value | Backend enforcement |
| --- | --- | --- |
| `package_id` | `EXPERT-REVIEW-R1` | Exact match required |
| `reviewer_setup_status` | `REVIEWER_SETUP_FROZEN_NOT_LAUNCHED` | Exact match required |
| `review_mode` | `PRIMARY_PLUS_RELIABILITY_SUBSET` | Exact match required |
| `reviewer_setup_freeze_sha256` | `eaf492d93f0fea9f67de884bf646af5db08e6fb4ee13fc9018757c191f494dbf` | Exact match required |
| `launch_gate_status` | One of `REVIEW_LAUNCHED`, `LAUNCHED`, `OPEN` | Allow-list required |
| `review_start_enabled` | `TRUE` | Exact truthy string check required |

`erv2ResolveReviewerIdentity_()` then requires a valid reviewer token mapped by `ERV2_REVIEWER_TOKEN_MAP_JSON`, a matching reviewer row, `active = TRUE`, and `review_mode = PRIMARY_PLUS_RELIABILITY_SUBSET`.

## MINIMUM_LIVE_MUTATIONS

| Field / Sheet | Current value | Required launch value | Must change? | Reason | Backend enforcement | Rollback value |
| --- | --- | --- | --- | --- | --- | --- |
| `Reviewers.REV_A.active` | `FALSE` | `TRUE` | Yes | REV_A must pass reviewer activation after token resolution. | `erv2ResolveReviewerIdentity_()` rejects unless active reads as `TRUE`. | `FALSE` |
| `Reviewers.REV_B.active` | `FALSE` | `TRUE` | Yes | REV_B must pass reviewer activation after token resolution. | `erv2ResolveReviewerIdentity_()` rejects unless active reads as `TRUE`. | `FALSE` |
| `ConfigV2.launch_gate_status` | `BLOCKED` | `REVIEW_LAUNCHED` | Yes | Production request must pass launch status allow-list. | `erv2ValidateConfigV2_()` allows `REVIEW_LAUNCHED`, `LAUNCHED`, or `OPEN`. Use `REVIEW_LAUNCHED` for the controlled launch value. | `BLOCKED` |
| `ConfigV2.review_start_enabled` | `FALSE` | `TRUE` | Yes | This is the final launch switch. | `erv2ValidateConfigV2_()` rejects unless `String(value).toUpperCase() === "TRUE"`. | `FALSE` |

No other live sheet, Script Property, Drive, assignment, response, session, deployment, or token mutation is required for launch.

## VALUES_THAT_MUST_REMAIN_FROZEN

| Field | Required unchanged value | Reason |
| --- | --- | --- |
| `ConfigV2.package_id` | `EXPERT-REVIEW-R1` | Backend exact-match invariant. |
| `ConfigV2.reviewer_setup_status` | `REVIEWER_SETUP_FROZEN_NOT_LAUNCHED` | Backend exact-match invariant, despite the name sounding pre-launch-specific. |
| `ConfigV2.review_mode` | `PRIMARY_PLUS_RELIABILITY_SUBSET` | Backend exact-match invariant and reviewer row mode check. |
| `ConfigV2.reviewer_setup_freeze_sha256` | `eaf492d93f0fea9f67de884bf646af5db08e6fb4ee13fc9018757c191f494dbf` | Backend exact-match invariant. |
| `ERV2_REVIEWER_TOKEN_MAP_JSON` | Provisioned two-entry map | Required for auth; do not print, rotate, or rewrite for launch. |
| `ERV2_REVIEW_ASSET_FOLDER_ID` | Existing production folder binding | Required for private asset delivery; do not print or rewrite for launch. |
| `ReviewAssignments` | `1461` rows: `1169` REV_A and `292` REV_B | Assignment set is already frozen; launch does not require mutation. |

## DOCUMENTATION_ONLY_OR_NOT_ENFORCED

These values are not read by `erv2ValidateConfigV2_()` in the current backend launch path and should not be changed merely for semantics:

| Field | Current value | Launch action |
| --- | --- | --- |
| `package_status` | `PACKAGE_READY_NOT_STARTED` | Leave unchanged unless a separate documentation process explicitly owns it. |
| `apps_script_migration_status` | `NOT_STARTED` or prior setup patch value | Leave unchanged; not enforced by the reviewer backend launch gate. |

## SAFE_LAUNCH_ORDER

The safest order is:

1. Keep `ConfigV2.launch_gate_status = BLOCKED`.
2. Keep `ConfigV2.review_start_enabled = FALSE`.
3. Set `Reviewers.REV_A.active = TRUE`.
4. Set `Reviewers.REV_B.active = TRUE`.
5. Verify `ReviewResponses = 0` data rows and `ReviewSessionsV2 = 0` data rows.
6. Set `ConfigV2.launch_gate_status = REVIEW_LAUNCHED`.
7. Set `ConfigV2.review_start_enabled = TRUE` as the final launch action.

This ordering is safe against the current backend because active reviewers still cannot bootstrap, load progress, fetch assets, save drafts, or submit responses while either the launch gate remains blocked or `review_start_enabled` remains false. There is no point in this order where an unexpected reviewer can perform review work: token mapping is still required, reviewer rows must exist, reviewer mode must match, and assignments are filtered to the resolved reviewer.

## ROLLBACK_ORDER

Fastest safe rollback:

1. Set `ConfigV2.review_start_enabled = FALSE`.
2. Set `ConfigV2.launch_gate_status = BLOCKED`.
3. If reviewer access must also be disabled, set `Reviewers.REV_A.active = FALSE`.
4. If reviewer access must also be disabled, set `Reviewers.REV_B.active = FALSE`.

Rollback must not delete responses, delete sessions, modify assignments, rotate tokens unless compromised, reset Drive verification, or delete reviewer data. Submitted responses remain protected by `RESPONSE_ALREADY_SUBMITTED` handling and must be preserved.

## POST_LAUNCH_SMOKE_TEST

Use the reviewer UI / reviewer RPC with production tokens only after the launch switch is complete:

1. Authenticate with the REV_A production token.
2. Confirm bootstrap succeeds and `assigned_count = 1169`.
3. Confirm returned reviewer-facing case metadata contains only minimal case identity and definition version.
4. Load only the first assigned REV_A image through `V2_GET_CASE_ASSET`.
5. Do not save draft and do not submit response.
6. Authenticate with the REV_B production token.
7. Confirm bootstrap succeeds and `assigned_count = 292`.
8. Confirm returned reviewer-facing case metadata contains only minimal case identity and definition version.
9. Load only the first assigned REV_B image through `V2_GET_CASE_ASSET`.
10. Do not save draft and do not submit response.
11. Confirm `ReviewResponses` remains at `0` data rows.
12. Confirm `ReviewSessionsV2` remains at `0` data rows.

Reviewer-facing payloads must not reveal `reviewer_id`, `reviewer_role`, `assignment_group`, global `review_order`, `batch_id`, `stratum`, E22 class, prediction score, bounding boxes, `ResearcherCaseMeta`, asset SHA, Drive ID, or Drive URL. The deployed reviewer RPC wrapper strips reviewer identity internals and uses reviewer-local positions for progress.

Simple authentication/bootstrap, load-progress, and first-image load are expected not to create a `ReviewSessionsV2` row in the current backend. Session rows are written only by save-draft or submit-response paths.

## REVIEW_SESSION_SIDE_EFFECT_ANALYSIS

| Operation | Writes `ReviewSessionsV2` | Writes `ReviewResponses` | Writes `ReviewAssignments` | Writes `ReviewCases` | Notes |
| --- | --- | --- | --- | --- | --- |
| `V2_GET_BOOTSTRAP` | No | No | No | No | Reads sessions/responses to compute counts and current case. |
| `V2_LOAD_PROGRESS` | No | No | No | No | Reads assignments/responses/sessions and returns reviewer-facing progress. |
| `V2_GET_CASE_ASSET` | No | No | No | No | Reads assignment, case row, Drive file, MIME type, bytes, and SHA; returns image bytes without sheet writes. |
| `V2_SAVE_DRAFT` | Yes | Yes | No in reviewer RPC | No | Writes draft response and session. Assignment transition only occurs if internal `enableAssignmentTransitions` option is true. |
| `V2_SUBMIT_RESPONSE` | Yes | Yes | No in reviewer RPC | No | Writes submitted response and session; submitted content is idempotent only when identical. |

## BOOTSTRAP_WRITES_SESSION

NO

## LOAD_PROGRESS_WRITES_SESSION

NO

## GET_CASE_ASSET_WRITES_SESSION

NO

## GET_CASE_ASSET_WRITES_RESPONSE

NO

## FINAL_LAUNCH_BLOCKERS

None found in source for the no-submit launch plan. Do not launch until the human checklist is complete and the temporary predeployment checker has been removed from the live Apps Script editor.
