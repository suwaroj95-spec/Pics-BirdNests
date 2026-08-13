const UI_STORAGE_SUFFIX = ":ui:v1";
const SHEETS_STORAGE_SUFFIX = ":sheets:v1";
const CLIENT_VERSION = "review-web-20260813-google-sheets-v1";
const DEFAULT_GOOGLE_SHEETS_WEB_APP_URL = "";
const SUBMISSION_ACTIONS = {
  saveProgress: "SAVE_PROGRESS",
  submitFinal: "SUBMIT_FINAL",
};

const state = {
  page: 1,
  data: null,
  cardsById: new Map(),
  review: {
    selections: {},
    completedPages: {},
    updatedAt: null,
  },
  ui: {
    mode: "overview",
    focusCardId: null,
    autoAdvance: false,
  },
  sheets: {
    endpointUrl: "",
    reviewerName: "",
    reviewerNotes: "",
    sessionId: "",
    startedAt: "",
    lastSyncedAt: "",
    finalSubmittedAt: "",
    status: "not_configured",
    message: "",
    isSubmitting: false,
  },
  modalCardId: null,
  toastTimer: null,
};

const els = {
  identityPanel: document.getElementById("identityPanel"),
  progressHero: document.getElementById("progressHero"),
  progressBar: document.getElementById("progressBar"),
  progressStrip: document.getElementById("progressStrip"),
  completionPanel: document.getElementById("completionPanel"),
  prevIncomplete: document.getElementById("prevIncomplete"),
  nextIncomplete: document.getElementById("nextIncomplete"),
  downloadCsv: document.getElementById("downloadCsv"),
  downloadJson: document.getElementById("downloadJson"),
  importJson: document.getElementById("importJson"),
  importFile: document.getElementById("importFile"),
  clearReview: document.getElementById("clearReview"),
  sheetsEndpoint: document.getElementById("sheetsEndpoint"),
  reviewerName: document.getElementById("reviewerName"),
  reviewerNotes: document.getElementById("reviewerNotes"),
  saveProgressSheets: document.getElementById("saveProgressSheets"),
  submitFinalSheets: document.getElementById("submitFinalSheets"),
  sheetsStatus: document.getElementById("sheetsStatus"),
  sheetsLastSync: document.getElementById("sheetsLastSync"),
  sheetsWarning: document.getElementById("sheetsWarning"),
  overviewMode: document.getElementById("overviewMode"),
  focusMode: document.getElementById("focusMode"),
  pageSelect: document.getElementById("pageSelect"),
  prevPage: document.getElementById("prevPage"),
  nextPage: document.getElementById("nextPage"),
  currentPageLabel: document.getElementById("currentPageLabel"),
  directLink: document.getElementById("directLink"),
  pageComplete: document.getElementById("pageComplete"),
  pageCompleteLabel: document.getElementById("pageCompleteLabel"),
  autoAdvance: document.getElementById("autoAdvance"),
  reviewImage: document.getElementById("reviewImage"),
  pageMeta: document.getElementById("pageMeta"),
  cardLayer: document.getElementById("cardLayer"),
  overviewPanel: document.getElementById("overviewPanel"),
  focusPanel: document.getElementById("focusPanel"),
  focusTitle: document.getElementById("focusTitle"),
  focusMeta: document.getElementById("focusMeta"),
  focusCrop: document.getElementById("focusCrop"),
  focusControls: document.getElementById("focusControls"),
  focusPrev: document.getElementById("focusPrev"),
  focusNext: document.getElementById("focusNext"),
  focusModal: document.getElementById("focusModal"),
  thumbGrid: document.getElementById("thumbGrid"),
  exportNotice: document.getElementById("exportNotice"),
  provenance: document.getElementById("provenance"),
  cardModal: document.getElementById("cardModal"),
  modalTitle: document.getElementById("modalTitle"),
  modalMeta: document.getElementById("modalMeta"),
  modalCrop: document.getElementById("modalCrop"),
  closeModal: document.getElementById("closeModal"),
  modalPrev: document.getElementById("modalPrev"),
  modalNext: document.getElementById("modalNext"),
  modalSelect: document.getElementById("modalSelect"),
  toast: document.getElementById("toast"),
};

const selectionOptions = [
  ["", "ถูกต้อง / ไม่เลือก F-P-U"],
  ["F", "F - False Positive"],
  ["P", "P - Pairing Error"],
  ["U", "U - ไม่แน่ใจ"],
];

const badgeLabels = {
  accepted: "✓",
  F: "F",
  P: "P",
  U: "U",
};

function formatScore(value) {
  return Number(value).toFixed(4);
}

function storageKey() {
  return state.data.reviewUi.localStorageKey;
}

function uiStorageKey() {
  return `${storageKey()}${UI_STORAGE_SUFFIX}`;
}

function sheetsStorageKey() {
  return `${storageKey()}${SHEETS_STORAGE_SUFFIX}`;
}

function generateSessionId() {
  const seed = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `review_${seed.replace(/[^a-zA-Z0-9_-]/g, "")}`;
}

function normalizeEndpointUrl(value) {
  return String(value || "").trim();
}

function loadReviewState() {
  const raw = localStorage.getItem(storageKey());
  if (!raw) return;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && parsed.storageKey === storageKey()) {
      state.review = {
        selections: parsed.selections || {},
        completedPages: parsed.completedPages || {},
        updatedAt: parsed.updatedAt || null,
      };
    }
  } catch (_error) {
    localStorage.removeItem(storageKey());
  }
}

function loadUiState() {
  const defaultMode = window.matchMedia("(max-width: 768px)").matches ? "focus" : "overview";
  state.ui.mode = defaultMode;
  const raw = localStorage.getItem(uiStorageKey());
  if (!raw) return;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && parsed.storageKey === uiStorageKey()) {
      state.ui.mode = parsed.mode === "focus" ? "focus" : "overview";
      state.ui.focusCardId = parsed.focusCardId || null;
      state.ui.autoAdvance = Boolean(parsed.autoAdvance);
    }
  } catch (_error) {
    localStorage.removeItem(uiStorageKey());
  }
}

function loadSheetsState() {
  const configuredUrl = normalizeEndpointUrl(window.PICS_BIRDNESTS_REVIEW_SHEETS_URL || DEFAULT_GOOGLE_SHEETS_WEB_APP_URL);
  state.sheets.endpointUrl = configuredUrl;
  state.sheets.sessionId = generateSessionId();
  state.sheets.startedAt = new Date().toISOString();

  const raw = localStorage.getItem(sheetsStorageKey());
  if (!raw) return;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && parsed.storageKey === sheetsStorageKey()) {
      state.sheets.endpointUrl = normalizeEndpointUrl(parsed.endpointUrl || configuredUrl);
      state.sheets.reviewerName = parsed.reviewerName || "";
      state.sheets.reviewerNotes = parsed.reviewerNotes || "";
      state.sheets.sessionId = parsed.sessionId || state.sheets.sessionId;
      state.sheets.startedAt = parsed.startedAt || state.sheets.startedAt;
      state.sheets.lastSyncedAt = parsed.lastSyncedAt || "";
      state.sheets.finalSubmittedAt = parsed.finalSubmittedAt || "";
      state.sheets.status = parsed.status || (state.sheets.endpointUrl ? "ready" : "not_configured");
      state.sheets.message = parsed.message || "";
    }
  } catch (_error) {
    localStorage.removeItem(sheetsStorageKey());
  }
}

function saveReviewState() {
  state.review.updatedAt = new Date().toISOString();
  localStorage.setItem(
    storageKey(),
    JSON.stringify({
      storageKey: storageKey(),
      selections: state.review.selections,
      completedPages: state.review.completedPages,
      updatedAt: state.review.updatedAt,
    }),
  );
}

function saveUiState() {
  localStorage.setItem(
    uiStorageKey(),
    JSON.stringify({
      storageKey: uiStorageKey(),
      mode: state.ui.mode,
      focusCardId: state.ui.focusCardId,
      autoAdvance: state.ui.autoAdvance,
      updatedAt: new Date().toISOString(),
    }),
  );
}

function saveSheetsState() {
  localStorage.setItem(
    sheetsStorageKey(),
    JSON.stringify({
      storageKey: sheetsStorageKey(),
      endpointUrl: state.sheets.endpointUrl,
      reviewerName: state.sheets.reviewerName,
      reviewerNotes: state.sheets.reviewerNotes,
      sessionId: state.sheets.sessionId,
      startedAt: state.sheets.startedAt,
      lastSyncedAt: state.sheets.lastSyncedAt,
      finalSubmittedAt: state.sheets.finalSubmittedAt,
      status: state.sheets.status,
      message: state.sheets.message,
      updatedAt: new Date().toISOString(),
    }),
  );
}

function cardsOnPage(pageNumber = state.page) {
  const page = state.data.pages[pageNumber - 1];
  return page.cards.map((cardId) => state.cardsById.get(cardId));
}

function currentFocusCard() {
  if (!state.ui.focusCardId || !state.cardsById.has(state.ui.focusCardId)) {
    state.ui.focusCardId = cardsOnPage()[0].cardId;
  }
  return state.cardsById.get(state.ui.focusCardId);
}

function cardSelection(cardId) {
  return state.review.selections[cardId] || "";
}

function setCardSelection(cardId, value, options = {}) {
  if (value) {
    state.review.selections[cardId] = value;
  } else {
    delete state.review.selections[cardId];
  }
  saveReviewState();
  renderAll();
  if (options.source === "focus") {
    showToast(`${value || "ถูกต้อง"} บันทึกแล้ว`);
    if (state.ui.autoAdvance) {
      moveFocus(1);
    }
  }
}

function isPageComplete(pageNumber) {
  return Boolean(state.review.completedPages[String(pageNumber)]);
}

function setPageComplete(pageNumber, complete) {
  if (complete) {
    state.review.completedPages[String(pageNumber)] = new Date().toISOString();
    showToast(`บันทึกหน้า ${pageNumber} แล้ว - ${cardsOnPage(pageNumber).length} Cards`);
  } else {
    delete state.review.completedPages[String(pageNumber)];
    showToast(`ยกเลิกตรวจครบหน้า ${pageNumber}: blank cards กลับเป็น NOT_REVIEWED`);
  }
  saveReviewState();
  renderAll();
}

function reviewStatus(card) {
  const selected = cardSelection(card.cardId);
  if (selected === "F") return "FALSE_POSITIVE";
  if (selected === "P") return "PAIRING_ERROR";
  if (selected === "U") return "UNCERTAIN";
  return isPageComplete(card.page) ? "ACCEPTED" : "NOT_REVIEWED";
}

function finalClassification(card) {
  const selected = cardSelection(card.cardId);
  if (selected === "F") return "FALSE_POSITIVE_BY_EXPERT";
  if (selected === "P") return "PAIRING_ERROR";
  if (selected === "U") return "UNRESOLVED";
  return isPageComplete(card.page) ? "HUMAN_ACCEPTED_TRUE_POSITIVE" : "NOT_REVIEWED";
}

function calculateProgress() {
  const counts = {
    pagesDone: Object.keys(state.review.completedPages).length,
    accepted: 0,
    f: 0,
    p: 0,
    u: 0,
    remaining: 0,
  };
  state.data.cards.forEach((card) => {
    const status = reviewStatus(card);
    if (status === "ACCEPTED") counts.accepted += 1;
    if (status === "FALSE_POSITIVE") counts.f += 1;
    if (status === "PAIRING_ERROR") counts.p += 1;
    if (status === "UNCERTAIN") counts.u += 1;
    if (status === "NOT_REVIEWED") counts.remaining += 1;
  });
  counts.completedCards = counts.accepted + counts.f + counts.p + counts.u;
  counts.totalPages = state.data.pages.length;
  counts.totalCards = state.data.cards.length;
  counts.percent = counts.totalCards ? Math.round((counts.completedCards / counts.totalCards) * 100) : 0;
  return counts;
}

function pageHasException(pageNumber) {
  return cardsOnPage(pageNumber).some((card) => ["F", "P", "U"].includes(cardSelection(card.cardId)));
}

function renderProgress() {
  const counts = calculateProgress();
  els.progressHero.innerHTML = [
    [`${counts.percent}%`, "completion"],
    [`${counts.pagesDone} / ${counts.totalPages}`, "หน้าที่ตรวจครบ"],
    [`${counts.completedCards.toLocaleString("th-TH")} / ${counts.totalCards.toLocaleString("th-TH")}`, "cards"],
  ]
    .map(([value, label]) => `<div class="progress-big"><strong>${value}</strong><span>${label}</span></div>`)
    .join("");
  els.progressBar.style.width = `${counts.percent}%`;
  const items = [
    [counts.accepted.toLocaleString("th-TH"), "Accepted", "accepted"],
    [counts.f.toLocaleString("th-TH"), "F", "f"],
    [counts.p.toLocaleString("th-TH"), "P", "p"],
    [counts.u.toLocaleString("th-TH"), "U", "u"],
    [counts.remaining.toLocaleString("th-TH"), "Remaining", "remaining"],
  ];
  els.progressStrip.innerHTML = items
    .map(([value, label, klass]) => `<div class="progress-count ${klass}"><strong>${value}</strong><span>${label}</span></div>`)
    .join("");
  els.prevIncomplete.disabled = !findIncompletePage(-1);
  els.nextIncomplete.disabled = !findIncompletePage(1);
  renderExportNotice(counts);
  renderCompletionPanel(counts);
  els.identityPanel.innerHTML = [
    `<strong>${state.data.canonicalGalleryPackage}</strong>`,
    `Model: ${state.data.experiment.modelProfile}`,
    `Threshold: ${state.data.experiment.threshold}`,
    `Cards: ${counts.totalCards.toLocaleString("th-TH")} | Pages: ${counts.totalPages}`,
  ].join("<br>");
}

function renderExportNotice(counts = calculateProgress()) {
  if (counts.pagesDone === counts.totalPages) {
    els.exportNotice.classList.add("is-complete");
    els.exportNotice.textContent = `Review complete - ตรวจครบ ${counts.totalCards.toLocaleString("th-TH")} Cards แล้ว แนะนำดาวน์โหลด JSON สำหรับ Phase 8`;
    return;
  }
  els.exportNotice.classList.remove("is-complete");
  const missingPages = counts.totalPages - counts.pagesDone;
  els.exportNotice.textContent = `ยังตรวจไม่ครบ ${missingPages} หน้า - export ได้เพื่อ backup แต่ผลจะมี NOT_REVIEWED`;
}

function formatSyncTime(value) {
  if (!value) return "Not synced yet";
  try {
    return new Intl.DateTimeFormat("th-TH", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch (_error) {
    return value;
  }
}

function renderSheetsPanel(counts = calculateProgress()) {
  if (!els.sheetsStatus) return;
  const endpointReady = Boolean(state.sheets.endpointUrl);
  const reviewerReady = Boolean(state.sheets.reviewerName.trim());
  const ready = endpointReady && reviewerReady && !state.sheets.isSubmitting;
  const finalReady = ready && counts.totalCards === state.data.cards.length;
  const complete = counts.pagesDone === counts.totalPages;
  const missingPages = counts.totalPages - counts.pagesDone;

  els.sheetsEndpoint.value = state.sheets.endpointUrl;
  els.reviewerName.value = state.sheets.reviewerName;
  els.reviewerNotes.value = state.sheets.reviewerNotes;
  els.saveProgressSheets.disabled = !ready;
  els.submitFinalSheets.disabled = !finalReady;
  els.saveProgressSheets.textContent = state.sheets.isSubmitting ? "Saving..." : "Save Progress to Google Sheet";
  els.submitFinalSheets.textContent = state.sheets.isSubmitting ? "Submitting..." : "Submit Final Review";
  els.sheetsLastSync.textContent = `Last sync: ${formatSyncTime(state.sheets.lastSyncedAt)}`;

  els.sheetsStatus.dataset.status = state.sheets.status;
  if (state.sheets.status === "success") {
    els.sheetsStatus.textContent = state.sheets.message || "Google Sheet sync complete.";
  } else if (state.sheets.status === "error") {
    els.sheetsStatus.textContent = state.sheets.message || "Google Sheet sync failed. Keep JSON backup.";
  } else if (!endpointReady) {
    els.sheetsStatus.dataset.status = "not_configured";
    els.sheetsStatus.textContent = "Paste the deployed Apps Script Web App URL before syncing.";
  } else if (!reviewerReady) {
    els.sheetsStatus.dataset.status = "not_configured";
    els.sheetsStatus.textContent = "Enter reviewer name before syncing.";
  } else {
    els.sheetsStatus.dataset.status = "ready";
    els.sheetsStatus.textContent = "Ready to sync. JSON export remains the trusted backup.";
  }

  if (!complete) {
    els.sheetsWarning.hidden = false;
    els.sheetsWarning.textContent = `Incomplete review: ${missingPages} pages / ${counts.remaining.toLocaleString("th-TH")} cards remain. Save Progress is allowed; Final Submit requires confirmation.`;
  } else {
    els.sheetsWarning.hidden = false;
    els.sheetsWarning.textContent = "All 70 pages are complete. Final Submit is recommended, and JSON backup should still be downloaded.";
  }
}

function renderCompletionPanel(counts = calculateProgress()) {
  if (counts.pagesDone !== counts.totalPages) {
    els.completionPanel.hidden = true;
    els.completionPanel.innerHTML = "";
    return;
  }
  els.completionPanel.hidden = false;
  els.completionPanel.innerHTML = `
    ตรวจครบ ${counts.totalCards.toLocaleString("th-TH")} Cards แล้ว:
    Accepted ${counts.accepted.toLocaleString("th-TH")} ·
    F ${counts.f.toLocaleString("th-TH")} ·
    P ${counts.p.toLocaleString("th-TH")} ·
    U ${counts.u.toLocaleString("th-TH")}
  `;
}

function findIncompletePage(direction) {
  const total = state.data.pages.length;
  for (let offset = 1; offset <= total; offset += 1) {
    const page = ((state.page - 1 + direction * offset + total) % total) + 1;
    if (!isPageComplete(page)) return page;
  }
  return null;
}

function optionHtml(selected = "") {
  return selectionOptions
    .map(([value, label]) => `<option value="${value}"${value === selected ? " selected" : ""}>${label}</option>`)
    .join("");
}

function cardPositionStyle(card) {
  const geometry = state.data.reviewUi.cardGeometry;
  const x = geometry.x0 + (card.column - 1) * (geometry.cardWidth + geometry.gapX);
  const y = geometry.y0 + (card.row - 1) * (geometry.cardHeight + geometry.gapY);
  return [
    `left:${(x / geometry.pageWidth) * 100}%`,
    `top:${(y / geometry.pageHeight) * 100}%`,
    `width:${(geometry.cardWidth / geometry.pageWidth) * 100}%`,
    `height:${(geometry.cardHeight / geometry.pageHeight) * 100}%`,
  ].join(";");
}

function renderCardLayer() {
  const pageComplete = isPageComplete(state.page);
  els.cardLayer.innerHTML = cardsOnPage()
    .map((card) => {
      const selected = cardSelection(card.cardId);
      const accepted = !selected && pageComplete;
      const stateClass = selected ? `state-${selected.toLowerCase()}` : accepted ? "state-accepted" : "";
      const label = selected ? badgeLabels[selected] : accepted ? badgeLabels.accepted : "";
      return `
        <div class="card-control ${stateClass}" style="${cardPositionStyle(card)}" data-card-id="${card.cardId}">
          <button type="button" class="open-card" data-card-id="${card.cardId}" aria-label="ตรวจ ${card.cardId} แบบ Focus"></button>
          <select data-card-select="${card.cardId}" aria-label="ผลตรวจ ${card.cardId}">
            ${optionHtml(selected)}
          </select>
          <span class="card-badge ${label ? "" : "is-empty"}">${label}</span>
        </div>`;
    })
    .join("");
}

function renderSelector() {
  els.pageSelect.innerHTML = state.data.pages
    .map((page) => `<option value="${page.page}">หน้า ${String(page.page).padStart(3, "0")}</option>`)
    .join("");
  els.thumbGrid.innerHTML = state.data.pages
    .map((page) => `<button type="button" data-page="${page.page}">${page.page}</button>`)
    .join("");
}

function renderProvenance() {
  const entries = [
    ["Checkpoint SHA-256", state.data.experiment.checkpointSha256],
    ["Anchor profile", state.data.experiment.smallAnchors.join(" / ")],
    ["Threshold", state.data.experiment.threshold],
    ["Manifest", state.data.manifestIdentifier],
    ["Pair left", state.data.pairSemantics.left],
    ["Pair right", state.data.pairSemantics.right],
  ];
  els.provenance.innerHTML = entries.map(([label, value]) => `<div><span>${label}</span>${value}</div>`).join("");
}

function setPage(pageNumber) {
  const page = Math.max(1, Math.min(state.data.pages.length, pageNumber));
  const item = state.data.pages[page - 1];
  state.page = page;
  els.pageSelect.value = String(page);
  els.reviewImage.src = item.image;
  els.reviewImage.alt = `Review page ${page}`;
  els.directLink.href = item.image;
  if (!state.ui.focusCardId || state.cardsById.get(state.ui.focusCardId)?.page !== page) {
    state.ui.focusCardId = item.cards[0];
  }
  els.pageComplete.checked = isPageComplete(page);
  els.currentPageLabel.textContent = `${page} / ${state.data.pages.length}`;
  els.pageMeta.textContent = `หน้า ${String(page).padStart(3, "0")} · card ${item.cardStart}-${item.cardEnd} · score ${formatScore(item.scoreMin)}-${formatScore(item.scoreMax)}`;
  els.prevPage.disabled = page === 1;
  els.nextPage.disabled = page === state.data.pages.length;
  renderAll();
  saveUiState();
}

function renderThumbs() {
  els.thumbGrid.querySelectorAll("button").forEach((button) => {
    const page = Number(button.dataset.page);
    button.setAttribute("aria-current", page === state.page ? "page" : "false");
    button.dataset.complete = String(isPageComplete(page));
    button.dataset.exception = String(pageHasException(page));
  });
}

function renderModes() {
  const focus = state.ui.mode === "focus";
  els.focusPanel.hidden = !focus;
  els.overviewPanel.hidden = focus;
  els.overviewMode.setAttribute("aria-selected", String(!focus));
  els.focusMode.setAttribute("aria-selected", String(focus));
  els.autoAdvance.checked = state.ui.autoAdvance;
  if (focus) renderFocus();
}

function renderPageCompletionControl() {
  const complete = isPageComplete(state.page);
  els.pageComplete.checked = complete;
  els.pageCompleteLabel.classList.toggle("is-complete", complete);
  els.pageCompleteLabel.querySelector("span").textContent = complete ? "✓ ตรวจครบหน้านี้แล้ว" : "ตรวจครบหน้านี้แล้ว";
}

function renderAll() {
  renderProgress();
  renderSheetsPanel();
  renderThumbs();
  renderPageCompletionControl();
  renderCardLayer();
  renderModes();
  if (state.modalCardId) renderModal();
}

function setMode(mode) {
  state.ui.mode = mode === "focus" ? "focus" : "overview";
  if (state.ui.mode === "focus") {
    currentFocusCard();
  }
  saveUiState();
  renderModes();
}

function focusCard(cardId) {
  if (!state.cardsById.has(cardId)) return;
  const card = state.cardsById.get(cardId);
  if (card.page !== state.page) {
    setPage(card.page);
  }
  state.ui.focusCardId = cardId;
  state.ui.mode = "focus";
  saveUiState();
  renderModes();
  els.focusPanel.scrollIntoView({ block: "start", behavior: "smooth" });
}

function renderCardCrop(target, card) {
  const page = state.data.pages[card.page - 1];
  const geometry = state.data.reviewUi.cardGeometry;
  const cardX = geometry.x0 + (card.column - 1) * (geometry.cardWidth + geometry.gapX);
  const cardY = geometry.y0 + (card.row - 1) * (geometry.cardHeight + geometry.gapY);
  const targetWidth = target.clientWidth || geometry.cardWidth;
  const targetHeight = target.clientHeight || geometry.cardHeight;
  const scale = Math.min(targetWidth / geometry.cardWidth, targetHeight / geometry.cardHeight);
  const offsetX = (targetWidth - geometry.cardWidth * scale) / 2 - cardX * scale;
  const offsetY = (targetHeight - geometry.cardHeight * scale) / 2 - cardY * scale;
  target.style.backgroundImage = `url("${page.image}")`;
  target.style.backgroundSize = `${geometry.pageWidth * scale}px ${geometry.pageHeight * scale}px`;
  target.style.backgroundPosition = `${offsetX}px ${offsetY}px`;
}

function renderFocus() {
  const card = currentFocusCard();
  if (!card) return;
  els.focusTitle.textContent = `Card ${card.cardIndex.toLocaleString("th-TH")} / ${state.data.cards.length.toLocaleString("th-TH")}`;
  els.focusMeta.textContent = `Source ${card.sourceId} · score ${formatScore(card.score)} · page ${card.page} · position ${card.position} · ${card.predictionId}`;
  renderCardCrop(els.focusCrop, card);
  const selected = cardSelection(card.cardId);
  els.focusControls.querySelectorAll("[data-focus-choice]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.focusChoice === selected);
  });
  els.focusPrev.disabled = card.cardIndex <= 1;
  els.focusNext.disabled = card.cardIndex >= state.data.cards.length;
}

function moveFocus(delta) {
  const card = currentFocusCard();
  if (!card) return;
  const next = state.data.cards[card.cardIndex - 1 + delta];
  if (!next) return;
  if (next.page !== state.page) {
    setPage(next.page);
  }
  state.ui.focusCardId = next.cardId;
  saveUiState();
  renderModes();
}

function openModal(cardId) {
  state.modalCardId = cardId;
  els.cardModal.classList.add("is-open");
  els.cardModal.setAttribute("aria-hidden", "false");
  renderModal();
  els.closeModal.focus();
}

function closeModal() {
  state.modalCardId = null;
  els.cardModal.classList.remove("is-open");
  els.cardModal.setAttribute("aria-hidden", "true");
}

function renderModal() {
  const card = state.cardsById.get(state.modalCardId);
  if (!card) return;
  els.modalTitle.textContent = `${card.cardId} | Source ${card.sourceId}`;
  els.modalMeta.textContent = `${card.predictionId} | score ${formatScore(card.score)} | page ${card.page} pos ${card.position}`;
  renderCardCrop(els.modalCrop, card);
  els.modalSelect.innerHTML = optionHtml(cardSelection(card.cardId));
  els.modalPrev.disabled = card.cardIndex <= 1;
  els.modalNext.disabled = card.cardIndex >= state.data.cards.length;
}

function moveModal(delta) {
  const card = state.cardsById.get(state.modalCardId);
  if (!card) return;
  const nextIndex = card.cardIndex + delta;
  const next = state.data.cards[nextIndex - 1];
  if (!next) return;
  if (next.page !== state.page) setPage(next.page);
  state.modalCardId = next.cardId;
  renderModal();
}

function buildResultRows() {
  const exportedAt = new Date().toISOString();
  return state.data.cards.map((card) => ({
    reviewSchemaVersion: state.data.reviewSchemaVersion,
    packageId: state.data.canonicalGalleryPackage,
    modelProfile: state.data.experiment.modelProfile,
    checkpointSha256: state.data.experiment.checkpointSha256,
    threshold: state.data.experiment.threshold,
    manifestIdentifier: state.data.manifestIdentifier,
    cardId: card.cardId,
    cardIndex: card.cardIndex,
    page: card.page,
    position: card.position,
    sourceId: card.sourceId,
    predictionId: card.predictionId,
    score: card.score,
    bboxX1: card.bbox.x1,
    bboxY1: card.bbox.y1,
    bboxX2: card.bbox.x2,
    bboxY2: card.bbox.y2,
    reviewerSelection: cardSelection(card.cardId),
    reviewStatus: reviewStatus(card),
    finalClassification: finalClassification(card),
    pageCompleted: isPageComplete(card.page),
    pageCompletedAt: state.review.completedPages[String(card.page)] || "",
    exportedAt,
  }));
}

function exportPayload() {
  const rows = buildResultRows();
  const counts = calculateProgress();
  return {
    reviewSchemaVersion: state.data.reviewSchemaVersion,
    packageId: state.data.canonicalGalleryPackage,
    modelProfile: state.data.experiment.modelProfile,
    checkpointSha256: state.data.experiment.checkpointSha256,
    threshold: state.data.experiment.threshold,
    manifestIdentifier: state.data.manifestIdentifier,
    exportedAt: new Date().toISOString(),
    summary: {
      pageCount: state.data.pages.length,
      cardCount: state.data.cards.length,
      reviewedPages: counts.pagesDone,
      completedCards: counts.completedCards,
      accepted: counts.accepted,
      falsePositive: counts.f,
      pairingError: counts.p,
      uncertain: counts.u,
      remaining: counts.remaining,
    },
    results: rows,
  };
}

function buildSessionSummary(counts = calculateProgress()) {
  return {
    pageCount: state.data.pages.length,
    cardCount: state.data.cards.length,
    reviewedPages: counts.pagesDone,
    completedCards: counts.completedCards,
    accepted: counts.accepted,
    falsePositive: counts.f,
    pairingError: counts.p,
    uncertain: counts.u,
    remaining: counts.remaining,
  };
}

function buildSubmissionPayload(action, options = {}) {
  const isFinal = action === SUBMISSION_ACTIONS.submitFinal;
  const submittedAt = new Date().toISOString();
  const rows = isFinal ? buildResultRows() : [];
  return {
    schemaVersion: "google-sheets-review-submission:v1",
    clientVersion: CLIENT_VERSION,
    action,
    sessionId: state.sheets.sessionId,
    reviewerName: state.sheets.reviewerName.trim(),
    reviewerNotes: state.sheets.reviewerNotes.trim(),
    startedAt: state.sheets.startedAt,
    clientSubmittedAt: submittedAt,
    overwriteResults: Boolean(options.overwriteResults),
    reviewSchemaVersion: state.data.reviewSchemaVersion,
    packageId: state.data.canonicalGalleryPackage,
    modelProfile: state.data.experiment.modelProfile,
    checkpointSha256: state.data.experiment.checkpointSha256,
    threshold: state.data.experiment.threshold,
    manifestIdentifier: state.data.manifestIdentifier,
    summary: buildSessionSummary(),
    results: rows,
  };
}

function download(filename, mime, textValue) {
  const blob = new Blob([textValue], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (/[",\n\r]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function announceExportStatus() {
  const counts = calculateProgress();
  if (counts.remaining > 0) {
    showToast(`ยังตรวจไม่ครบ ${counts.totalPages - counts.pagesDone} หน้า - export จะมี NOT_REVIEWED`);
  } else {
    showToast("Review complete - พร้อมส่ง JSON เข้า Phase 8");
  }
}

function downloadCsv() {
  announceExportStatus();
  const rows = buildResultRows();
  const fields = Object.keys(rows[0]);
  const csv = [fields.join(","), ...rows.map((row) => fields.map((field) => csvEscape(row[field])).join(","))].join("\n");
  download("small_anchor_0125_expert_review_results.csv", "text/csv;charset=utf-8", csv);
}

function downloadJson() {
  announceExportStatus();
  download(
    "small_anchor_0125_expert_review_results.json",
    "application/json;charset=utf-8",
    JSON.stringify(exportPayload(), null, 2),
  );
}

function importJsonFile(file) {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const payload = JSON.parse(String(reader.result));
      const identityMatches =
        payload.packageId === state.data.canonicalGalleryPackage &&
        payload.modelProfile === state.data.experiment.modelProfile &&
        payload.checkpointSha256 === state.data.experiment.checkpointSha256 &&
        payload.threshold === state.data.experiment.threshold &&
        payload.manifestIdentifier === state.data.manifestIdentifier;
      if (!identityMatches || !Array.isArray(payload.results)) {
        window.alert("ไฟล์ JSON นี้ไม่ตรงกับ package/checkpoint/manifest ของงานนี้");
        return;
      }
      const selections = {};
      const completedPages = {};
      payload.results.forEach((row) => {
        if (["F", "P", "U"].includes(row.reviewerSelection)) {
          selections[row.cardId] = row.reviewerSelection;
        }
        if (row.pageCompleted) {
          completedPages[String(row.page)] = row.pageCompletedAt || payload.exportedAt || new Date().toISOString();
        }
      });
      state.review = { selections, completedPages, updatedAt: new Date().toISOString() };
      saveReviewState();
      renderAll();
      window.alert("นำเข้าผลตรวจ JSON แล้ว");
    } catch (_error) {
      window.alert("อ่านไฟล์ JSON ไม่สำเร็จ");
    }
  };
  reader.readAsText(file, "utf-8");
}

function validateSheetSubmission(action) {
  if (!state.sheets.endpointUrl) return "Paste the Apps Script Web App URL before syncing.";
  if (!/^https:\/\/script\.google\.com\/macros\/s\//.test(state.sheets.endpointUrl)) {
    return "Apps Script URL should start with https://script.google.com/macros/s/.";
  }
  if (!state.sheets.reviewerName.trim()) return "Enter reviewer name before syncing.";
  if (action === SUBMISSION_ACTIONS.submitFinal && buildResultRows().length !== state.data.cards.length) {
    return "Final Submit row count does not match the 1,400-card review package.";
  }
  return "";
}

function setSheetStatus(status, message) {
  state.sheets.status = status;
  state.sheets.message = message;
  saveSheetsState();
  renderSheetsPanel();
}

async function postSheetPayload(payload) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 45000);
  try {
    const response = await fetch(state.sheets.endpointUrl, {
      method: "POST",
      mode: "cors",
      headers: {
        "Content-Type": "text/plain;charset=utf-8",
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    const text = await response.text();
    let result;
    try {
      result = JSON.parse(text);
    } catch (_error) {
      result = { ok: response.ok, message: text || response.statusText };
    }
    if (!response.ok || result.ok === false) {
      const error = new Error(result.message || `Google Apps Script returned HTTP ${response.status}`);
      error.response = result;
      throw error;
    }
    return result;
  } finally {
    window.clearTimeout(timer);
  }
}

async function submitToGoogleSheets(action, options = {}) {
  const validationError = validateSheetSubmission(action);
  if (validationError) {
    setSheetStatus("error", validationError);
    showToast(validationError);
    return;
  }

  const counts = calculateProgress();
  const isFinal = action === SUBMISSION_ACTIONS.submitFinal;
  if (isFinal && counts.remaining > 0 && !options.confirmedIncomplete) {
    const ok = window.confirm(`Final Submit includes ${counts.remaining.toLocaleString("th-TH")} NOT_REVIEWED cards because ${counts.totalPages - counts.pagesDone} pages are incomplete. Submit anyway?`);
    if (!ok) return;
  }
  if (isFinal && state.sheets.finalSubmittedAt && !options.overwriteResults) {
    const ok = window.confirm("This session was already submitted. Replace the existing ReviewResults rows for this session_id?");
    if (!ok) return;
    options = { ...options, overwriteResults: true };
  }

  state.sheets.isSubmitting = true;
  renderSheetsPanel(counts);
  try {
    const payload = buildSubmissionPayload(action, options);
    const result = await postSheetPayload(payload);
    const now = new Date().toISOString();
    state.sheets.lastSyncedAt = now;
    if (isFinal) state.sheets.finalSubmittedAt = now;
    setSheetStatus("success", result.message || (isFinal ? "Final review submitted to Google Sheet." : "Progress saved to Google Sheet."));
    showToast(isFinal ? "Google Sheet final submit complete" : "Google Sheet progress saved");
  } catch (error) {
    const duplicateFinal = error.response && error.response.code === "DUPLICATE_FINAL_SUBMISSION";
    if (isFinal && duplicateFinal && !options.overwriteResults) {
      const ok = window.confirm("This session_id already has ReviewResults rows. Replace those rows and submit again?");
      if (ok) {
        state.sheets.isSubmitting = false;
        await submitToGoogleSheets(action, { ...options, overwriteResults: true });
        return;
      }
    }
    setSheetStatus("error", `${error.message || "Google Sheet sync failed."} JSON backup is still available.`);
    showToast("Google Sheet sync failed - use JSON backup if needed");
  } finally {
    state.sheets.isSubmitting = false;
    saveSheetsState();
    renderSheetsPanel();
  }
}

function isTypingTarget(target) {
  return Boolean(target.closest("input, textarea, select, [contenteditable='true']"));
}

function handleShortcut(event) {
  if (isTypingTarget(event.target)) return;
  const modalOpen = els.cardModal.classList.contains("is-open");
  const focusMode = state.ui.mode === "focus";
  if (event.key === "Escape" && modalOpen) {
    closeModal();
    return;
  }
  if (!modalOpen && !focusMode) {
    if (event.key === "ArrowLeft") setPage(state.page - 1);
    if (event.key === "ArrowRight") setPage(state.page + 1);
    return;
  }
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    modalOpen ? moveModal(-1) : moveFocus(-1);
    return;
  }
  if (event.key === "ArrowRight") {
    event.preventDefault();
    modalOpen ? moveModal(1) : moveFocus(1);
    return;
  }
  const key = event.key.toUpperCase();
  const shortcutMap = { F: "F", P: "P", U: "U", C: "", "0": "" };
  if (Object.prototype.hasOwnProperty.call(shortcutMap, key)) {
    event.preventDefault();
    const cardId = modalOpen ? state.modalCardId : currentFocusCard()?.cardId;
    if (cardId) setCardSelection(cardId, shortcutMap[key], { source: modalOpen ? "modal" : "focus" });
  }
}

function showToast(message) {
  window.clearTimeout(state.toastTimer);
  els.toast.textContent = message;
  els.toast.classList.add("is-visible");
  state.toastTimer = window.setTimeout(() => {
    els.toast.classList.remove("is-visible");
  }, 1800);
}

function initEvents() {
  els.pageSelect.addEventListener("change", (event) => setPage(Number(event.target.value)));
  els.prevPage.addEventListener("click", () => setPage(state.page - 1));
  els.nextPage.addEventListener("click", () => setPage(state.page + 1));
  els.pageComplete.addEventListener("change", (event) => setPageComplete(state.page, event.target.checked));
  els.overviewMode.addEventListener("click", () => setMode("overview"));
  els.focusMode.addEventListener("click", () => setMode("focus"));
  els.autoAdvance.addEventListener("change", (event) => {
    state.ui.autoAdvance = event.target.checked;
    saveUiState();
    showToast(state.ui.autoAdvance ? "Auto-advance เปิดแล้ว" : "Auto-advance ปิดแล้ว");
  });
  els.prevIncomplete.addEventListener("click", () => {
    const page = findIncompletePage(-1);
    if (page) setPage(page);
  });
  els.nextIncomplete.addEventListener("click", () => {
    const page = findIncompletePage(1);
    if (page) setPage(page);
  });
  els.sheetsEndpoint.addEventListener("input", (event) => {
    state.sheets.endpointUrl = normalizeEndpointUrl(event.target.value);
    state.sheets.status = state.sheets.endpointUrl ? "ready" : "not_configured";
    state.sheets.message = "";
    saveSheetsState();
    renderSheetsPanel();
  });
  els.reviewerName.addEventListener("input", (event) => {
    state.sheets.reviewerName = event.target.value;
    state.sheets.status = state.sheets.endpointUrl ? "ready" : "not_configured";
    state.sheets.message = "";
    saveSheetsState();
    renderSheetsPanel();
  });
  els.reviewerNotes.addEventListener("input", (event) => {
    state.sheets.reviewerNotes = event.target.value;
    saveSheetsState();
  });
  els.saveProgressSheets.addEventListener("click", () => submitToGoogleSheets(SUBMISSION_ACTIONS.saveProgress));
  els.submitFinalSheets.addEventListener("click", () => submitToGoogleSheets(SUBMISSION_ACTIONS.submitFinal));
  els.downloadCsv.addEventListener("click", downloadCsv);
  els.downloadJson.addEventListener("click", downloadJson);
  els.importJson.addEventListener("click", () => els.importFile.click());
  els.importFile.addEventListener("change", (event) => {
    const [file] = event.target.files || [];
    if (file) importJsonFile(file);
    event.target.value = "";
  });
  els.clearReview.addEventListener("click", () => {
    const ok = window.confirm("ล้างผลตรวจทั้งหมดจาก browser นี้หรือไม่?");
    if (!ok) return;
    state.review = { selections: {}, completedPages: {}, updatedAt: null };
    localStorage.removeItem(storageKey());
    renderAll();
    showToast("ล้างผลตรวจแล้ว");
  });
  els.cardLayer.addEventListener("click", (event) => {
    const button = event.target.closest(".open-card");
    if (button) focusCard(button.dataset.cardId);
  });
  els.cardLayer.addEventListener("change", (event) => {
    const select = event.target.closest("select[data-card-select]");
    if (select) setCardSelection(select.dataset.cardSelect, select.value);
  });
  els.thumbGrid.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-page]");
    if (button) setPage(Number(button.dataset.page));
  });
  els.focusControls.addEventListener("click", (event) => {
    const button = event.target.closest("[data-focus-choice]");
    if (!button) return;
    const card = currentFocusCard();
    if (card) setCardSelection(card.cardId, button.dataset.focusChoice, { source: "focus" });
  });
  els.focusPrev.addEventListener("click", () => moveFocus(-1));
  els.focusNext.addEventListener("click", () => moveFocus(1));
  els.focusModal.addEventListener("click", () => {
    const card = currentFocusCard();
    if (card) openModal(card.cardId);
  });
  els.closeModal.addEventListener("click", closeModal);
  els.cardModal.addEventListener("click", (event) => {
    if (event.target === els.cardModal) closeModal();
  });
  els.modalPrev.addEventListener("click", () => moveModal(-1));
  els.modalNext.addEventListener("click", () => moveModal(1));
  els.modalSelect.addEventListener("change", () => {
    if (state.modalCardId) setCardSelection(state.modalCardId, els.modalSelect.value);
  });
  window.addEventListener("resize", () => {
    if (state.ui.mode === "focus") renderFocus();
    if (state.modalCardId) renderModal();
  });
  document.addEventListener("keydown", handleShortcut);
}

async function init() {
  const response = await fetch("data/review-data.json");
  if (!response.ok) throw new Error(`Unable to load review metadata: ${response.status}`);
  state.data = await response.json();
  state.data.cards.forEach((card) => state.cardsById.set(card.cardId, card));
  loadReviewState();
  loadUiState();
  loadSheetsState();
  renderSelector();
  renderProvenance();
  initEvents();
  setPage(1);
  window.reviewApp = {
    state,
    storageKey,
    uiStorageKey,
    calculateProgress,
    buildResultRows,
    buildSessionSummary,
    buildSubmissionPayload,
    exportPayload,
    finalClassification,
    reviewStatus,
    setPage,
    setCardSelection,
    setPageComplete,
    setMode,
    moveFocus,
  };
}

init().catch((error) => {
  els.pageMeta.textContent = error.message;
});
