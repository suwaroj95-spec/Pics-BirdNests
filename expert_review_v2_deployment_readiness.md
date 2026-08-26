# Expert Review v2 Deployment Readiness Audit

Status: PASS for repository readiness. No live deployment or production mutation was performed.

Audit baseline repository HEAD before this documentation commit:

```text
7c9ff492086662b95ef5c07b9d988ac852260cee
```

## Scope

Expert Review package: `EXPERT-REVIEW-R1`

Expected scientific state:

- Reviewer cases: 1169
- REV_A assignments: 1169
- REV_B assignments: 292
- Private Drive asset inventory verified: 1169 / 1169
- Private Drive asset SHA-256 verified: 1169 / 1169
- Drive verification failures: 0
- Review launch state remains `review_start_enabled = FALSE` and `launch_gate_status = BLOCKED`
- Reviewers remain inactive
- Expert Review remains not launched

Approved source commits:

- Drive asset evidence: `8f13ad88f95aa653dd6243aaeb30d884fe71232f`
- Reviewer UI v2: `625f380afee5bb97d7e95680faaa3845717ee9b7`
- Auth provisioning toolkit: `7c9ff492086662b95ef5c07b9d988ac852260cee`

## Repository Source Findings

Approved Apps Script source files were inspected:

- `docs/anchor-review-small-16-32-64-128/google-apps-script/Code.gs`
- `docs/anchor-review-small-16-32-64-128/google-apps-script/ExpertReviewV2.gs`
- `docs/anchor-review-small-16-32-64-128/google-apps-script/ReviewerUIV2.html`
- `docs/anchor-review-small-16-32-64-128/google-apps-script/appsscript.json`

Findings:

- `Code.gs` contains the v2 routing handoff.
- Default legacy `doGet` response remains preserved when `ui=v2` is absent.
- `GET ?ui=v2` serves `ReviewerUIV2.html` through HtmlService.
- `ExpertReviewV2.gs` contains `reviewerV2Rpc(payload)` and the reviewer-facing payload sanitizer.
- `ReviewerUIV2.html` exists.
- Private reviewer image retrieval remains routed through `V2_GET_CASE_ASSET`.
- Reviewer-facing payload tests cover hiding reviewer id, role, assignment group, global review order, batch id, asset references, asset hashes, and researcher metadata.
- The UI does not use `localStorage`, `console.log`, URL token parameters, external scripts, CDNs, or external fonts.
- `appsscript.json` remains minimal: V8 runtime, no dependencies, and webapp access configured as `ANYONE`.
- The auth generator is local-only and does not call Apps Script, Google Sheets, Google Drive, Gmail, or external network services.

## Test Evidence

Command:

```powershell
C:\copter\Pics-BirdNests\.venv-cv-cuda\Scripts\python.exe -m unittest tests.test_apps_script_v2_backend tests.test_expert_review_v2_import_script tests.test_reviewer_ui_v2 tests.test_reviewer_auth_v2_provisioning tests.test_expert_review_package tests.test_reviewer_setup_v1 tests.test_reviewer_asset_delivery_v1
```

Result:

```text
Ran 61 tests in 28.249s
OK
```

## Secret Scan Findings

Tracked relevant source was scanned for raw-token assignment patterns, token-map locations, long token-shaped values, and prohibited deployment/service mutation capabilities.

Findings:

- Production raw reviewer token in repository: NO
- Assignment-style raw token entry for REV_A: not found
- Assignment-style raw token entry for REV_B: not found
- Production `ERV2_REVIEWER_TOKEN_MAP_JSON` hash map value: not found
- Long values found were expected public identifiers, frozen hashes, fake all-zero/all-one example hashes, or non-secret test/source text.
- Google Apps Script deployment secrets: not found

## Live Apps Script Reconciliation

Do not assume the live Apps Script project equals repository HEAD.

Known live history:

- Earlier approved `Code.gs` and `ExpertReviewV2.gs` were manually copied into the live Apps Script project for Drive verification.
- A temporary live helper file named `AdminVerification.gs` was manually created to log inventory/hash verification results.
- `ReviewerUIV2.html` was added to the repository later and may not exist in the live Apps Script project.

Required future reconciliation:

1. Replace live `Code.gs` with the approved repository version.
2. Replace live `ExpertReviewV2.gs` with the approved repository version.
3. Add live `ReviewerUIV2.html` from the approved repository version.
4. Preserve required legacy/import files, including `ImportV2.gs`, unless separately approved evidence requires removal.
5. Remove temporary `AdminVerification.gs` before production deployment.

`AdminVerification.gs` should be removed because it is no longer required after verification evidence has been frozen, production deployment should contain only intentional runtime/admin code, and removing the helper does not erase the repository evidence. Do not reset completed verifier Script Properties merely because this helper file is removed.

## Script Property Readiness

Do not set or modify Script Properties in this phase.

Expected existing live property:

- `ERV2_REVIEW_ASSET_FOLDER_ID`: should remain set to the private reviewer asset folder used for completed Drive verification.

Future required property:

- `ERV2_REVIEWER_TOKEN_MAP_JSON`: must remain absent until production reviewer tokens are generated in a separately approved phase.

Completed Drive verification state properties may remain. Do not reset them during predeployment cleanup.

## Reviewer Table Readiness

No live Sheets were inspected or modified in this phase.

Future activation procedure:

1. Before smoke testing, confirm REV_A `active` remains `FALSE`.
2. Before smoke testing, confirm REV_B `active` remains `FALSE`.
3. Activate reviewers only in the controlled smoke-test or launch phase after explicit approval.
4. Do not modify `ReviewResponses` or `ReviewSessionsV2` until the separately approved smoke-test/launch procedure.

If smoke testing requires active reviewers or a temporary gate mechanism, treat that as a next-phase design decision. Do not silently open production review to make smoke testing convenient.

## Deployment Security Model

Current `appsscript.json` web app configuration allows broad page access:

```json
"webapp": {
  "executeAs": "USER_DEPLOYING",
  "access": "ANYONE"
}
```

This can be acceptable for the current reviewer-token architecture only if the distinction remains strict:

- Public capability A: unauthenticated users may load the generic login page.
- Protected capability B: reviewer data and private images require valid server-side token authorization through protected RPC actions.

Repository evidence supports this model:

- The UI sends opaque tokens to `reviewerV2Rpc` via `google.script.run`, not URL parameters.
- `reviewerV2Rpc` disables browser-controlled dry-run and ignores browser-supplied reviewer identity.
- Backend identity resolution depends on `SHA256(token)` lookup in the server-side `ERV2_REVIEWER_TOKEN_MAP_JSON` Script Property.
- Protected data/image actions require successful backend authorization and launch-gate validation.
- Private images are returned only through the server-side asset layer and `V2_GET_CASE_ASSET`.

Deployment security blocker: NO.

Residual caution: if the live project contains extra helper functions, debug logging, stale files, or manually modified code not matching repository HEAD, reconcile before deployment.

## Future Deployment Plan

Phase 1: Generate production reviewer tokens outside the repository.

Phase 2: Manually set `ERV2_REVIEWER_TOKEN_MAP_JSON` with token hashes only.

Phase 3: Deploy Apps Script web app.

Phase 4: Run controlled authentication/UI smoke tests with reviewers still protected from unintended real review submission.

Phase 5: Perform final launch audit.

Phase 6: Activate reviewers and open the launch gate only after explicit approval.

## Live Change Statement

- Live Apps Script modified: NO
- Live Google Sheets written: NO
- Production reviewer tokens generated: NO
- Script Properties changed: NO
- Reviewers activated: NO
- Apps Script deployed: NO
- Launch gate changed: NO
- Review start changed: NO
- Drive verification rerun or reset: NO
