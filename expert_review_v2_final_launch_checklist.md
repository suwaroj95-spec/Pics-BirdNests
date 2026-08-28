# EXPERT-REVIEW-R1 Final Launch Checklist

This checklist is sequential. Do not deploy, rotate tokens, delete rows, change assignments, reset Drive verification, or submit a scientific response as part of launch verification.

## Pre-Launch Verification

- [ ] GitHub HEAD verified as `5e6875110d2bbaf60c27ae92b701fc90f68248e8`.
- [ ] Production Web App URL recorded.
- [ ] `PredeploymentSafetyCheck.gs` removed from the live Apps Script editor.
- [ ] Production Script Property `ERV2_REVIEWER_TOKEN_MAP_JSON` exists.
- [ ] Production Script Property `ERV2_REVIEW_ASSET_FOLDER_ID` exists.
- [ ] Private asset folder remains private.
- [ ] Asset inventory remains `1169 / 1169` verified.
- [ ] Asset SHA-256 verification remains `1169 / 1169` verified with `0` failures.
- [ ] `ReviewResponses` has `0` data rows.
- [ ] `ReviewSessionsV2` has `0` data rows.
- [ ] `Reviewers.REV_A.active` is `FALSE`.
- [ ] `Reviewers.REV_B.active` is `FALSE`.
- [ ] `ConfigV2.launch_gate_status` is `BLOCKED`.
- [ ] `ConfigV2.review_start_enabled` is `FALSE`.
- [ ] `ConfigV2.package_id` remains `EXPERT-REVIEW-R1`.
- [ ] `ConfigV2.reviewer_setup_status` remains `REVIEWER_SETUP_FROZEN_NOT_LAUNCHED`.
- [ ] `ConfigV2.review_mode` remains `PRIMARY_PLUS_RELIABILITY_SUBSET`.
- [ ] `ConfigV2.reviewer_setup_freeze_sha256` remains `eaf492d93f0fea9f67de884bf646af5db08e6fb4ee13fc9018757c191f494dbf`.

## Launch Actions

- [ ] Keep `ConfigV2.launch_gate_status` at `BLOCKED`.
- [ ] Keep `ConfigV2.review_start_enabled` at `FALSE`.
- [ ] Set `Reviewers.REV_A.active` to `TRUE`.
- [ ] Set `Reviewers.REV_B.active` to `TRUE`.
- [ ] Verify `ReviewResponses` still has `0` data rows.
- [ ] Verify `ReviewSessionsV2` still has `0` data rows.
- [ ] Set `ConfigV2.launch_gate_status` to `REVIEW_LAUNCHED`.
- [ ] Set `ConfigV2.review_start_enabled` to `TRUE` as the final launch action.
- [ ] Record launch timestamp and operator outside the live review sheets if needed.

## Post-Launch No-Submit Smoke Test

- [ ] Using the production REV_A token, open the reviewer UI and authenticate.
- [ ] Confirm REV_A bootstrap succeeds.
- [ ] Confirm REV_A `assigned_count` is `1169`.
- [ ] Confirm REV_A first assigned case metadata is minimal and reviewer-facing.
- [ ] Load only the first REV_A assigned image.
- [ ] Do not save draft.
- [ ] Do not submit response.
- [ ] Using the production REV_B token, open the reviewer UI and authenticate.
- [ ] Confirm REV_B bootstrap succeeds.
- [ ] Confirm REV_B `assigned_count` is `292`.
- [ ] Confirm REV_B first assigned case metadata is minimal and reviewer-facing.
- [ ] Load only the first REV_B assigned image.
- [ ] Do not save draft.
- [ ] Do not submit response.
- [ ] Confirm reviewer-facing payloads do not expose reviewer identity internals, global order, batch IDs, researcher metadata, model details, asset hashes, Drive IDs, or Drive URLs.
- [ ] Confirm `ReviewResponses` still has `0` data rows.
- [ ] Confirm `ReviewSessionsV2` still has `0` data rows.

## Emergency Rollback

- [ ] Set `ConfigV2.review_start_enabled` to `FALSE`.
- [ ] Set `ConfigV2.launch_gate_status` to `BLOCKED`.
- [ ] If reviewer access must also be disabled, set `Reviewers.REV_A.active` to `FALSE`.
- [ ] If reviewer access must also be disabled, set `Reviewers.REV_B.active` to `FALSE`.
- [ ] Do not delete responses.
- [ ] Do not delete sessions.
- [ ] Do not modify assignments.
- [ ] Do not rotate tokens unless a token compromise is suspected.
- [ ] Do not reset Drive verification.
- [ ] Preserve submitted responses as immutable records.
