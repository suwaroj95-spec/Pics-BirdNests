const UI_STORAGE_SUFFIX = ":ui:v1";

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
