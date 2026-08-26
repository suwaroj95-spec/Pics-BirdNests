# Expert Review v2 Predeployment Checklist

Use this checklist during the future controlled deployment window. Leave items unchecked until a human operator has performed or verified each step in the live environment.

## Repository And Local Gates

- [ ] Repository HEAD confirmed as the approved deployment source.
- [ ] All scoped Expert Review v2 tests PASS.
- [ ] Commit history includes Drive asset evidence, Reviewer UI v2, and auth provisioning toolkit commits.
- [ ] No production raw reviewer token exists in the repository.
- [ ] No production token hash map has been committed as `ERV2_REVIEWER_TOKEN_MAP_JSON`.

## Live Apps Script Reconciliation

- [ ] Live `Code.gs` replaced from approved repository source.
- [ ] Live `ExpertReviewV2.gs` replaced from approved repository source.
- [ ] `ReviewerUIV2.html` added to the live Apps Script project from approved repository source.
- [ ] Temporary `AdminVerification.gs` removed before production deployment.
- [ ] `ImportV2.gs` preserved unless a separate approved change explicitly requires otherwise.
- [ ] `appsscript.json` reviewed and unchanged unless separately approved.
- [ ] No unreviewed helper, debug, or verification-only runtime file remains in the live project.

## Script Properties

- [ ] `ERV2_REVIEW_ASSET_FOLDER_ID` is still set to the private reviewer asset folder.
- [ ] Private Drive asset verification state properties are not reset merely because helper code is removed.
- [ ] `ERV2_REVIEWER_TOKEN_MAP_JSON` remains absent until production tokens are generated in a separately approved phase.
- [ ] No raw reviewer token is present in any Script Property.

## Live Data And Launch Gates

- [ ] Drive asset folder remains private.
- [ ] REV_A inactive.
- [ ] REV_B inactive.
- [ ] `ReviewResponses` empty.
- [ ] `ReviewSessionsV2` empty.
- [ ] `launch_gate_status` is `BLOCKED`.
- [ ] `review_start_enabled` is `FALSE`.
- [ ] No deployment performed yet.

## Future Deployment Phases

- [ ] Phase 1: generate production reviewer tokens outside the repository.
- [ ] Phase 2: manually set `ERV2_REVIEWER_TOKEN_MAP_JSON` using hashes only.
- [ ] Phase 3: deploy the Apps Script web app.
- [ ] Phase 4: run controlled authentication and UI smoke tests.
- [ ] Phase 5: perform final launch audit.
- [ ] Phase 6: activate reviewers and open launch gate only after explicit approval.
