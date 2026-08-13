const SPREADSHEET_ID = "PASTE_TARGET_SPREADSHEET_ID_HERE";
const REVIEW_SITE_ORIGIN = "https://suwaroj95-spec.github.io";

const EXPECTED_IDENTITY = {
  package_id: "package_a_small_anchor_0125",
  model_profile: "small_16_32_64_128",
  checkpoint_sha256: "e9f4d2e1b8530662fd3390165419008647c7d9baaf80e8a2d3cc4108b22fa7c0",
  threshold: "0.125",
  card_count: "1400",
  page_count: "70",
};

const SESSION_COLUMNS = [
  "session_id",
  "reviewer_name",
  "package_id",
  "model_profile",
  "checkpoint_sha256",
  "threshold",
  "manifest_identifier",
  "started_at",
  "last_saved_at",
  "submitted_at",
  "page_count",
  "card_count",
  "reviewed_pages",
  "completed_cards",
  "accepted",
  "false_positive",
  "pairing_error",
  "uncertain",
  "remaining",
  "submission_status",
  "client_version",
];

const RESULT_COLUMNS = [
  "session_id",
  "reviewer_name",
  "package_id",
  "model_profile",
  "checkpoint_sha256",
  "threshold",
  "manifest_identifier",
  "card_id",
  "card_index",
  "page",
  "position",
  "source_id",
  "prediction_id",
  "score",
  "bbox_x1",
  "bbox_y1",
  "bbox_x2",
  "bbox_y2",
  "reviewer_selection",
  "review_status",
  "final_classification",
  "page_completed",
  "page_completed_at",
  "review_updated_at",
  "submitted_at",
];

const FINAL_CLASSIFICATIONS = {
  HUMAN_ACCEPTED_TRUE_POSITIVE: true,
  FALSE_POSITIVE_BY_EXPERT: true,
  PAIRING_ERROR: true,
  UNRESOLVED: true,
  NOT_REVIEWED: true,
};

function doGet() {
  return jsonResponse({
    ok: true,
    service: "Pics-BirdNests Expert Review Google Sheets bridge",
    spreadsheetId: SPREADSHEET_ID,
    reviewSiteOrigin: REVIEW_SITE_ORIGIN,
  });
}

function doOptions() {
  return jsonResponse({ ok: true });
}

function doPost(event) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const payload = parsePayload(event);
    const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
    const config = readConfigMap(spreadsheet);

    validatePayloadShape(payload);
    validateIdentity(payload, config);

    if (payload.action === "SAVE_PROGRESS") {
      const result = saveProgress(spreadsheet, payload);
      return jsonResponse({
        ok: true,
        action: payload.action,
        sessionId: payload.sessionId,
        message: "Progress saved to ReviewSessions.",
        result,
      });
    }

    if (payload.action === "SUBMIT_FINAL") {
      const result = submitFinal(spreadsheet, payload);
      return jsonResponse({
        ok: true,
        action: payload.action,
        sessionId: payload.sessionId,
        message: "Final review submitted to ReviewSessions and ReviewResults.",
        result,
      });
    }

    throw userError("UNKNOWN_ACTION", "Unsupported action.");
  } catch (error) {
    return jsonResponse({
      ok: false,
      code: error.code || "SERVER_ERROR",
      message: error.message || String(error),
    });
  } finally {
    lock.releaseLock();
  }
}

function parsePayload(event) {
  const text = event && event.postData && event.postData.contents;
  if (!text) throw userError("EMPTY_BODY", "Request body is empty.");
  try {
    return JSON.parse(text);
  } catch (_error) {
    throw userError("INVALID_JSON", "Request body must be valid JSON.");
  }
}

function validatePayloadShape(payload) {
  if (!payload || typeof payload !== "object") throw userError("INVALID_PAYLOAD", "Payload must be an object.");
  if (!payload.sessionId) throw userError("MISSING_SESSION_ID", "session_id is required.");
  if (!payload.reviewerName) throw userError("MISSING_REVIEWER_NAME", "reviewer_name is required.");
  if (!payload.summary || typeof payload.summary !== "object") throw userError("MISSING_SUMMARY", "summary is required.");
  if (!payload.packageId || !payload.modelProfile || !payload.checkpointSha256) {
    throw userError("MISSING_IDENTITY", "package/model/checkpoint identity is required.");
  }
  if (String(payload.action) === "SUBMIT_FINAL") {
    if (!Array.isArray(payload.results)) throw userError("MISSING_RESULTS", "Final submit requires results.");
    if (payload.results.length !== Number(payload.summary.cardCount)) {
      throw userError("RESULT_COUNT_MISMATCH", "Final submit row count must match card_count.");
    }
    payload.results.forEach(function (row, index) {
      if (!FINAL_CLASSIFICATIONS[row.finalClassification]) {
        throw userError("INVALID_FINAL_CLASSIFICATION", "Unexpected final_classification at result index " + index + ".");
      }
    });
  }
}

function validateIdentity(payload, config) {
  const expected = {
    package_id: expectedConfig(config, "package_id"),
    model_profile: expectedConfig(config, "model_profile"),
    checkpoint_sha256: expectedConfig(config, "checkpoint_sha256"),
    threshold: expectedConfig(config, "threshold"),
    card_count: expectedConfig(config, "card_count"),
    page_count: expectedConfig(config, "page_count"),
  };

  assertEqual("package_id", payload.packageId, expected.package_id);
  assertEqual("model_profile", payload.modelProfile, expected.model_profile);
  assertEqual("checkpoint_sha256", payload.checkpointSha256, expected.checkpoint_sha256);
  assertEqual("threshold", Number(payload.threshold), Number(expected.threshold));
  assertEqual("card_count", Number(payload.summary.cardCount), Number(expected.card_count));
  assertEqual("page_count", Number(payload.summary.pageCount), Number(expected.page_count));
}

function saveProgress(spreadsheet, payload) {
  const sheet = getRequiredSheet(spreadsheet, "ReviewSessions");
  const header = ensureColumns(sheet, SESSION_COLUMNS);
  const rowObject = buildSessionRow(payload, "IN_PROGRESS");
  const rowNumber = findSessionRow(sheet, header, payload.sessionId);
  const values = rowToValues(header, rowObject);
  if (rowNumber) {
    sheet.getRange(rowNumber, 1, 1, header.length).setValues([values]);
    return { wrote: "updated", row: rowNumber };
  }
  sheet.appendRow(values);
  return { wrote: "inserted", row: sheet.getLastRow() };
}

function submitFinal(spreadsheet, payload) {
  const resultSheet = getRequiredSheet(spreadsheet, "ReviewResults");
  const resultHeader = ensureColumns(resultSheet, RESULT_COLUMNS);
  const existingCount = countRowsForSession(resultSheet, resultHeader, payload.sessionId);
  if (existingCount > 0 && !payload.overwriteResults) {
    throw userError("DUPLICATE_FINAL_SUBMISSION", "ReviewResults already has rows for this session_id. Re-submit with overwriteResults=true to replace them.");
  }
  if (existingCount > 0) deleteRowsForSession(resultSheet, resultHeader, payload.sessionId);

  const submittedAt = new Date().toISOString();
  const resultRows = payload.results.map(function (row) {
    return rowToValues(resultHeader, buildResultRow(payload, row, submittedAt));
  });
  if (resultRows.length) {
    resultSheet.getRange(resultSheet.getLastRow() + 1, 1, resultRows.length, resultHeader.length).setValues(resultRows);
  }

  const sessionSheet = getRequiredSheet(spreadsheet, "ReviewSessions");
  const sessionHeader = ensureColumns(sessionSheet, SESSION_COLUMNS);
  const sessionRowObject = buildSessionRow(payload, "SUBMITTED", submittedAt);
  const rowNumber = findSessionRow(sessionSheet, sessionHeader, payload.sessionId);
  const sessionValues = rowToValues(sessionHeader, sessionRowObject);
  if (rowNumber) {
    sessionSheet.getRange(rowNumber, 1, 1, sessionHeader.length).setValues([sessionValues]);
  } else {
    sessionSheet.appendRow(sessionValues);
  }

  return { resultsWritten: resultRows.length, overwrittenRows: existingCount };
}

function buildSessionRow(payload, status, submittedAt) {
  const summary = payload.summary;
  const now = new Date().toISOString();
  return {
    session_id: payload.sessionId,
    reviewer_name: payload.reviewerName,
    package_id: payload.packageId,
    model_profile: payload.modelProfile,
    checkpoint_sha256: payload.checkpointSha256,
    threshold: payload.threshold,
    manifest_identifier: payload.manifestIdentifier,
    started_at: payload.startedAt,
    last_saved_at: now,
    submitted_at: submittedAt || "",
    page_count: summary.pageCount,
    card_count: summary.cardCount,
    reviewed_pages: summary.reviewedPages,
    completed_cards: summary.completedCards,
    accepted: summary.accepted,
    false_positive: summary.falsePositive,
    pairing_error: summary.pairingError,
    uncertain: summary.uncertain,
    remaining: summary.remaining,
    submission_status: status,
    client_version: payload.clientVersion,
    reviewer_notes: payload.reviewerNotes || "",
  };
}

function buildResultRow(payload, row, submittedAt) {
  return {
    session_id: payload.sessionId,
    reviewer_name: payload.reviewerName,
    package_id: payload.packageId,
    model_profile: payload.modelProfile,
    checkpoint_sha256: payload.checkpointSha256,
    threshold: payload.threshold,
    manifest_identifier: payload.manifestIdentifier,
    card_id: row.cardId,
    card_index: row.cardIndex,
    page: row.page,
    position: row.position,
    source_id: row.sourceId,
    prediction_id: row.predictionId,
    score: row.score,
    bbox_x1: row.bboxX1,
    bbox_y1: row.bboxY1,
    bbox_x2: row.bboxX2,
    bbox_y2: row.bboxY2,
    reviewer_selection: row.reviewerSelection,
    review_status: row.reviewStatus,
    final_classification: row.finalClassification,
    page_completed: row.pageCompleted,
    page_completed_at: row.pageCompletedAt,
    review_updated_at: row.exportedAt,
    submitted_at: submittedAt,
  };
}

function getRequiredSheet(spreadsheet, name) {
  const sheet = spreadsheet.getSheetByName(name);
  if (!sheet) throw userError("MISSING_SHEET", "Missing sheet tab: " + name + ".");
  return sheet;
}

function ensureColumns(sheet, requiredColumns) {
  const lastColumn = Math.max(sheet.getLastColumn(), requiredColumns.length, 1);
  let header = sheet.getRange(1, 1, 1, lastColumn).getValues()[0].map(String);
  const hasHeader = header.some(function (value) { return value.trim(); });
  if (!hasHeader) {
    sheet.getRange(1, 1, 1, requiredColumns.length).setValues([requiredColumns]);
    return requiredColumns.slice();
  }
  requiredColumns.forEach(function (column) {
    if (header.indexOf(column) === -1) {
      header.push(column);
      sheet.getRange(1, header.length).setValue(column);
    }
  });
  return header;
}

function rowToValues(header, rowObject) {
  return header.map(function (column) {
    return Object.prototype.hasOwnProperty.call(rowObject, column) ? rowObject[column] : "";
  });
}

function findSessionRow(sheet, header, sessionId) {
  const index = header.indexOf("session_id");
  if (index === -1 || sheet.getLastRow() < 2) return 0;
  const values = sheet.getRange(2, index + 1, sheet.getLastRow() - 1, 1).getValues();
  for (let i = 0; i < values.length; i += 1) {
    if (String(values[i][0]) === String(sessionId)) return i + 2;
  }
  return 0;
}

function countRowsForSession(sheet, header, sessionId) {
  const index = header.indexOf("session_id");
  if (index === -1 || sheet.getLastRow() < 2) return 0;
  const values = sheet.getRange(2, index + 1, sheet.getLastRow() - 1, 1).getValues();
  return values.filter(function (row) { return String(row[0]) === String(sessionId); }).length;
}

function deleteRowsForSession(sheet, header, sessionId) {
  const index = header.indexOf("session_id");
  if (index === -1 || sheet.getLastRow() < 2) return;
  const values = sheet.getRange(2, index + 1, sheet.getLastRow() - 1, 1).getValues();
  for (let i = values.length - 1; i >= 0; i -= 1) {
    if (String(values[i][0]) === String(sessionId)) sheet.deleteRow(i + 2);
  }
}

function readConfigMap(spreadsheet) {
  const sheet = getRequiredSheet(spreadsheet, "Config");
  const values = sheet.getDataRange().getValues();
  const config = {};
  if (!values.length) return config;

  values.forEach(function (row) {
    if (row.length >= 2 && row[0]) config[normalizeKey(row[0])] = row[1];
  });

  if (values.length >= 2) {
    values[0].forEach(function (heading, index) {
      if (heading) config[normalizeKey(heading)] = values[1][index];
    });
  }
  return config;
}

function expectedConfig(config, key) {
  const value = config[normalizeKey(key)];
  return value === undefined || value === "" ? EXPECTED_IDENTITY[key] : value;
}

function normalizeKey(value) {
  return String(value || "").trim().toLowerCase();
}

function assertEqual(name, actual, expected) {
  if (String(actual) !== String(expected)) {
    throw userError("IDENTITY_MISMATCH", name + " mismatch. Expected " + expected + ", received " + actual + ".");
  }
}

function userError(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

function jsonResponse(value) {
  return ContentService
    .createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}
