# Reviewer Auth v2 Provisioning

Status: toolkit prepared only. Production reviewer tokens have not been generated.

This document describes the later human-controlled procedure for provisioning blinded reviewer access tokens for EXPERT-REVIEW-R1. Do not run this procedure until reviewer activation and launch-gate work are separately approved.

## Backend Contract

The Apps Script backend reads the Script Property named `ERV2_REVIEWER_TOKEN_MAP_JSON`.

The reviewer browser sends an opaque access token. The server hashes the exact UTF-8 token bytes with SHA-256 and looks up the lowercase hexadecimal digest in the Script Property map.

Expected map shape:

```json
{
  "0000000000000000000000000000000000000000000000000000000000000000": {
    "reviewer_id": "REV_A"
  },
  "1111111111111111111111111111111111111111111111111111111111111111": {
    "reviewer_id": "REV_B"
  }
}
```

The example above uses fake hash values only. Raw tokens must never be stored in Apps Script source, GitHub, Google Sheets, chat logs, or research artifacts.

## Toolkit

Generator:

```powershell
python tools/generate_expert_review_v2_tokens.py --output-dir <ABSOLUTE_PATH_OUTSIDE_REPO>
```

Validator:

```powershell
python tools/generate_expert_review_v2_tokens.py --output-dir <ABSOLUTE_PATH_OUTSIDE_REPO> --validate-bundle
```

The output directory must be outside `C:\copter\Pics-BirdNests`. The tool fails closed for the repository root or any child path and does not provide an override.

Private files created in the external directory:

- `REV_A_ACCESS_TOKEN.txt`
- `REV_B_ACCESS_TOKEN.txt`
- `ERV2_REVIEWER_TOKEN_MAP_JSON.txt`
- `token_provisioning_audit.json`

The raw token files contain the only raw reviewer tokens. The Script Property JSON and audit JSON contain hashes only.

The generator uses Python standard-library `secrets.token_urlsafe(32)`, providing 256 bits of cryptographic randomness before URL-safe encoding. Hashes are SHA-256 lowercase hexadecimal strings.

## Later Human Procedure

1. Choose a secure external directory outside the repository.
2. Run the generator once.
3. Store `REV_A_ACCESS_TOKEN.txt` and `REV_B_ACCESS_TOKEN.txt` securely.
4. Copy only `ERV2_REVIEWER_TOKEN_MAP_JSON.txt` into the Apps Script Script Property named `ERV2_REVIEWER_TOKEN_MAP_JSON`.
5. Give REV_A only the raw token from `REV_A_ACCESS_TOKEN.txt`.
6. Give REV_B only the raw token from `REV_B_ACCESS_TOKEN.txt`.
7. Never send both tokens to the same reviewer.
8. Never paste raw tokens into GitHub, Google Sheets, source code, chat logs, or research artifacts.
9. After provisioning, run controlled authentication smoke tests.
10. Do not activate reviewers or open the launch gate until separately approved.

## Secure Delivery Principles

- One reviewer receives one token only.
- Communicate the access URL and token separately where practical.
- Do not include reviewer role terminology.
- Do not tell REV_B that they are a reliability reviewer.
- Do not include real reviewer names or email addresses in repository files.
- Revoke and rotate any token that may have been exposed.

## Token Rotation

To rotate a compromised token:

1. Generate a replacement random token outside the repository.
2. Compute the SHA-256 hash of the replacement token.
3. Replace the old token hash entry in `ERV2_REVIEWER_TOKEN_MAP_JSON`.
4. Remove the old hash.
5. Keep the same `reviewer_id`.
6. Securely deliver only the replacement raw token to that reviewer.

No Google Sheet schema or reviewer assignment change should be required for token rotation. This toolkit does not automate live Apps Script updates.

## File Permissions

The tool attempts restrictive local file permissions using Python standard-library functionality. On POSIX systems it uses owner-only permissions. On Windows, Python `chmod` can mark files writable/readable but cannot safely author full private ACLs with the standard library alone; store the output directory in a user-private, access-controlled location.
