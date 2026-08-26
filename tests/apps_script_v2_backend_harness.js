const assert = require("assert");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "..");
const SCRIPT = path.join(ROOT, "docs", "anchor-review-small-16-32-64-128", "google-apps-script", "ExpertReviewV2.gs");

class FakeRange {
  constructor(sheet, row, column, rows, columns) {
    this.sheet = sheet;
    this.row = row;
    this.column = column;
    this.rows = rows || 1;
    this.columns = columns || 1;
  }

  getDisplayValues() {
    return this._read().map((row) => row.map((value) => String(value ?? "")));
  }

  getValues() {
    return this._read();
  }

  setValues(values) {
    for (let rowIndex = 0; rowIndex < values.length; rowIndex += 1) {
      const targetRow = this.row - 1 + rowIndex;
      this.sheet.ensureRow(targetRow);
      for (let columnIndex = 0; columnIndex < values[rowIndex].length; columnIndex += 1) {
        this.sheet.rows[targetRow][this.column - 1 + columnIndex] = values[rowIndex][columnIndex];
      }
    }
  }

  setValue(value) {
    this.setValues([[value]]);
  }

  _read() {
    const result = [];
    for (let rowIndex = 0; rowIndex < this.rows; rowIndex += 1) {
      const sourceRow = this.sheet.rows[this.row - 1 + rowIndex] || [];
      const out = [];
      for (let columnIndex = 0; columnIndex < this.columns; columnIndex += 1) {
        out.push(sourceRow[this.column - 1 + columnIndex] ?? "");
      }
      result.push(out);
    }
    return result;
  }
}

class FakeDataRange {
  constructor(sheet) {
    this.sheet = sheet;
  }

  getDisplayValues() {
    return this.sheet.rows.map((row) => row.map((value) => String(value ?? "")));
  }
}

class FakeSheet {
  constructor(name, header, rows = []) {
    this.name = name;
    this.rows = [header.slice()].concat(rows.map((row) => header.map((column) => row[column] ?? "")));
  }

  getLastRow() {
    return this.rows.length;
  }

  getLastColumn() {
    return this.rows.reduce((max, row) => Math.max(max, row.length), 0);
  }

  getRange(row, column, rows, columns) {
    return new FakeRange(this, row, column, rows, columns);
  }

  getDataRange() {
    return new FakeDataRange(this);
  }

  appendRow(values) {
    this.rows.push(values.slice());
  }

  ensureRow(rowIndex) {
    while (this.rows.length <= rowIndex) this.rows.push([]);
  }
}

class FakeSpreadsheet {
  constructor(sheets) {
    this.sheets = sheets;
  }

  getSheetByName(name) {
    return this.sheets[name] || null;
  }
}

class FakeBlob {
  constructor(bytes) {
    this.bytes = Buffer.from(bytes);
  }

  getBytes() {
    return Array.from(this.bytes).map((byte) => (byte > 127 ? byte - 256 : byte));
  }
}

class FakeFile {
  constructor(name, mimeType, bytes, id = "hidden-file-id") {
    this.name = name;
    this.mimeType = mimeType;
    this.bytes = Buffer.from(bytes);
    this.id = id;
  }

  getName() {
    return this.name;
  }

  getMimeType() {
    return this.mimeType;
  }

  getBlob() {
    return new FakeBlob(this.bytes);
  }

  getId() {
    return this.id;
  }

  getUrl() {
    return `https://drive.google.com/file/d/${this.id}/view`;
  }
}

class FakeIterator {
  constructor(items) {
    this.items = items.slice();
    this.index = 0;
  }

  hasNext() {
    return this.index < this.items.length;
  }

  next() {
    return this.items[this.index++];
  }
}

class FakeFolder {
  constructor(name, files) {
    this.name = name;
    this.files = files.slice();
    this.getFilesByNameCount = 0;
  }

  getName() {
    return this.name;
  }

  getFiles() {
    return new FakeIterator(this.files);
  }

  getFilesByName(name) {
    this.getFilesByNameCount += 1;
    return new FakeIterator(this.files.filter((file) => file.getName() === name));
  }
}

class FakeProperties {
  constructor() {
    this.values = {};
  }

  getProperty(key) {
    return this.values[key] || "";
  }

  setProperty(key, value) {
    this.values[key] = String(value);
  }

  deleteProperty(key) {
    delete this.values[key];
  }
}

function loadBackend() {
  const code = fs.readFileSync(SCRIPT, "utf8");
  const lockStats = { waitLock: 0, releaseLock: 0 };
  const scriptProperties = new FakeProperties();
  const context = {
    console,
    Date,
    Error,
    JSON,
    Number,
    Object,
    Set,
    String,
    Boolean,
    __lockStats: lockStats,
    __scriptProperties: scriptProperties,
    LockService: {
      getScriptLock() {
        return {
          waitLock() {
            lockStats.waitLock += 1;
          },
          releaseLock() {
            lockStats.releaseLock += 1;
          },
        };
      },
    },
    PropertiesService: {
      getScriptProperties() {
        return scriptProperties;
      },
    },
    Utilities: {
      DigestAlgorithm: { SHA_256: "SHA_256" },
      computeDigest(_algorithm, value) {
        let input;
        if (Array.isArray(value)) {
          input = Buffer.from(value.map((byte) => (byte + 256) % 256));
        } else if (Buffer.isBuffer(value)) {
          input = value;
        } else {
          input = Buffer.from(String(value));
        }
        return Array.from(crypto.createHash("sha256").update(input).digest()).map((byte) => (byte > 127 ? byte - 256 : byte));
      },
      base64Encode(value) {
        if (Array.isArray(value)) return Buffer.from(value.map((byte) => (byte + 256) % 256)).toString("base64");
        return Buffer.from(value).toString("base64");
      },
    },
  };
  vm.createContext(context);
  vm.runInContext(`${code}
this.__erv2 = {
  __lockStats,
  __scriptProperties,
  ERV2_HEADERS,
  ERV2_FORBIDDEN_REVIEWER_FIELDS,
  handleExpertReviewV2Post,
  erv2VerifyDriveAssetInventory_,
  erv2VerifyDriveAssetHashesBatch_,
  resetExpertReviewV2DriveAssetVerification,
  erv2ReadRows_,
  erv2SafeCasePayload_
};`, context, { filename: SCRIPT });
  context.__erv2.__lockStats = lockStats;
  context.__erv2.__scriptProperties = scriptProperties;
  return context.__erv2;
}

function row(header, values) {
  return Object.assign(Object.fromEntries(header.map((key) => [key, ""])), values);
}

function buildSpreadsheet(active = true) {
  const c = loadBackend();
  const casesHeader = c.ERV2_HEADERS.ReviewCases;
  const assignmentsHeader = c.ERV2_HEADERS.ReviewAssignments;
  const responsesHeader = c.ERV2_HEADERS.ReviewResponses;
  const sessionsHeader = c.ERV2_HEADERS.ReviewSessionsV2;
  const reviewersHeader = c.ERV2_HEADERS.Reviewers;

  const caseRows = [];
  for (let index = 1; index <= 1169; index += 1) {
    caseRows.push(row(casesHeader, {
      case_id: `CASE_${String(index).padStart(4, "0")}`,
      case_index: String(index),
      batch_id: `B${String(Math.ceil(index / 75)).padStart(3, "0")}`,
      batch_position: String(((index - 1) % 75) + 1),
      review_order: String(index),
      review_asset_ref: `asset:EXPERT-REVIEW-R1:CASE_${String(index).padStart(4, "0")}`,
      asset_sha256: crypto.createHash("sha256").update(`asset-${index}`).digest("hex"),
      package_id: "EXPERT-REVIEW-R1",
      case_status: "PENDING",
      definition_version: "annotation_definition_v1",
    }));
  }

  const assignmentRows = [];
  for (let index = 1; index <= 1169; index += 1) {
    assignmentRows.push(row(assignmentsHeader, {
      assignment_id: `A_${index}`,
      case_id: `CASE_${String(index).padStart(4, "0")}`,
      reviewer_id: "REV_A",
      reviewer_role: "PRIMARY",
      assignment_group: "REV_A",
      batch_id: `B${String(Math.ceil(index / 75)).padStart(3, "0")}`,
      review_order: String(index),
      required: "TRUE",
      assigned_at: "2026-08-24T00:00:00.000Z",
      assignment_status: "PENDING",
    }));
  }
  for (let index = 1; index <= 292; index += 1) {
    assignmentRows.push(row(assignmentsHeader, {
      assignment_id: `B_${index}`,
      case_id: `CASE_${String(index).padStart(4, "0")}`,
      reviewer_id: "REV_B",
      reviewer_role: "RELIABILITY",
      assignment_group: "REV_B",
      batch_id: `B${String(Math.ceil(index / 75)).padStart(3, "0")}`,
      review_order: String(index),
      required: "TRUE",
      assigned_at: "2026-08-24T00:00:00.000Z",
      assignment_status: "PENDING",
    }));
  }

  const reviewerRows = [
    row(reviewersHeader, {
      reviewer_id: "REV_A",
      reviewer_role: "PRIMARY",
      active: active ? "TRUE" : "FALSE",
      review_mode: "PRIMARY_PLUS_RELIABILITY_SUBSET",
      assignment_group: "REV_A",
    }),
    row(reviewersHeader, {
      reviewer_id: "REV_B",
      reviewer_role: "RELIABILITY",
      active: active ? "TRUE" : "FALSE",
      review_mode: "PRIMARY_PLUS_RELIABILITY_SUBSET",
      assignment_group: "REV_B",
    }),
  ];

  const configRows = [
    ["package_id", "EXPERT-REVIEW-R1"],
    ["reviewer_setup_status", "REVIEWER_SETUP_FROZEN_NOT_LAUNCHED"],
    ["review_mode", "PRIMARY_PLUS_RELIABILITY_SUBSET"],
    ["reviewer_setup_freeze_sha256", "eaf492d93f0fea9f67de884bf646af5db08e6fb4ee13fc9018757c191f494dbf"],
    ["review_start_enabled", "FALSE"],
    ["launch_gate_status", "BLOCKED"],
  ];

  const spreadsheet = new FakeSpreadsheet({
    ReviewCases: new FakeSheet("ReviewCases", casesHeader, caseRows),
    ReviewAssignments: new FakeSheet("ReviewAssignments", assignmentsHeader, assignmentRows),
    ReviewResponses: new FakeSheet("ReviewResponses", responsesHeader, []),
    ReviewSessionsV2: new FakeSheet("ReviewSessionsV2", sessionsHeader, []),
    Reviewers: new FakeSheet("Reviewers", reviewersHeader, reviewerRows),
    ConfigV2: new FakeSheet("ConfigV2", ["key", "value"], configRows.map(([key, value]) => ({ key, value }))),
  });
  return { c, spreadsheet };
}

function buildDriveFolder({ name = "EXPERT-REVIEW-R1_ReviewerAssets_Private", missing = [], extra = [], duplicates = [], invalidMime = [], hashMismatch = [] } = {}) {
  const skip = new Set(missing);
  const badMime = new Set(invalidMime);
  const badHash = new Set(hashMismatch);
  const duplicateSet = new Set(duplicates);
  const files = [];
  for (let index = 1; index <= 1169; index += 1) {
    const caseId = `CASE_${String(index).padStart(4, "0")}`;
    if (skip.has(caseId)) continue;
    const bytes = badHash.has(caseId) ? `corrupt-${index}` : `asset-${index}`;
    files.push(new FakeFile(`${caseId}.jpg`, badMime.has(caseId) ? "text/plain" : "image/jpeg", bytes, `drive-${caseId}`));
    if (duplicateSet.has(caseId)) {
      files.push(new FakeFile(`${caseId}.jpg`, "image/jpeg", bytes, `drive-duplicate-${caseId}`));
    }
  }
  for (const filename of extra) {
    files.push(new FakeFile(filename, "image/jpeg", "extra", "drive-extra"));
  }
  return new FakeFolder(name, files);
}

function call(env, reviewerId, payload, extraOptions = {}) {
  return env.c.handleExpertReviewV2Post(
    Object.assign({ dryRun: true, clientVersion: "test-client" }, payload),
    Object.assign({
      allowDryRun: true,
      spreadsheet: env.spreadsheet,
      testReviewerIdentity: { reviewer_id: reviewerId },
    }, extraOptions),
  );
}

function assertOk(result) {
  assert.strictEqual(result.ok, true, JSON.stringify(result));
  return result;
}

function assertError(result, code) {
  assert.strictEqual(result.ok, false, JSON.stringify(result));
  assert.strictEqual(result.error.code, code, JSON.stringify(result));
}

function main() {
  let env = buildSpreadsheet(true);

  const bootA = assertOk(call(env, "REV_A", { action: "V2_GET_BOOTSTRAP" }));
  assert.strictEqual(bootA.assigned_count, 1169, "A. REV_A sees 1169 assignments");
  const bootB = assertOk(call(env, "REV_B", { action: "V2_GET_BOOTSTRAP" }));
  assert.strictEqual(bootB.assigned_count, 292, "B. REV_B sees 292 assignments");

  const loadA = assertOk(call(env, "REV_A", { action: "V2_LOAD_PROGRESS" }));
  assert(loadA.assignments.every((item) => item.reviewer_role === "PRIMARY"), "C. REV_A cannot access REV_B-only context");
  const loadB = assertOk(call(env, "REV_B", { action: "V2_LOAD_PROGRESS" }));
  assert(loadB.assignments.every((item) => item.reviewer_role === "RELIABILITY"), "D. REV_B isolated role only");
  assert(!JSON.stringify(loadB).includes("assigned_reviewer_count"), "D. REV_B cannot infer dual review");
  assert(!JSON.stringify(loadB).includes("asset_sha256"), "D. reviewer bootstrap/load does not expose asset SHA");
  assert(!JSON.stringify(loadB).includes("review_asset_ref"), "D. reviewer bootstrap/load does not expose source asset ref");

  assertError(call(env, "REV_A", {
    action: "V2_LOAD_PROGRESS",
    caseId: "CASE_9999",
  }), "CASE_NOT_ASSIGNED");

  assertError(call(env, "REV_A", {
    action: "V2_SAVE_DRAFT",
    sessionId: "S1",
    caseId: "CASE_0001",
    decision: "BAD",
    confidence: "HIGH",
  }), "INVALID_DECISION");

  assertError(call(env, "REV_A", {
    action: "V2_SAVE_DRAFT",
    sessionId: "S1",
    caseId: "CASE_0001",
    decision: "AMBIGUOUS",
    confidence: "BAD",
  }), "INVALID_CONFIDENCE");

  const draft = assertOk(call(env, "REV_A", {
    action: "V2_SAVE_DRAFT",
    sessionId: "S1",
    caseId: "CASE_0001",
    decision: "AMBIGUOUS",
    confidence: "LOW",
    comment: "draft one",
    stateJson: { current: "CASE_0001" },
  }));
  assert.strictEqual(draft.response_status, "DRAFT", "H. draft save works");
  const resumed = assertOk(call(env, "REV_A", { action: "V2_LOAD_PROGRESS" }));
  assert.strictEqual(resumed.session.state_version, 1, "H. resume returns session state");

  assertError(call(env, "REV_A", {
    action: "V2_SAVE_DRAFT",
    sessionId: "S1",
    caseId: "CASE_0001",
    decision: "AMBIGUOUS",
    confidence: "LOW",
    baseStateVersion: 0,
  }), "STALE_STATE");

  const submit = assertOk(call(env, "REV_A", {
    action: "V2_SUBMIT_RESPONSE",
    sessionId: "S1",
    caseId: "CASE_0001",
    decision: "AMBIGUOUS",
    confidence: "LOW",
    comment: "draft one",
    baseStateVersion: 1,
  }));
  assert.strictEqual(submit.response_status, "SUBMITTED", "J. first submit succeeds");

  const dup = assertOk(call(env, "REV_A", {
    action: "V2_SUBMIT_RESPONSE",
    sessionId: "S1",
    caseId: "CASE_0001",
    decision: "AMBIGUOUS",
    confidence: "LOW",
    comment: "draft one",
    baseStateVersion: 2,
  }));
  assert.strictEqual(dup.idempotent, true, "K. duplicate identical submit is idempotent");

  assertError(call(env, "REV_A", {
    action: "V2_SAVE_DRAFT",
    sessionId: "S1",
    caseId: "CASE_0001",
    decision: "NOT_DIRTY_SPOT",
    confidence: "HIGH",
    baseStateVersion: 2,
  }), "RESPONSE_ALREADY_SUBMITTED");

  const unsafe = env.c.erv2SafeCasePayload_(Object.assign({}, env.c.erv2ReadRows_(env.spreadsheet.getSheetByName("ReviewCases"), env.c.ERV2_HEADERS.ReviewCases)[0], {
    stratum: "secret",
    e22_classification: "secret",
    prediction_score: "0.9",
    bbox_x1: "1",
    bbox_y1: "2",
    bbox_x2: "3",
    bbox_y2: "4",
    source_id: "source",
    tile_id: "tile",
    researcher_notes: "notes",
  }));
  for (const field of env.c.ERV2_FORBIDDEN_REVIEWER_FIELDS) {
    assert(!(field in unsafe), `M. researcher-only metadata hidden: ${field}`);
  }

  env = buildSpreadsheet(true);
  const productionBlocked = env.c.handleExpertReviewV2Post(
    { action: "V2_GET_BOOTSTRAP" },
    { spreadsheet: env.spreadsheet, testReviewerIdentity: { reviewer_id: "REV_A" } },
  );
  assertError(productionBlocked, "REVIEW_NOT_LAUNCHED");

  env = buildSpreadsheet(true);
  assertError(call(env, "REV_A", {
    action: "V2_GET_CASE_ASSET",
    caseId: "CASE_0001",
  }), "ASSET_FOLDER_NOT_CONFIGURED");

  const goodFolder = buildDriveFolder();
  const inventory = env.c.erv2VerifyDriveAssetInventory_({
    spreadsheet: env.spreadsheet,
    assetFolderId: "test-folder-id",
    assetFolder: goodFolder,
  });
  assertOk(inventory);
  assert.strictEqual(inventory.status, "DRIVE_ASSET_INVENTORY_VERIFIED", "B. expected private folder identity accepted");

  const wrongFolder = buildDriveFolder({ name: "Wrong" });
  assertError(env.c.erv2VerifyDriveAssetInventory_({
    spreadsheet: env.spreadsheet,
    assetFolderId: "test-folder-id",
    assetFolder: wrongFolder,
  }), "ASSET_FOLDER_NAME_MISMATCH");

  const asset = assertOk(call(env, "REV_A", {
    action: "V2_GET_CASE_ASSET",
    caseId: "CASE_0001",
  }, {
    assetFolderId: "test-folder-id",
    assetFolder: goodFolder,
  }));
  assert.strictEqual(asset.asset.case_id, "CASE_0001", "D/I/K. exact case filename resolves and hash match accepted");
  assert.strictEqual(asset.asset.mime_type, "image/jpeg");
  assert.strictEqual(asset.asset.data_base64, Buffer.from("asset-1").toString("base64"));
  const assetJson = JSON.stringify(asset);
  for (const forbidden of ["drive_file_id", "drive_folder_id", "drive_url", "webViewLink", "asset_sha256", "ResearcherCaseMeta", "source_asset_ref", "folder_id", "file_id"]) {
    assert(!assetJson.includes(forbidden), `M-Q. asset response does not expose ${forbidden}`);
  }

  assertError(call(env, "REV_A", {
    action: "V2_GET_CASE_ASSET",
    caseId: "CASE_0001",
  }, {
    assetFolderId: "test-folder-id",
    assetFolder: buildDriveFolder({ missing: ["CASE_0001"] }),
  }), "ASSET_NOT_FOUND");

  assertError(call(env, "REV_A", {
    action: "V2_GET_CASE_ASSET",
    caseId: "CASE_0001",
  }, {
    assetFolderId: "test-folder-id",
    assetFolder: buildDriveFolder({ duplicates: ["CASE_0001"] }),
  }), "ASSET_DUPLICATE");

  assertError(call(env, "REV_A", {
    action: "V2_GET_CASE_ASSET",
    caseId: "CASE_0001",
  }, {
    assetFolderId: "test-folder-id",
    assetFolder: buildDriveFolder({ invalidMime: ["CASE_0001"] }),
  }), "ASSET_INVALID_MIME");

  assertError(call(env, "REV_A", {
    action: "V2_GET_CASE_ASSET",
    caseId: "CASE_0001",
  }, {
    assetFolderId: "test-folder-id",
    assetFolder: buildDriveFolder({ hashMismatch: ["CASE_0001"] }),
  }), "ASSET_INTEGRITY_MISMATCH");

  const unreadFolder = buildDriveFolder();
  assertError(call(env, "REV_A", {
    action: "V2_GET_CASE_ASSET",
    caseId: "CASE_9999",
  }, {
    assetFolderId: "test-folder-id",
    assetFolder: unreadFolder,
  }), "CASE_NOT_ASSIGNED");
  assert.strictEqual(unreadFolder.getFilesByNameCount, 0, "J. unassigned reviewer rejected before asset read");

  const bAsset = assertOk(call(env, "REV_B", {
    action: "V2_GET_CASE_ASSET",
    caseId: "CASE_0002",
  }, {
    assetFolderId: "test-folder-id",
    assetFolder: goodFolder,
  }));
  assert.strictEqual(bAsset.asset.case_id, "CASE_0002", "L. REV_B can access B-assigned mocked case");

  const productionAssetBlocked = env.c.handleExpertReviewV2Post(
    { action: "V2_GET_CASE_ASSET", caseId: "CASE_0001" },
    {
      spreadsheet: env.spreadsheet,
      testReviewerIdentity: { reviewer_id: "REV_A" },
      assetFolderId: "test-folder-id",
      assetFolder: goodFolder,
    },
  );
  assertError(productionAssetBlocked, "REVIEW_NOT_LAUNCHED");

  const badInventory = env.c.erv2VerifyDriveAssetInventory_({
    spreadsheet: env.spreadsheet,
    assetFolderId: "test-folder-id",
    assetFolder: buildDriveFolder({ missing: ["CASE_0001"], extra: ["EXTRA.jpg"], duplicates: ["CASE_0002"] }),
  });
  assert.strictEqual(badInventory.ok, false, "S. inventory verifier detects missing/extra/duplicate");
  assert.strictEqual(badInventory.missing, 1);
  assert.strictEqual(badInventory.extra, 1);
  assert.strictEqual(badInventory.duplicates, 1);

  const props = new FakeProperties();
  const lockStart = env.c.__lockStats.waitLock;
  const batch1 = env.c.erv2VerifyDriveAssetHashesBatch_({
    spreadsheet: env.spreadsheet,
    assetFolderId: "test-folder-id",
    assetFolder: goodFolder,
    properties: props,
    batchSize: 10,
  });
  assert.strictEqual(batch1.cursor, 10, "T. first hash batch advances cursor");
  assert.strictEqual(batch1.status, "DRIVE_ASSET_SHA256_BATCH_IN_PROGRESS");
  assert(env.c.__lockStats.waitLock > lockStart, "11. hash batch uses Script Lock");
  const batch2 = env.c.erv2VerifyDriveAssetHashesBatch_({
    spreadsheet: env.spreadsheet,
    assetFolderId: "test-folder-id",
    assetFolder: goodFolder,
    properties: props,
    batchSize: 10,
  });
  assert.strictEqual(batch2.cursor, 20, "T. second hash batch resumes cursor");

  const mismatchProps = new FakeProperties();
  const mismatchBatch1 = env.c.erv2VerifyDriveAssetHashesBatch_({
    spreadsheet: env.spreadsheet,
    assetFolderId: "test-folder-id",
    assetFolder: buildDriveFolder({ hashMismatch: ["CASE_0001"] }),
    properties: mismatchProps,
    batchSize: 1,
  });
  assert.strictEqual(mismatchBatch1.mismatches, 1, "4/9. first batch records cumulative mismatch");
  assert.strictEqual(mismatchBatch1.failed, 1);
  assert.strictEqual(mismatchBatch1.batch_failures.length, 1);
  const mismatchFinal = env.c.erv2VerifyDriveAssetHashesBatch_({
    spreadsheet: env.spreadsheet,
    assetFolderId: "test-folder-id",
    assetFolder: goodFolder,
    properties: mismatchProps,
    batchSize: 2000,
  });
  assert.strictEqual(mismatchFinal.status, "DRIVE_ASSET_FULL_SHA256_FAILED", "6. earlier failure survives final status");
  assert.strictEqual(mismatchFinal.remaining, 0, "8. final remaining is zero");
  assert.strictEqual(mismatchFinal.mismatches, 1, "5/9. cumulative mismatch count preserved");
  assert.strictEqual(mismatchFinal.failed, 1);
  assert.strictEqual(mismatchFinal.batch_failures.length, 0, "batch failures are local to invocation");

  const successFinal = env.c.erv2VerifyDriveAssetHashesBatch_({
    spreadsheet: env.spreadsheet,
    assetFolderId: "success-folder-id",
    assetFolder: goodFolder,
    properties: new FakeProperties(),
    batchSize: 2000,
  });
  assert.strictEqual(successFinal.status, "DRIVE_ASSET_FULL_SHA256_VERIFIED", "7. successful final completion is verified");
  assert.strictEqual(successFinal.remaining, 0);
  assert.strictEqual(successFinal.failed, 0);

  const categoryProps = new FakeProperties();
  env.c.erv2VerifyDriveAssetHashesBatch_({
    spreadsheet: env.spreadsheet,
    assetFolderId: "category-folder-id",
    assetFolder: buildDriveFolder({
      hashMismatch: ["CASE_0001"],
      missing: ["CASE_0002"],
      duplicates: ["CASE_0003"],
      invalidMime: ["CASE_0004"],
    }),
    properties: categoryProps,
    batchSize: 4,
  });
  const categoryFinal = env.c.erv2VerifyDriveAssetHashesBatch_({
    spreadsheet: env.spreadsheet,
    assetFolderId: "category-folder-id",
    assetFolder: goodFolder,
    properties: categoryProps,
    batchSize: 2000,
  });
  assert.strictEqual(categoryFinal.mismatches, 1, "9. cumulative mismatch counter");
  assert.strictEqual(categoryFinal.missing, 1, "9. cumulative missing counter");
  assert.strictEqual(categoryFinal.duplicates, 1, "9. cumulative duplicate counter");
  assert.strictEqual(categoryFinal.invalid_mime, 1, "9. cumulative MIME counter");

  const changedFolder = env.c.erv2VerifyDriveAssetHashesBatch_({
    spreadsheet: env.spreadsheet,
    assetFolderId: "different-folder-id",
    assetFolder: goodFolder,
    properties: props,
    batchSize: 10,
  });
  assertError(changedFolder, "ASSET_VERIFICATION_STATE_MISMATCH");

  const resetProps = env.c.__scriptProperties;
  for (const key of [
    "ERV2_ASSET_VERIFY_CURSOR",
    "ERV2_ASSET_VERIFY_PASS_COUNT",
    "ERV2_ASSET_VERIFY_FAIL_COUNT",
    "ERV2_ASSET_VERIFY_MISMATCH_COUNT",
    "ERV2_ASSET_VERIFY_MISSING_COUNT",
    "ERV2_ASSET_VERIFY_DUPLICATE_COUNT",
    "ERV2_ASSET_VERIFY_INVALID_MIME_COUNT",
    "ERV2_ASSET_VERIFY_INTERNAL_ERROR_COUNT",
    "ERV2_ASSET_VERIFY_FOLDER_ID",
    "ERV2_ASSET_VERIFY_STARTED_AT",
  ]) {
    resetProps.setProperty(key, "x");
  }
  assertOk(env.c.resetExpertReviewV2DriveAssetVerification());
  for (const key of [
    "ERV2_ASSET_VERIFY_CURSOR",
    "ERV2_ASSET_VERIFY_PASS_COUNT",
    "ERV2_ASSET_VERIFY_FAIL_COUNT",
    "ERV2_ASSET_VERIFY_MISMATCH_COUNT",
    "ERV2_ASSET_VERIFY_MISSING_COUNT",
    "ERV2_ASSET_VERIFY_DUPLICATE_COUNT",
    "ERV2_ASSET_VERIFY_INVALID_MIME_COUNT",
    "ERV2_ASSET_VERIFY_INTERNAL_ERROR_COUNT",
    "ERV2_ASSET_VERIFY_FOLDER_ID",
    "ERV2_ASSET_VERIFY_STARTED_AT",
  ]) {
    assert.strictEqual(resetProps.getProperty(key), "", `10. reset clears ${key}`);
  }

  const legacyCode = fs.readFileSync(path.join(ROOT, "docs", "anchor-review-small-16-32-64-128", "google-apps-script", "Code.gs"), "utf8");
  assert(legacyCode.includes('payload.action === "LOAD_PROGRESS"'), "O. legacy LOAD_PROGRESS route remains");
  assert(legacyCode.includes('payload.action === "SAVE_PROGRESS"'), "O. legacy SAVE_PROGRESS route remains");
  assert(legacyCode.includes('payload.action === "SUBMIT_FINAL"'), "O. legacy SUBMIT_FINAL route remains");

  console.log("APPS_SCRIPT_V2_BACKEND_HARNESS_PASS");
}

main();
