# EXPERT-REVIEW-R1 Controlled Authentication Smoke Test Evidence

Evidence source: `MANUALLY_CAPTURED_LIVE_TEST`

This file freezes the researcher's manually captured live authentication smoke test from 2026-08-27. Codex did not independently reproduce this live execution and did not use production raw tokens.

## Initial State

- `REV_A.active`: `FALSE`
- `REV_B.active`: `FALSE`
- `ConfigV2.launch_gate_status`: `BLOCKED`
- `ConfigV2.review_start_enabled`: `FALSE`
- `ReviewResponses` data rows: `0`
- `ReviewSessionsV2` data rows: `0`

## Temporary Test Window

The researcher temporarily set:

- `ConfigV2.launch_gate_status`: `REVIEW_LAUNCHED`
- `ConfigV2.review_start_enabled`: `TRUE`

Both reviewers remained inactive throughout this test window.

## Observed Results

| Test input | Result | Reviewer-facing message | Case exposed | Image exposed |
| --- | --- | --- | --- | --- |
| Invalid fake token | `UNAUTHORIZED_REVIEWER` | `รหัสเข้าใช้งานไม่ถูกต้อง` | No | No |
| Valid production REV_A token | `REVIEWER_INACTIVE` | `บัญชีผู้ประเมินยังไม่เปิดใช้งาน` | No | No |
| Valid production REV_B token | `REVIEWER_INACTIVE` | `บัญชีผู้ประเมินยังไม่เปิดใช้งาน` | No | No |

No raw token, token hash, Drive ID, Drive URL, case detail, comment, or response content is included in this artifact.

## Restored State

- `ReviewResponses` data rows: `0`
- `ReviewSessionsV2` data rows: `0`
- `ConfigV2.launch_gate_status`: `BLOCKED`
- `ConfigV2.review_start_enabled`: `FALSE`
- `REV_A.active`: `FALSE`
- `REV_B.active`: `FALSE`

The researcher reran the read-only predeployment safety checker after restoring the state. The manually captured final result was `PREDEPLOYMENT_SAFETY_VERIFIED` with `ok: true`.

Expert review started: `false`
