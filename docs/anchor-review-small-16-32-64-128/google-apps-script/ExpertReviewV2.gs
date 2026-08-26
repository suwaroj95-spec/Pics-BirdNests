/**
 * Backend-only Apps Script v2 support for EXPERT-REVIEW-R1.
 *
 * This file is intentionally isolated from the legacy ReviewSessions/ReviewResults
 * bridge in Code.gs. Production reviewer identity is resolved from a server-side
 * Script Property token-hash map and fails closed when that mapping is absent.
 */
const ERV2_BACKEND_CONFIG = Object.freeze({
  spreadsheetId: "1c5QYrz8CJymAO3LAu8szYnBoubnoT82dPQkf0UJRGTg",
  packageId: "EXPERT-REVIEW-R1",
  reviewerSetupStatus: "REVIEWER_SETUP_FROZEN_NOT_LAUNCHED",
  reviewMode: "PRIMARY_PLUS_RELIABILITY_SUBSET",
  reviewerSetupFreezeSha256: "eaf492d93f0fea9f67de884bf646af5db08e6fb4ee13fc9018757c191f494dbf",
  tokenMapProperty: "ERV2_REVIEWER_TOKEN_MAP_JSON",
  assetFolderProperty: "ERV2_REVIEW_ASSET_FOLDER_ID",
  expectedAssetFolderName: "EXPERT-REVIEW-R1_ReviewerAssets_Private",
  expectedAssetCount: 1169,
  assetHashBatchSize: 75,
  launchAllowedStatuses: Object.freeze({ REVIEW_LAUNCHED: true, LAUNCHED: true, OPEN: true }),
  dryRunAllowedStatuses: Object.freeze({ BLOCKED: true, REVIEW_BLOCKED: true, REVIEW_DRY_RUN: true }),
  lockTimeoutMs: 30000,
});

const ERV2_ACTIONS = Object.freeze({
  V2_GET_BOOTSTRAP: true,
  V2_LOAD_PROGRESS: true,
  V2_SAVE_DRAFT: true,
  V2_SUBMIT_RESPONSE: true,
  V2_GET_CASE_ASSET: true,
});

const ERV2_SHEETS = Object.freeze({
  cases: "ReviewCases",
  assignments: "ReviewAssignments",
  responses: "ReviewResponses",
  sessions: "ReviewSessionsV2",
  reviewers: "Reviewers",
  config: "ConfigV2",
});

const ERV2_HEADERS = Object.freeze({
  ReviewCases: Object.freeze([
    "case_id", "case_index", "batch_id", "batch_position", "review_order",
    "review_asset_ref", "asset_sha256", "package_id", "case_status",
    "definition_version", "assigned_reviewer_count", "response_count",
    "created_at", "imported_at", "notes",
  ]),
  ReviewAssignments: Object.freeze([
    "assignment_id", "case_id", "reviewer_id", "reviewer_role",
    "assignment_group", "batch_id", "review_order", "required",
    "assigned_at", "assignment_status", "completed_at", "notes",
  ]),
  ReviewResponses: Object.freeze([
    "response_id", "case_id", "reviewer_id", "decision", "confidence",
    "comment", "response_status", "started_at", "last_saved_at",
    "submitted_at", "response_version", "session_id", "client_version",
    "protocol_deviation_id", "row_hash",
  ]),
  ReviewSessionsV2: Object.freeze([
    "session_id", "reviewer_id", "reviewer_role", "session_status",
    "current_case_id", "current_batch_id", "assigned_count",
    "completed_count", "remaining_count", "started_at", "last_saved_at",
    "submitted_at", "state_version", "state_json", "client_version",
    "base_state_updated_at", "reviewer_notes", "server_notes",
  ]),
  Reviewers: Object.freeze([
    "reviewer_id", "display_name", "reviewer_role", "active",
    "review_mode", "assignment_group", "created_at", "notes",
  ]),
});

const ERV2_DECISIONS = Object.freeze({
  CONFIRMED_DIRTY_SPOT: true,
  NOT_DIRTY_SPOT: true,
  AMBIGUOUS: true,
  UNJUDGEABLE: true,
  ANNOTATION_LOCALIZATION_ISSUE: true,
});

const ERV2_CONFIDENCE = Object.freeze({ HIGH: true, MEDIUM: true, LOW: true });
const ERV2_FORBIDDEN_REVIEWER_FIELDS = Object.freeze([
  "stratum", "e22_classification", "prediction_score", "bbox_x1", "bbox_y1",
  "bbox_x2", "bbox_y2", "source_id", "tile_id", "researcher_notes",
  "prediction_id", "gt_id", "size_quartile", "match_metric", "match_value",
  "assigned_reviewer_count", "response_count", "notes", "asset_sha256",
  "review_asset_ref",
]);

const ERV2_ASSET_VERIFY_PROPERTIES = Object.freeze({
  cursor: "ERV2_ASSET_VERIFY_CURSOR",
  passCount: "ERV2_ASSET_VERIFY_PASS_COUNT",
  failCount: "ERV2_ASSET_VERIFY_FAIL_COUNT",
  startedAt: "ERV2_ASSET_VERIFY_STARTED_AT",
});

function isExpertReviewV2Action_(action) {
  return Boolean(ERV2_ACTIONS[String(action || "")]);
}

function handleExpertReviewV2Post(payload, options) {
  try {
    if (!payload || typeof payload !== "object") throw erv2Error_("INVALID_PAYLOAD", "Payload must be an object.");
    if (!isExpertReviewV2Action_(payload.action)) throw erv2Error_("INTERNAL_ERROR", "Unsupported v2 action.");

    const action = String(payload.action);
    if (action === "V2_SAVE_DRAFT" || action === "V2_SUBMIT_RESPONSE") {
      return erv2WithScriptLock_(function() {
        return erv2Dispatch_(payload, options || {});
      }, options || {});
    }
    return erv2Dispatch_(payload, options || {});
  } catch (error) {
    return erv2Failure_(error);
  }
}

function erv2Dispatch_(payload, options) {
  const dryRun = Boolean(payload.dryRun && options.allowDryRun);
  const spreadsheet = options.spreadsheet || SpreadsheetApp.openById(ERV2_BACKEND_CONFIG.spreadsheetId);
  const sheets = erv2ReadRequiredSheets_(spreadsheet);
  const config = erv2ReadConfigV2_(sheets.config.sheet);
  erv2ValidateConfigV2_(config, dryRun);

  const reviewer = erv2ResolveReviewerIdentity_(payload, sheets.reviewers.sheet, options);
  const assignments = erv2OwnAssignments_(sheets.assignments.sheet, reviewer);
  const casesById = erv2RowsByKey_(erv2ReadRows_(sheets.cases.sheet, sheets.cases.header), "case_id");
  const responses = erv2OwnResponses_(sheets.responses.sheet, reviewer);
  const sessions = erv2OwnSessions_(sheets.sessions.sheet, reviewer);

  if (payload.action === "V2_GET_BOOTSTRAP") {
    return erv2Bootstrap_(reviewer, assignments, casesById, responses, sessions);
  }
  if (payload.action === "V2_LOAD_PROGRESS") {
    return erv2LoadProgress_(payload, reviewer, assignments, casesById, responses, sessions);
  }
  if (payload.action === "V2_SAVE_DRAFT") {
    return erv2SaveDraft_(payload, reviewer, assignments, casesById, responses, sessions, sheets, options);
  }
  if (payload.action === "V2_SUBMIT_RESPONSE") {
    return erv2SubmitResponse_(payload, reviewer, assignments, casesById, responses, sessions, sheets, options);
  }
  if (payload.action === "V2_GET_CASE_ASSET") {
    return erv2GetCaseAsset_(payload, reviewer, assignments, casesById, options);
  }
  throw erv2Error_("INTERNAL_ERROR", "Unsupported v2 action.");
}

function verifyExpertReviewV2DriveAssetInventory() {
  return erv2VerifyDriveAssetInventory_({});
}

function verifyExpertReviewV2DriveAssetHashesBatch() {
  return erv2VerifyDriveAssetHashesBatch_({});
}

function resetExpertReviewV2DriveAssetVerification() {
  const props = erv2ScriptProperties_();
  Object.keys(ERV2_ASSET_VERIFY_PROPERTIES).forEach(function(key) {
    props.deleteProperty(ERV2_ASSET_VERIFY_PROPERTIES[key]);
  });
  return {
    ok: true,
    status: "DRIVE_ASSET_VERIFICATION_RESET",
    properties_cleared: Object.keys(ERV2_ASSET_VERIFY_PROPERTIES).length,
  };
}

function erv2VerifyDriveAssetInventory_(options) {
  try {
    const spreadsheet = (options && options.spreadsheet) || SpreadsheetApp.openById(ERV2_BACKEND_CONFIG.spreadsheetId);
    const sheets = erv2ReadRequiredSheets_(spreadsheet);
    const cases = erv2ExpectedCaseRows_(sheets.cases.sheet);
    const folder = erv2OpenAssetFolder_(options || {});
    const inventory = erv2DriveFolderInventory_(folder);
    const expectedByFilename = {};
    cases.forEach(function(row) {
      expectedByFilename[erv2AssetFilename_(row.case_id)] = true;
    });

    const missing = [];
    Object.keys(expectedByFilename).forEach(function(filename) {
      if (!inventory.filesByName[filename]) missing.push(filename);
    });
    const extra = inventory.files.filter(function(file) {
      return !expectedByFilename[file.name];
    }).map(function(file) { return file.name; });
    const duplicateCount = Object.keys(inventory.duplicateNames).length;
    const invalidMimeCount = inventory.files.filter(function(file) {
      return !erv2IsJpegMime_(file.mimeType);
    }).length;

    const ok = cases.length === ERV2_BACKEND_CONFIG.expectedAssetCount &&
      inventory.files.length === ERV2_BACKEND_CONFIG.expectedAssetCount &&
      missing.length === 0 &&
      extra.length === 0 &&
      duplicateCount === 0 &&
      invalidMimeCount === 0;

    return {
      ok: ok,
      status: ok ? "DRIVE_ASSET_INVENTORY_VERIFIED" : "DRIVE_ASSET_INVENTORY_FAILED",
      expected_cases: cases.length,
      drive_files: inventory.files.length,
      matched: ERV2_BACKEND_CONFIG.expectedAssetCount - missing.length,
      missing: missing.length,
      extra: extra.length,
      duplicates: duplicateCount,
      invalid_mime: invalidMimeCount,
    };
  } catch (error) {
    return erv2Failure_(error);
  }
}

function erv2VerifyDriveAssetHashesBatch_(options) {
  try {
    const spreadsheet = (options && options.spreadsheet) || SpreadsheetApp.openById(ERV2_BACKEND_CONFIG.spreadsheetId);
    const sheets = erv2ReadRequiredSheets_(spreadsheet);
    const cases = erv2ExpectedCaseRows_(sheets.cases.sheet);
    const folder = erv2OpenAssetFolder_(options || {});
    const props = (options && options.properties) || erv2ScriptProperties_();
    const cursor = Number(props.getProperty(ERV2_ASSET_VERIFY_PROPERTIES.cursor) || 0);
    const startedAt = props.getProperty(ERV2_ASSET_VERIFY_PROPERTIES.startedAt) || erv2NowIso_();
    if (!props.getProperty(ERV2_ASSET_VERIFY_PROPERTIES.startedAt)) {
      props.setProperty(ERV2_ASSET_VERIFY_PROPERTIES.startedAt, startedAt);
    }

    const batchSize = Number((options && options.batchSize) || ERV2_BACKEND_CONFIG.assetHashBatchSize);
    const end = Math.min(cases.length, cursor + batchSize);
    let passCount = Number(props.getProperty(ERV2_ASSET_VERIFY_PROPERTIES.passCount) || 0);
    let failCount = Number(props.getProperty(ERV2_ASSET_VERIFY_PROPERTIES.failCount) || 0);
    const failures = [];

    for (let index = cursor; index < end; index += 1) {
      const row = cases[index];
      const result = erv2VerifySingleDriveAssetHash_(folder, row);
      if (result.ok) {
        passCount += 1;
      } else {
        failCount += 1;
        failures.push({ case_id: row.case_id, code: result.code });
      }
    }

    props.setProperty(ERV2_ASSET_VERIFY_PROPERTIES.cursor, String(end));
    props.setProperty(ERV2_ASSET_VERIFY_PROPERTIES.passCount, String(passCount));
    props.setProperty(ERV2_ASSET_VERIFY_PROPERTIES.failCount, String(failCount));

    const done = end >= cases.length;
    return {
      ok: done && failCount === 0,
      status: done && failCount === 0 ? "DRIVE_ASSET_FULL_SHA256_VERIFIED" : "DRIVE_ASSET_SHA256_BATCH_IN_PROGRESS",
      expected: cases.length,
      verified: passCount,
      cursor: end,
      remaining: Math.max(0, cases.length - end),
      mismatches: failures.filter(function(item) { return item.code === "ASSET_INTEGRITY_MISMATCH"; }).length,
      missing: failures.filter(function(item) { return item.code === "ASSET_NOT_FOUND"; }).length,
      duplicates: failures.filter(function(item) { return item.code === "ASSET_DUPLICATE"; }).length,
      invalid_mime: failures.filter(function(item) { return item.code === "ASSET_INVALID_MIME"; }).length,
      failed: failCount,
      failures: failures,
      started_at: startedAt,
    };
  } catch (error) {
    return erv2Failure_(error);
  }
}

function erv2GetCaseAsset_(payload, _reviewer, assignments, casesById, options) {
  const caseId = erv2RequiredString_(payload.caseId || payload.case_id, "CASE_NOT_ASSIGNED", "case_id is required.");
  erv2RequireAssignment_(assignments, caseId);
  const caseRow = casesById[caseId];
  if (!caseRow) throw erv2Error_("CASE_NOT_ASSIGNED", "Case is not available.");

  const folder = erv2OpenAssetFolder_(options || {});
  const file = erv2FindExactDriveAssetFile_(folder, erv2AssetFilename_(caseId));
  const mimeType = file.getMimeType();
  if (!erv2IsJpegMime_(mimeType)) throw erv2Error_("ASSET_INVALID_MIME", "Asset MIME type is invalid.");

  const bytes = file.getBlob().getBytes();
  const actualSha = erv2Sha256BytesHex_(bytes);
  if (actualSha !== String(caseRow.asset_sha256)) {
    throw erv2Error_("ASSET_INTEGRITY_MISMATCH", "Asset integrity verification failed.");
  }

  return erv2Success_({
    action: "V2_GET_CASE_ASSET",
    asset: {
      case_id: caseId,
      mime_type: "image/jpeg",
      data_base64: Utilities.base64Encode(bytes),
    },
  });
}

function erv2ReadRequiredSheets_(spreadsheet) {
  const result = {};
  Object.keys(ERV2_SHEETS).forEach(function(key) {
    const name = ERV2_SHEETS[key];
    const sheet = spreadsheet.getSheetByName(name);
    if (!sheet) throw erv2Error_("CONFIG_MISMATCH", "Required v2 sheet is missing.");
    const expected = ERV2_HEADERS[name];
    if (expected) {
      const actual = sheet.getRange(1, 1, 1, expected.length).getDisplayValues()[0].map(String);
      for (let index = 0; index < expected.length; index += 1) {
        if (actual[index] !== expected[index]) throw erv2Error_("CONFIG_MISMATCH", "Required v2 sheet schema mismatch.");
      }
      result[key] = { sheet: sheet, header: expected.slice() };
    } else {
      result[key] = { sheet: sheet, header: [] };
    }
  });
  return result;
}

function erv2ValidateConfigV2_(config, dryRun) {
  erv2AssertConfig_(config.package_id, ERV2_BACKEND_CONFIG.packageId);
  erv2AssertConfig_(config.reviewer_setup_status, ERV2_BACKEND_CONFIG.reviewerSetupStatus);
  erv2AssertConfig_(config.review_mode, ERV2_BACKEND_CONFIG.reviewMode);
  erv2AssertConfig_(config.reviewer_setup_freeze_sha256, ERV2_BACKEND_CONFIG.reviewerSetupFreezeSha256);

  if (dryRun) {
    if (!ERV2_BACKEND_CONFIG.dryRunAllowedStatuses[String(config.launch_gate_status || "")]) {
      throw erv2Error_("CONFIG_MISMATCH", "Dry-run launch gate status is not allowed.");
    }
    return;
  }
  if (String(config.review_start_enabled).toUpperCase() !== "TRUE" ||
      !ERV2_BACKEND_CONFIG.launchAllowedStatuses[String(config.launch_gate_status || "")]) {
    throw erv2Error_("REVIEW_NOT_LAUNCHED", "Expert review has not been launched.");
  }
}

function erv2AssertConfig_(actual, expected) {
  if (String(actual || "") !== String(expected)) throw erv2Error_("CONFIG_MISMATCH", "Frozen review configuration mismatch.");
}

function erv2ResolveReviewerIdentity_(payload, reviewerSheet, options) {
  let reviewerId = "";
  if (options && options.testReviewerIdentity) {
    reviewerId = String(options.testReviewerIdentity.reviewer_id || "");
  } else {
    const token = String(payload.reviewerToken || payload.accessToken || "");
    if (!token) throw erv2Error_("UNAUTHORIZED_REVIEWER", "Reviewer authorization is required.");
    const tokenMap = erv2ReadReviewerTokenMap_();
    const tokenHash = erv2Sha256Hex_(token);
    const mapped = tokenMap[tokenHash];
    reviewerId = mapped && String(mapped.reviewer_id || "");
  }
  if (!reviewerId) throw erv2Error_("UNAUTHORIZED_REVIEWER", "Reviewer authorization is required.");

  const reviewers = erv2ReadRows_(reviewerSheet, ERV2_HEADERS.Reviewers);
  const reviewer = reviewers.filter(function(row) { return String(row.reviewer_id) === reviewerId; })[0];
  if (!reviewer) throw erv2Error_("UNAUTHORIZED_REVIEWER", "Reviewer is not authorized for this review.");
  if (String(reviewer.active).toUpperCase() !== "TRUE") throw erv2Error_("REVIEWER_INACTIVE", "Reviewer is not active.");
  if (String(reviewer.review_mode) !== ERV2_BACKEND_CONFIG.reviewMode) throw erv2Error_("UNAUTHORIZED_REVIEWER", "Reviewer mode is not authorized.");
  return {
    reviewer_id: String(reviewer.reviewer_id),
    reviewer_role: String(reviewer.reviewer_role),
    assignment_group: String(reviewer.assignment_group),
  };
}

function erv2ReadReviewerTokenMap_() {
  if (typeof PropertiesService === "undefined") throw erv2Error_("UNAUTHORIZED_REVIEWER", "Reviewer authorization is not configured.");
  const raw = PropertiesService.getScriptProperties().getProperty(ERV2_BACKEND_CONFIG.tokenMapProperty);
  if (!raw) throw erv2Error_("UNAUTHORIZED_REVIEWER", "Reviewer authorization is not configured.");
  try {
    return JSON.parse(raw);
  } catch (_error) {
    throw erv2Error_("UNAUTHORIZED_REVIEWER", "Reviewer authorization is not configured.");
  }
}

function erv2Bootstrap_(reviewer, assignments, casesById, responses, sessions) {
  const session = erv2LatestSession_(sessions);
  const submittedCount = erv2SubmittedCaseSet_(responses).size;
  const currentCaseId = session && session.current_case_id ? String(session.current_case_id) : erv2FirstRemainingCaseId_(assignments, responses);
  return erv2Success_({
    action: "V2_GET_BOOTSTRAP",
    reviewer: erv2PublicReviewer_(reviewer),
    assigned_count: assignments.length,
    completed_count: submittedCount,
    remaining_count: Math.max(0, assignments.length - submittedCount),
    current_case: currentCaseId ? erv2SafeCasePayload_(casesById[currentCaseId]) : null,
    allowed_decisions: Object.keys(ERV2_DECISIONS),
    allowed_confidence: Object.keys(ERV2_CONFIDENCE),
    definition_version: erv2FirstDefinitionVersion_(assignments, casesById),
    session: session ? erv2SessionPayload_(session) : null,
  });
}

function erv2LoadProgress_(payload, reviewer, assignments, casesById, responses, sessions) {
  if (payload.caseId) erv2RequireAssignment_(assignments, payload.caseId);
  return erv2Success_({
    action: "V2_LOAD_PROGRESS",
    reviewer: erv2PublicReviewer_(reviewer),
    assigned_count: assignments.length,
    completed_count: erv2SubmittedCaseSet_(responses).size,
    assignments: assignments.map(function(assignment) {
      return {
        assignment_id: assignment.assignment_id,
        reviewer_role: assignment.reviewer_role,
        batch_id: assignment.batch_id,
        review_order: Number(assignment.review_order),
        required: String(assignment.required).toUpperCase() !== "FALSE",
        assignment_status: assignment.assignment_status,
        case: erv2SafeCasePayload_(casesById[assignment.case_id]),
        response: erv2OwnCaseResponsePayload_(responses, assignment.case_id),
      };
    }),
    session: erv2LatestSession_(sessions) ? erv2SessionPayload_(erv2LatestSession_(sessions)) : null,
  });
}

function erv2SaveDraft_(payload, reviewer, assignments, casesById, responses, sessions, sheets, options) {
  const caseId = erv2RequiredString_(payload.caseId || payload.case_id, "CASE_NOT_ASSIGNED", "case_id is required.");
  const assignment = erv2RequireAssignment_(assignments, caseId);
  if (!casesById[caseId]) throw erv2Error_("CASE_NOT_ASSIGNED", "Case is not available.");
  const decision = erv2ValidateDecision_(payload.decision);
  const confidence = erv2ValidateConfidence_(payload.confidence);
  erv2RejectIfSubmitted_(responses, caseId, payload, false);

  const sessionWrite = erv2BuildSessionWrite_(payload, reviewer, assignments, responses, sessions, caseId, decision, confidence, false);
  const responseWrite = erv2BuildResponseWrite_(payload, reviewer, caseId, "DRAFT", decision, confidence, "", responses);
  const draftRow = erv2FindResponseRow_(sheets.responses.sheet, sheets.responses.header, reviewer.reviewer_id, caseId, "DRAFT");
  if (draftRow.rowNumber) {
    sheets.responses.sheet.getRange(draftRow.rowNumber, 1, 1, sheets.responses.header.length)
      .setValues([erv2RowToValues_(sheets.responses.header, responseWrite)]);
  } else {
    sheets.responses.sheet.appendRow(erv2RowToValues_(sheets.responses.header, responseWrite));
  }
  erv2WriteSession_(sheets.sessions.sheet, sheets.sessions.header, sessionWrite);
  erv2MaybeMarkAssignmentInProgress_(sheets.assignments.sheet, sheets.assignments.header, assignment, options);

  return erv2Success_({
    action: "V2_SAVE_DRAFT",
    response_id: responseWrite.response_id,
    response_status: "DRAFT",
    session: erv2SessionPayload_(sessionWrite),
  });
}

function erv2SubmitResponse_(payload, reviewer, assignments, casesById, responses, sessions, sheets, options) {
  const caseId = erv2RequiredString_(payload.caseId || payload.case_id, "CASE_NOT_ASSIGNED", "case_id is required.");
  const assignment = erv2RequireAssignment_(assignments, caseId);
  if (!casesById[caseId]) throw erv2Error_("CASE_NOT_ASSIGNED", "Case is not available.");
  const decision = erv2ValidateDecision_(payload.decision);
  const confidence = erv2ValidateConfidence_(payload.confidence);
  const existingSubmitted = erv2RejectIfSubmitted_(responses, caseId, payload, true);
  if (existingSubmitted) {
    return erv2Success_({
      action: "V2_SUBMIT_RESPONSE",
      response_id: existingSubmitted.response_id,
      response_status: "SUBMITTED",
      idempotent: true,
    });
  }

  const submittedAt = erv2NowIso_();
  const responseWrite = erv2BuildResponseWrite_(payload, reviewer, caseId, "SUBMITTED", decision, confidence, submittedAt, responses);
  const draftRow = erv2FindResponseRow_(sheets.responses.sheet, sheets.responses.header, reviewer.reviewer_id, caseId, "DRAFT");
  if (draftRow.rowNumber) {
    sheets.responses.sheet.getRange(draftRow.rowNumber, 1, 1, sheets.responses.header.length)
      .setValues([erv2RowToValues_(sheets.responses.header, responseWrite)]);
  } else {
    sheets.responses.sheet.appendRow(erv2RowToValues_(sheets.responses.header, responseWrite));
  }

  const responsesAfterSubmit = responses.concat([responseWrite]);
  const sessionWrite = erv2BuildSessionWrite_(payload, reviewer, assignments, responsesAfterSubmit, sessions, caseId, decision, confidence, true, submittedAt);
  erv2WriteSession_(sheets.sessions.sheet, sheets.sessions.header, sessionWrite);
  erv2MaybeMarkAssignmentCompleted_(sheets.assignments.sheet, sheets.assignments.header, assignment, options, submittedAt);

  return erv2Success_({
    action: "V2_SUBMIT_RESPONSE",
    response_id: responseWrite.response_id,
    response_status: "SUBMITTED",
    idempotent: false,
    row_hash: responseWrite.row_hash,
    session: erv2SessionPayload_(sessionWrite),
  });
}

function erv2BuildResponseWrite_(payload, reviewer, caseId, status, decision, confidence, submittedAt, responses) {
  const now = erv2NowIso_();
  const startedAt = String(payload.startedAt || payload.started_at || now);
  const responseId = erv2StableResponseId_(reviewer.reviewer_id, caseId, String(payload.sessionId || payload.session_id || ""));
  const existing = erv2LatestCaseResponse_(responses, caseId);
  const responseVersion = Number(existing && existing.response_version) || 1;
  const row = {
    response_id: responseId,
    case_id: caseId,
    reviewer_id: reviewer.reviewer_id,
    decision: decision,
    confidence: confidence,
    comment: String(payload.comment || ""),
    response_status: status,
    started_at: existing && existing.started_at ? existing.started_at : startedAt,
    last_saved_at: now,
    submitted_at: submittedAt || "",
    response_version: responseVersion,
    session_id: String(payload.sessionId || payload.session_id || ""),
    client_version: String(payload.clientVersion || payload.client_version || ""),
    protocol_deviation_id: String(payload.protocolDeviationId || payload.protocol_deviation_id || ""),
    row_hash: "",
  };
  row.row_hash = erv2ResponseRowHash_(row);
  return row;
}

function erv2BuildSessionWrite_(payload, reviewer, assignments, responses, sessions, caseId, _decision, _confidence, submitted, submittedAt) {
  const current = erv2LatestSession_(sessions);
  const sessionId = String(payload.sessionId || payload.session_id || (current && current.session_id) || erv2StableSessionId_(reviewer.reviewer_id));
  erv2GuardStaleSession_(payload, current);
  const completed = erv2SubmittedCaseSet_(responses).size;
  const now = erv2NowIso_();
  return {
    session_id: sessionId,
    reviewer_id: reviewer.reviewer_id,
    reviewer_role: reviewer.reviewer_role,
    session_status: completed >= assignments.length ? "SUBMITTED" : "IN_PROGRESS",
    current_case_id: caseId,
    current_batch_id: erv2AssignmentBatch_(assignments, caseId),
    assigned_count: assignments.length,
    completed_count: completed,
    remaining_count: Math.max(0, assignments.length - completed),
    started_at: current && current.started_at ? current.started_at : String(payload.startedAt || payload.started_at || now),
    last_saved_at: now,
    submitted_at: submitted ? submittedAt : (current && current.submitted_at ? current.submitted_at : ""),
    state_version: (Number(current && current.state_version) || 0) + 1,
    state_json: typeof payload.stateJson === "object" ? JSON.stringify(payload.stateJson) : String(payload.stateJson || payload.state_json || "{}"),
    client_version: String(payload.clientVersion || payload.client_version || ""),
    base_state_updated_at: String(payload.baseStateUpdatedAt || payload.base_state_updated_at || ""),
    reviewer_notes: String(payload.reviewerNotes || payload.reviewer_notes || ""),
    server_notes: "",
  };
}

function erv2GuardStaleSession_(payload, current) {
  if (!current) return;
  const supplied = payload.baseStateVersion !== undefined ? payload.baseStateVersion : payload.base_state_version;
  if (supplied === undefined || supplied === null || supplied === "") {
    throw erv2Error_("STALE_STATE", "Client state_version is required to update an existing session.");
  }
  if (Number(supplied) !== Number(current.state_version || 0)) {
    throw erv2Error_("STALE_STATE", "Client state is older than the server session.");
  }
}

function erv2WriteSession_(sheet, header, sessionWrite) {
  const row = erv2FindSessionRow_(sheet, header, sessionWrite.session_id);
  const values = erv2RowToValues_(header, sessionWrite);
  if (row) {
    sheet.getRange(row, 1, 1, header.length).setValues([values]);
  } else {
    sheet.appendRow(values);
  }
}

function erv2RejectIfSubmitted_(responses, caseId, payload, allowIdempotent) {
  const submitted = responses.filter(function(row) {
    return String(row.case_id) === String(caseId) && String(row.response_status) === "SUBMITTED";
  })[0];
  if (!submitted) return null;
  if (allowIdempotent && erv2SubmittedContentMatches_(submitted, payload)) return submitted;
  throw erv2Error_("RESPONSE_ALREADY_SUBMITTED", "Submitted responses cannot be overwritten.");
}

function erv2SubmittedContentMatches_(submitted, payload) {
  return String(submitted.decision) === String(payload.decision || "") &&
    String(submitted.confidence) === String(payload.confidence || "") &&
    String(submitted.comment || "") === String(payload.comment || "") &&
    String(submitted.session_id || "") === String(payload.sessionId || payload.session_id || "") &&
    String(submitted.client_version || "") === String(payload.clientVersion || payload.client_version || "");
}

function erv2ValidateDecision_(decision) {
  const value = String(decision || "");
  if (!ERV2_DECISIONS[value]) throw erv2Error_("INVALID_DECISION", "Decision is not allowed.");
  return value;
}

function erv2ValidateConfidence_(confidence) {
  const value = String(confidence || "");
  if (!ERV2_CONFIDENCE[value]) throw erv2Error_("INVALID_CONFIDENCE", "Confidence is not allowed.");
  return value;
}

function erv2RequireAssignment_(assignments, caseId) {
  const assignment = assignments.filter(function(row) { return String(row.case_id) === String(caseId); })[0];
  if (!assignment || String(assignment.assignment_status).toUpperCase() === "CANCELLED") {
    throw erv2Error_("CASE_NOT_ASSIGNED", "Case is not assigned to this reviewer.");
  }
  return assignment;
}

function erv2OwnAssignments_(sheet, reviewer) {
  return erv2ReadRows_(sheet, ERV2_HEADERS.ReviewAssignments).filter(function(row) {
    return String(row.reviewer_id) === reviewer.reviewer_id &&
      String(row.reviewer_role) === reviewer.reviewer_role &&
      String(row.assignment_status).toUpperCase() !== "CANCELLED";
  }).sort(function(left, right) {
    return Number(left.review_order) - Number(right.review_order);
  });
}

function erv2OwnResponses_(sheet, reviewer) {
  return erv2ReadRows_(sheet, ERV2_HEADERS.ReviewResponses).filter(function(row) {
    return String(row.reviewer_id) === reviewer.reviewer_id;
  });
}

function erv2OwnSessions_(sheet, reviewer) {
  return erv2ReadRows_(sheet, ERV2_HEADERS.ReviewSessionsV2).filter(function(row) {
    return String(row.reviewer_id) === reviewer.reviewer_id;
  });
}

function erv2ExpectedCaseRows_(sheet) {
  const rows = erv2ReadRows_(sheet, ERV2_HEADERS.ReviewCases).filter(function(row) {
    return String(row.package_id) === ERV2_BACKEND_CONFIG.packageId;
  }).sort(function(left, right) {
    return Number(left.review_order) - Number(right.review_order);
  });
  if (rows.length !== ERV2_BACKEND_CONFIG.expectedAssetCount) {
    throw erv2Error_("CONFIG_MISMATCH", "Frozen case count mismatch.");
  }
  const seen = {};
  rows.forEach(function(row, index) {
    if (Number(row.review_order) !== index + 1) throw erv2Error_("CONFIG_MISMATCH", "Frozen review order mismatch.");
    if (seen[row.case_id]) throw erv2Error_("CONFIG_MISMATCH", "Duplicate frozen case identity.");
    seen[row.case_id] = true;
  });
  return rows;
}

function erv2AssetFilename_(caseId) {
  return String(caseId) + ".jpg";
}

function erv2OpenAssetFolder_(options) {
  const folderId = (options && options.assetFolderId) || erv2ConfiguredAssetFolderId_();
  const folder = (options && options.assetFolder) || DriveApp.getFolderById(folderId);
  if (folder.getName() !== ERV2_BACKEND_CONFIG.expectedAssetFolderName) {
    throw erv2Error_("ASSET_FOLDER_NAME_MISMATCH", "Configured asset folder identity is invalid.");
  }
  return folder;
}

function erv2ConfiguredAssetFolderId_() {
  const raw = erv2ScriptProperties_().getProperty(ERV2_BACKEND_CONFIG.assetFolderProperty);
  if (!raw) throw erv2Error_("ASSET_FOLDER_NOT_CONFIGURED", "Reviewer asset folder is not configured.");
  return raw;
}

function erv2ScriptProperties_() {
  if (typeof PropertiesService === "undefined") {
    throw erv2Error_("ASSET_FOLDER_NOT_CONFIGURED", "Required server-side configuration is missing.");
  }
  return PropertiesService.getScriptProperties();
}

function erv2FindExactDriveAssetFile_(folder, filename) {
  const files = [];
  const iterator = folder.getFilesByName(filename);
  while (iterator.hasNext()) {
    const file = iterator.next();
    if (file.getName() === filename) files.push(file);
  }
  if (files.length === 0) throw erv2Error_("ASSET_NOT_FOUND", "Requested asset is not available.");
  if (files.length > 1) throw erv2Error_("ASSET_DUPLICATE", "Requested asset is duplicated.");
  return files[0];
}

function erv2DriveFolderInventory_(folder) {
  const iterator = folder.getFiles();
  const files = [];
  const seen = {};
  const duplicates = {};
  while (iterator.hasNext()) {
    const file = iterator.next();
    const name = file.getName();
    files.push({ name: name, mimeType: file.getMimeType() });
    if (seen[name]) duplicates[name] = true;
    seen[name] = true;
  }
  return { files: files, filesByName: seen, duplicateNames: duplicates };
}

function erv2VerifySingleDriveAssetHash_(folder, caseRow) {
  try {
    const file = erv2FindExactDriveAssetFile_(folder, erv2AssetFilename_(caseRow.case_id));
    if (!erv2IsJpegMime_(file.getMimeType())) return { ok: false, code: "ASSET_INVALID_MIME" };
    const actualSha = erv2Sha256BytesHex_(file.getBlob().getBytes());
    if (actualSha !== String(caseRow.asset_sha256)) return { ok: false, code: "ASSET_INTEGRITY_MISMATCH" };
    return { ok: true };
  } catch (error) {
    return { ok: false, code: error && error.code ? error.code : "INTERNAL_ERROR" };
  }
}

function erv2IsJpegMime_(mimeType) {
  const normalized = String(mimeType || "").toLowerCase();
  return normalized === "image/jpeg" || normalized === "image/jpg";
}

function erv2SafeCasePayload_(row) {
  if (!row) return null;
  const safe = {
    case_id: String(row.case_id),
    case_index: Number(row.case_index),
    batch_id: String(row.batch_id),
    batch_position: Number(row.batch_position),
    review_order: Number(row.review_order),
    package_id: String(row.package_id),
    case_status: String(row.case_status),
    definition_version: String(row.definition_version),
  };
  ERV2_FORBIDDEN_REVIEWER_FIELDS.forEach(function(field) {
    if (Object.prototype.hasOwnProperty.call(safe, field)) delete safe[field];
  });
  return safe;
}

function erv2OwnCaseResponsePayload_(responses, caseId) {
  const response = erv2LatestCaseResponse_(responses, caseId);
  if (!response) return null;
  return {
    response_id: response.response_id,
    case_id: response.case_id,
    decision: response.decision,
    confidence: response.confidence,
    comment: response.comment,
    response_status: response.response_status,
    last_saved_at: response.last_saved_at,
    submitted_at: response.submitted_at,
    response_version: Number(response.response_version) || 1,
    session_id: response.session_id,
    client_version: response.client_version,
  };
}

function erv2LatestCaseResponse_(responses, caseId) {
  const matches = responses.filter(function(row) { return String(row.case_id) === String(caseId); });
  matches.sort(function(left, right) {
    return erv2Timestamp_(right.submitted_at || right.last_saved_at) - erv2Timestamp_(left.submitted_at || left.last_saved_at);
  });
  return matches[0] || null;
}

function erv2LatestSession_(sessions) {
  const sorted = sessions.slice().sort(function(left, right) {
    return erv2Timestamp_(right.last_saved_at || right.started_at) - erv2Timestamp_(left.last_saved_at || left.started_at);
  });
  return sorted[0] || null;
}

function erv2SessionPayload_(session) {
  return {
    session_id: session.session_id,
    session_status: session.session_status,
    current_case_id: session.current_case_id,
    current_batch_id: session.current_batch_id,
    assigned_count: Number(session.assigned_count) || 0,
    completed_count: Number(session.completed_count) || 0,
    remaining_count: Number(session.remaining_count) || 0,
    started_at: session.started_at,
    last_saved_at: session.last_saved_at,
    submitted_at: session.submitted_at,
    state_version: Number(session.state_version) || 0,
    state_json: session.state_json,
    client_version: session.client_version,
    base_state_updated_at: session.base_state_updated_at,
    reviewer_notes: session.reviewer_notes,
  };
}

function erv2PublicReviewer_(reviewer) {
  return { reviewer_id: reviewer.reviewer_id, reviewer_role: reviewer.reviewer_role };
}

function erv2ReadConfigV2_(sheet) {
  const values = sheet.getDataRange().getDisplayValues();
  const config = {};
  values.forEach(function(row) {
    if (row[0]) config[String(row[0])] = row[1];
  });
  return config;
}

function erv2ReadRows_(sheet, header) {
  if (sheet.getLastRow() <= 1) return [];
  return sheet.getRange(2, 1, sheet.getLastRow() - 1, header.length).getDisplayValues()
    .filter(function(row) {
      return row.some(function(value) { return String(value) !== ""; });
    })
    .map(function(row) { return erv2RowObjectFromValues_(header, row); });
}

function erv2RowsByKey_(rows, key) {
  const result = {};
  rows.forEach(function(row) { result[String(row[key])] = row; });
  return result;
}

function erv2FindResponseRow_(sheet, header, reviewerId, caseId, status) {
  const rows = erv2ReadRows_(sheet, header);
  for (let index = 0; index < rows.length; index += 1) {
    if (String(rows[index].reviewer_id) === String(reviewerId) &&
        String(rows[index].case_id) === String(caseId) &&
        String(rows[index].response_status) === String(status)) {
      return { rowNumber: index + 2, row: rows[index] };
    }
  }
  return { rowNumber: 0, row: null };
}

function erv2FindSessionRow_(sheet, header, sessionId) {
  const rows = erv2ReadRows_(sheet, header);
  for (let index = 0; index < rows.length; index += 1) {
    if (String(rows[index].session_id) === String(sessionId)) return index + 2;
  }
  return 0;
}

function erv2RowObjectFromValues_(header, values) {
  return header.reduce(function(acc, column, index) {
    acc[column] = values[index];
    return acc;
  }, {});
}

function erv2RowToValues_(header, rowObject) {
  return header.map(function(column) {
    return Object.prototype.hasOwnProperty.call(rowObject, column) ? rowObject[column] : "";
  });
}

function erv2SubmittedCaseSet_(responses) {
  const set = new Set();
  responses.forEach(function(row) {
    if (String(row.response_status) === "SUBMITTED") set.add(String(row.case_id));
  });
  return set;
}

function erv2FirstRemainingCaseId_(assignments, responses) {
  const submitted = erv2SubmittedCaseSet_(responses);
  for (let index = 0; index < assignments.length; index += 1) {
    if (!submitted.has(String(assignments[index].case_id))) return String(assignments[index].case_id);
  }
  return "";
}

function erv2FirstDefinitionVersion_(assignments, casesById) {
  for (let index = 0; index < assignments.length; index += 1) {
    const row = casesById[assignments[index].case_id];
    if (row && row.definition_version) return String(row.definition_version);
  }
  return "";
}

function erv2AssignmentBatch_(assignments, caseId) {
  const row = assignments.filter(function(assignment) { return String(assignment.case_id) === String(caseId); })[0];
  return row ? String(row.batch_id) : "";
}

function erv2MaybeMarkAssignmentInProgress_(sheet, header, assignment, options) {
  if (!options || options.enableAssignmentTransitions !== true) return;
  if (String(assignment.assignment_status).toUpperCase() !== "PENDING") return;
  erv2PatchAssignmentStatus_(sheet, header, assignment.assignment_id, "IN_PROGRESS", "");
}

function erv2MaybeMarkAssignmentCompleted_(sheet, header, assignment, options, completedAt) {
  if (!options || options.enableAssignmentTransitions !== true) return;
  erv2PatchAssignmentStatus_(sheet, header, assignment.assignment_id, "COMPLETED", completedAt);
}

function erv2PatchAssignmentStatus_(sheet, header, assignmentId, status, completedAt) {
  const rows = erv2ReadRows_(sheet, header);
  for (let index = 0; index < rows.length; index += 1) {
    if (String(rows[index].assignment_id) === String(assignmentId)) {
      rows[index].assignment_status = status;
      rows[index].completed_at = completedAt || rows[index].completed_at || "";
      sheet.getRange(index + 2, 1, 1, header.length).setValues([erv2RowToValues_(header, rows[index])]);
      return;
    }
  }
}

function erv2StableResponseId_(reviewerId, caseId, sessionId) {
  return "ERV2_RESP_" + erv2Sha256Hex_([
    ERV2_BACKEND_CONFIG.packageId, reviewerId, caseId, sessionId,
  ].join("|")).slice(0, 24);
}

function erv2StableSessionId_(reviewerId) {
  return "ERV2_SESSION_" + erv2Sha256Hex_([ERV2_BACKEND_CONFIG.packageId, reviewerId].join("|")).slice(0, 20);
}

function erv2ResponseRowHash_(row) {
  return erv2Sha256Hex_(erv2CanonicalResponseJson_(row));
}

function erv2CanonicalResponseJson_(row) {
  // row_hash canonical fields: response_id, package_id, case_id, reviewer_id,
  // decision, confidence, comment, response_status, submitted_at,
  // response_version, session_id, client_version, protocol_deviation_id.
  return JSON.stringify({
    response_id: String(row.response_id || ""),
    package_id: ERV2_BACKEND_CONFIG.packageId,
    case_id: String(row.case_id || ""),
    reviewer_id: String(row.reviewer_id || ""),
    decision: String(row.decision || ""),
    confidence: String(row.confidence || ""),
    comment: String(row.comment || ""),
    response_status: String(row.response_status || ""),
    submitted_at: String(row.submitted_at || ""),
    response_version: String(row.response_version || ""),
    session_id: String(row.session_id || ""),
    client_version: String(row.client_version || ""),
    protocol_deviation_id: String(row.protocol_deviation_id || ""),
  });
}

function erv2Sha256Hex_(value) {
  if (typeof Utilities === "undefined") throw erv2Error_("INTERNAL_ERROR", "SHA-256 service is unavailable.");
  const digest = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, String(value));
  return digest.map(function(byteValue) {
    const normalized = (byteValue + 256) % 256;
    return ("0" + normalized.toString(16)).slice(-2);
  }).join("");
}

function erv2Sha256BytesHex_(bytes) {
  if (typeof Utilities === "undefined") throw erv2Error_("INTERNAL_ERROR", "SHA-256 service is unavailable.");
  const digest = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, bytes);
  return digest.map(function(byteValue) {
    const normalized = (byteValue + 256) % 256;
    return ("0" + normalized.toString(16)).slice(-2);
  }).join("");
}

function erv2WithScriptLock_(callback, options) {
  if (options && options.lockAlreadyHeld) return callback();
  if (typeof LockService === "undefined") return callback();
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(ERV2_BACKEND_CONFIG.lockTimeoutMs);
  } catch (_error) {
    throw erv2Error_("LOCK_TIMEOUT", "Could not acquire write lock.");
  }
  try {
    return callback();
  } finally {
    lock.releaseLock();
  }
}

function erv2RequiredString_(value, code, message) {
  const normalized = String(value || "");
  if (!normalized) throw erv2Error_(code, message);
  return normalized;
}

function erv2NowIso_() {
  return new Date().toISOString();
}

function erv2Timestamp_(value) {
  const time = value ? Date.parse(value) : 0;
  return Number.isFinite(time) ? time : 0;
}

function erv2Success_(body) {
  return Object.assign({ ok: true }, body);
}

function erv2Failure_(error) {
  const code = error && error.code ? error.code : "INTERNAL_ERROR";
  const allowed = {
    REVIEW_NOT_LAUNCHED: true,
    UNAUTHORIZED_REVIEWER: true,
    REVIEWER_INACTIVE: true,
    CASE_NOT_ASSIGNED: true,
    INVALID_DECISION: true,
    INVALID_CONFIDENCE: true,
    RESPONSE_ALREADY_SUBMITTED: true,
    STALE_STATE: true,
    CONFIG_MISMATCH: true,
    LOCK_TIMEOUT: true,
    INTERNAL_ERROR: true,
    INVALID_PAYLOAD: true,
    ASSET_FOLDER_NOT_CONFIGURED: true,
    ASSET_FOLDER_NAME_MISMATCH: true,
    ASSET_NOT_FOUND: true,
    ASSET_DUPLICATE: true,
    ASSET_INVALID_MIME: true,
    ASSET_INTEGRITY_MISMATCH: true,
    ASSET_VERIFICATION_INCOMPLETE: true,
  };
  return {
    ok: false,
    error: {
      code: allowed[code] ? code : "INTERNAL_ERROR",
      message: error && error.message ? error.message : "Internal error.",
    },
  };
}

function erv2Error_(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}
