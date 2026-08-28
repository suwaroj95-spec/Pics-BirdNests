/**
 * TEMPORARY READ-ONLY ADMIN CHECKER for EXPERT-REVIEW-R1.
 *
 * Paste into the live Apps Script project, run
 * runExpertReviewV2PredeploymentSafetyCheck() once, then remove it before
 * deployment. This checker performs reads only and emits one sanitized result.
 */

const ERV2_PREDEPLOYMENT_EXPECTED_ = Object.freeze({
  spreadsheetId: "1c5QYrz8CJymAO3LAu8szYnBoubnoT82dPQkf0UJRGTg",
  packageId: "EXPERT-REVIEW-R1",
  tokenMapProperty: "ERV2_REVIEWER_TOKEN_MAP_JSON",
  assetFolderProperty: "ERV2_REVIEW_ASSET_FOLDER_ID",
  expectedCases: 1169,
  expectedAssignments: 1461,
  expectedRevAAssignments: 1169,
  expectedRevBAssignments: 292,
  expectedLaunchGateStatus: "BLOCKED",
  expectedReviewStartEnabled: false,
});

const ERV2_PREDEPLOYMENT_ASSET_PROPERTIES_ = Object.freeze({
  cursor: "ERV2_ASSET_VERIFY_CURSOR",
  passCount: "ERV2_ASSET_VERIFY_PASS_COUNT",
  failCount: "ERV2_ASSET_VERIFY_FAIL_COUNT",
  mismatchCount: "ERV2_ASSET_VERIFY_MISMATCH_COUNT",
  missingCount: "ERV2_ASSET_VERIFY_MISSING_COUNT",
  duplicateCount: "ERV2_ASSET_VERIFY_DUPLICATE_COUNT",
  invalidMimeCount: "ERV2_ASSET_VERIFY_INVALID_MIME_COUNT",
  internalErrorCount: "ERV2_ASSET_VERIFY_INTERNAL_ERROR_COUNT",
  folderId: "ERV2_ASSET_VERIFY_FOLDER_ID",
});

const ERV2_PREDEPLOYMENT_SHEETS_ = Object.freeze({
  reviewers: "Reviewers",
  assignments: "ReviewAssignments",
  responses: "ReviewResponses",
  sessions: "ReviewSessionsV2",
  config: "ConfigV2",
});

function runExpertReviewV2PredeploymentSafetyCheck() {
  const failureCodes = [];
  let result;
  try {
    const props = PropertiesService.getScriptProperties();
    result = Object.assign(
      {
        ok: false,
        status: "PREDEPLOYMENT_SAFETY_BLOCKED",
        live_writes_performed: false,
      },
      erv2PredeploymentCheckTokenMap_(props),
      erv2PredeploymentCheckAssetState_(props),
      erv2PredeploymentCheckLiveSheets_()
    );
    erv2PredeploymentCollectFailures_(result, failureCodes);
  } catch (error) {
    result = {
      ok: false,
      status: "PREDEPLOYMENT_SAFETY_BLOCKED",
      failure_codes: [erv2PredeploymentSafeErrorCode_(error)],
      live_writes_performed: false,
    };
  }

  if (result && !result.failure_codes) result.failure_codes = failureCodes;
  if (result && result.failure_codes && result.failure_codes.length === 0) delete result.failure_codes;
  if (result) {
    result.ok = !result.failure_codes;
    result.status = result.ok ? "PREDEPLOYMENT_SAFETY_VERIFIED" : "PREDEPLOYMENT_SAFETY_BLOCKED";
  }
  console.log(JSON.stringify(result));
  return result;
}

function erv2PredeploymentCheckTokenMap_(props) {
  const rawTokenMap = props.getProperty(ERV2_PREDEPLOYMENT_EXPECTED_.tokenMapProperty);
  const output = {
    token_map_present: Boolean(rawTokenMap),
    token_map_parse_ok: false,
    token_map_entry_count: 0,
    token_map_reviewer_set_ok: false,
    token_hash_format_ok: false,
  };
  if (!rawTokenMap) return output;

  let parsed;
  try {
    parsed = JSON.parse(rawTokenMap);
    output.token_map_parse_ok = parsed && typeof parsed === "object" && !Array.isArray(parsed);
  } catch (_error) {
    return output;
  }
  if (!output.token_map_parse_ok) return output;

  const hashKeys = Object.keys(parsed);
  const reviewers = {};
  output.token_map_entry_count = hashKeys.length;
  output.token_hash_format_ok = hashKeys.every(function(key) {
    return /^[0-9a-f]{64}$/.test(String(key));
  });

  hashKeys.forEach(function(key) {
    const reviewerId = erv2PredeploymentReviewerIdFromTokenMapping_(parsed[key]);
    if (reviewerId) reviewers[reviewerId] = (reviewers[reviewerId] || 0) + 1;
  });

  output.token_map_reviewer_set_ok =
    hashKeys.length === 2 &&
    reviewers.REV_A === 1 &&
    reviewers.REV_B === 1 &&
    Object.keys(reviewers).length === 2;
  return output;
}

function erv2PredeploymentReviewerIdFromTokenMapping_(mapping) {
  if (typeof mapping === "string") return mapping;
  if (mapping && typeof mapping === "object") return String(mapping.reviewer_id || "");
  return "";
}

function erv2PredeploymentCheckAssetState_(props) {
  const assetFolderId = props.getProperty(ERV2_PREDEPLOYMENT_EXPECTED_.assetFolderProperty);
  const verifyFolderId = props.getProperty(ERV2_PREDEPLOYMENT_ASSET_PROPERTIES_.folderId);
  const cursor = erv2PredeploymentNumberProperty_(props, ERV2_PREDEPLOYMENT_ASSET_PROPERTIES_.cursor);
  const passCount = erv2PredeploymentNumberProperty_(props, ERV2_PREDEPLOYMENT_ASSET_PROPERTIES_.passCount);
  const failCount = erv2PredeploymentNumberProperty_(props, ERV2_PREDEPLOYMENT_ASSET_PROPERTIES_.failCount);
  const mismatchCount = erv2PredeploymentNumberProperty_(props, ERV2_PREDEPLOYMENT_ASSET_PROPERTIES_.mismatchCount);
  const missingCount = erv2PredeploymentNumberProperty_(props, ERV2_PREDEPLOYMENT_ASSET_PROPERTIES_.missingCount);
  const duplicateCount = erv2PredeploymentNumberProperty_(props, ERV2_PREDEPLOYMENT_ASSET_PROPERTIES_.duplicateCount);
  const invalidMimeCount = erv2PredeploymentNumberProperty_(props, ERV2_PREDEPLOYMENT_ASSET_PROPERTIES_.invalidMimeCount);
  const internalErrorCount = erv2PredeploymentNumberProperty_(props, ERV2_PREDEPLOYMENT_ASSET_PROPERTIES_.internalErrorCount);

  return {
    asset_cursor: cursor,
    asset_pass_count: passCount,
    asset_fail_count: failCount,
    asset_mismatch_count: mismatchCount,
    asset_missing_count: missingCount,
    asset_duplicate_count: duplicateCount,
    asset_invalid_mime_count: invalidMimeCount,
    asset_internal_error_count: internalErrorCount,
    asset_integrity_state_ok:
      cursor === ERV2_PREDEPLOYMENT_EXPECTED_.expectedCases &&
      passCount === ERV2_PREDEPLOYMENT_EXPECTED_.expectedCases &&
      failCount === 0 &&
      mismatchCount === 0 &&
      missingCount === 0 &&
      duplicateCount === 0 &&
      invalidMimeCount === 0 &&
      internalErrorCount === 0,
    asset_folder_property_present: Boolean(assetFolderId),
    asset_folder_binding_matches: Boolean(assetFolderId) && (!verifyFolderId || verifyFolderId === assetFolderId),
  };
}

function erv2PredeploymentNumberProperty_(props, name) {
  const value = props.getProperty(name);
  if (value === null || value === "") return 0;
  return Number(value);
}

function erv2PredeploymentCheckLiveSheets_() {
  const spreadsheet = SpreadsheetApp.openById(ERV2_PREDEPLOYMENT_EXPECTED_.spreadsheetId);
  const sheets = {};
  Object.keys(ERV2_PREDEPLOYMENT_SHEETS_).forEach(function(key) {
    sheets[key] = erv2PredeploymentRequiredSheet_(spreadsheet, ERV2_PREDEPLOYMENT_SHEETS_[key]);
  });

  const reviewerRows = erv2ReadRows_(sheets.reviewers, ERV2_HEADERS.Reviewers);
  const assignmentRows = erv2ReadRows_(sheets.assignments, ERV2_HEADERS.ReviewAssignments);
  const responseRows = erv2ReadRows_(sheets.responses, ERV2_HEADERS.ReviewResponses);
  const sessionRows = erv2ReadRows_(sheets.sessions, ERV2_HEADERS.ReviewSessionsV2);
  const config = erv2ReadConfigV2_(sheets.config);

  const revARows = reviewerRows.filter(function(row) { return String(row.reviewer_id) === "REV_A"; });
  const revBRows = reviewerRows.filter(function(row) { return String(row.reviewer_id) === "REV_B"; });
  const reviewerAActive = revARows.length === 1 ? erv2PredeploymentIsActive_(revARows[0].active) : null;
  const reviewerBActive = revBRows.length === 1 ? erv2PredeploymentIsActive_(revBRows[0].active) : null;

  let revAAssignments = 0;
  let revBAssignments = 0;
  let unexpectedReviewerAssignments = 0;
  assignmentRows.forEach(function(row) {
    const reviewerId = String(row.reviewer_id || "");
    if (reviewerId === "REV_A") revAAssignments += 1;
    else if (reviewerId === "REV_B") revBAssignments += 1;
    else unexpectedReviewerAssignments += 1;
  });

  const reviewStartEnabled = erv2PredeploymentIsActive_(config.review_start_enabled);
  return {
    reviewer_a_present: revARows.length === 1,
    reviewer_b_present: revBRows.length === 1,
    reviewer_a_active: reviewerAActive,
    reviewer_b_active: reviewerBActive,
    total_assignments: assignmentRows.length,
    rev_a_assignments: revAAssignments,
    rev_b_assignments: revBAssignments,
    unexpected_reviewer_assignments: unexpectedReviewerAssignments,
    assignment_counts_ok:
      assignmentRows.length === ERV2_PREDEPLOYMENT_EXPECTED_.expectedAssignments &&
      revAAssignments === ERV2_PREDEPLOYMENT_EXPECTED_.expectedRevAAssignments &&
      revBAssignments === ERV2_PREDEPLOYMENT_EXPECTED_.expectedRevBAssignments &&
      unexpectedReviewerAssignments === 0,
    review_responses: responseRows.length,
    review_sessions_v2: sessionRows.length,
    launch_gate_status: String(config.launch_gate_status || ""),
    review_start_enabled: reviewStartEnabled,
  };
}

function erv2PredeploymentRequiredSheet_(spreadsheet, name) {
  const sheet = spreadsheet.getSheetByName(name);
  if (!sheet) throw erv2PredeploymentError_("MISSING_SHEET");
  return sheet;
}

function erv2PredeploymentIsActive_(value) {
  if (value === true) return true;
  if (value === false) return false;
  const normalized = String(value || "").trim().toUpperCase();
  return normalized === "TRUE" || normalized === "YES" || normalized === "1";
}

function erv2PredeploymentCollectFailures_(result, failureCodes) {
  erv2PredeploymentRequire_(result.token_map_present, "TOKEN_MAP_MISSING", failureCodes);
  erv2PredeploymentRequire_(result.token_map_parse_ok, "TOKEN_MAP_PARSE_FAILED", failureCodes);
  erv2PredeploymentRequire_(result.token_map_entry_count === 2, "TOKEN_MAP_ENTRY_COUNT_MISMATCH", failureCodes);
  erv2PredeploymentRequire_(result.token_map_reviewer_set_ok, "TOKEN_MAP_REVIEWER_SET_MISMATCH", failureCodes);
  erv2PredeploymentRequire_(result.token_hash_format_ok, "TOKEN_HASH_FORMAT_MISMATCH", failureCodes);
  erv2PredeploymentRequire_(result.asset_integrity_state_ok, "ASSET_INTEGRITY_STATE_MISMATCH", failureCodes);
  erv2PredeploymentRequire_(result.asset_folder_property_present, "ASSET_FOLDER_PROPERTY_MISSING", failureCodes);
  erv2PredeploymentRequire_(result.asset_folder_binding_matches, "ASSET_FOLDER_BINDING_MISMATCH", failureCodes);
  erv2PredeploymentRequire_(result.reviewer_a_present, "REVIEWER_A_MISSING_OR_DUPLICATE", failureCodes);
  erv2PredeploymentRequire_(result.reviewer_b_present, "REVIEWER_B_MISSING_OR_DUPLICATE", failureCodes);
  erv2PredeploymentRequire_(result.reviewer_a_active === false, "REVIEWER_A_ACTIVE", failureCodes);
  erv2PredeploymentRequire_(result.reviewer_b_active === false, "REVIEWER_B_ACTIVE", failureCodes);
  erv2PredeploymentRequire_(result.assignment_counts_ok, "ASSIGNMENT_COUNTS_MISMATCH", failureCodes);
  erv2PredeploymentRequire_(result.review_responses === 0, "REVIEW_RESPONSES_NOT_EMPTY", failureCodes);
  erv2PredeploymentRequire_(result.review_sessions_v2 === 0, "REVIEW_SESSIONS_V2_NOT_EMPTY", failureCodes);
  erv2PredeploymentRequire_(
    result.launch_gate_status === ERV2_PREDEPLOYMENT_EXPECTED_.expectedLaunchGateStatus,
    "LAUNCH_GATE_STATUS_MISMATCH",
    failureCodes
  );
  erv2PredeploymentRequire_(
    result.review_start_enabled === ERV2_PREDEPLOYMENT_EXPECTED_.expectedReviewStartEnabled,
    "REVIEW_START_ENABLED_MISMATCH",
    failureCodes
  );
  erv2PredeploymentRequire_(result.live_writes_performed === false, "LIVE_WRITE_DETECTED", failureCodes);
}

function erv2PredeploymentRequire_(condition, code, failureCodes) {
  if (!condition) failureCodes.push(code);
}

function erv2PredeploymentError_(code) {
  const error = new Error(code);
  error.code = code;
  return error;
}

function erv2PredeploymentSafeErrorCode_(error) {
  const code = error && error.code ? String(error.code) : "PREDEPLOYMENT_CHECK_EXCEPTION";
  return /^[A-Z0-9_]+$/.test(code) ? code : "PREDEPLOYMENT_CHECK_EXCEPTION";
}
