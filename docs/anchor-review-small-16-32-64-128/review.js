const state = {
  page: 1,
  data: null,
  cardsById: new Map(),
  review: {
    selections: {},
    completedPages: {},
    updatedAt: null,
  },
  modalCardId: null,
};

const els = {
  identityPanel: document.getElementById("identityPanel"),
  progressStrip: document.getElementById("progressStrip"),
  prevIncomplete: document.getElementById("prevIncomplete"),
  nextIncomplete: document.getElementById("nextIncomplete"),
  downloadCsv: document.getElementById("downloadCsv"),
  downloadJson: document.getElementById("downloadJson"),
  importJson: document.getElementById("importJson"),
  importFile: document.getElementById("importFile"),
  clearReview: document.getElementById("clearReview"),
  pageSelect: document.getElementById("pageSelect"),
  prevPage: document.getElementById("prevPage"),
  nextPage: document.getElementById("nextPage"),
  directLink: document.getElementById("directLink"),
  pageComplete: document.getElementById("pageComplete"),
  reviewImage: document.getElementById("reviewImage"),
  pageMeta: document.getElementById("pageMeta"),
  cardLayer: document.getElementById("cardLayer"),
  thumbGrid: document.getElementById("thumbGrid"),
  provenance: document.getElementById("provenance"),
  cardModal: document.getElementById("cardModal"),
  modalTitle: document.getElementById("modalTitle"),
  modalMeta: document.getElementById("modalMeta"),
  modalCrop: document.getElementById("modalCrop"),
  closeModal: document.getElementById("closeModal"),
  modalPrev: document.getElementById("modalPrev"),
  modalNext: document.getElementById("modalNext"),
  modalSelect: document.getElementById("modalSelect"),
};

const selectionOptions = [
  ["", "ไม่เลือก — ถือว่าถูกต้องเมื่อยืนยันตรวจครบหน้า"],
  ["F", "F — False Positive"],
  ["P", "P — Pairing Error"],
  ["U", "U — ไม่แน่ใจ"],
];

const badgeLabels = {
  F: "F — False Positive",
  P: "P — Pairing Error",
  U: "U — Uncertain",
};

function formatScore(value) {
  return Number(value).toFixed(4);
}

function storageKey() {
  return state.data.reviewUi.localStorageKey;
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

function cardsOnPage(pageNumber = state.page) {
  const page = state.data.pages[pageNumber - 1];
  return page.cards.map((cardId) => state.cardsById.get(cardId));
}

function cardSelection(cardId) {
  return state.review.selections[cardId] || "";
}

function setCardSelection(cardId, value) {
  if (value) {
    state.review.selections[cardId] = value;
  } else {
    delete state.review.selections[cardId];
  }
  saveReviewState();
  renderAll();
}

function isPageComplete(pageNumber) {
  return Boolean(state.review.completedPages[String(pageNumber)]);
}

function setPageComplete(pageNumber, complete) {
  if (complete) {
    state.review.completedPages[String(pageNumber)] = new Date().toISOString();
  } else {
    delete state.review.completedPages[String(pageNumber)];
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
  return counts;
}

function renderProgress() {
  const counts = calculateProgress();
  const totalPages = state.data.pages.length;
  const totalCards = state.data.cards.length;
  const items = [
    [`${counts.pagesDone} / ${totalPages}`, "ตรวจแล้ว"],
    [counts.completedCards.toLocaleString("th-TH"), "Completed cards"],
    [counts.accepted.toLocaleString("th-TH"), "Accepted"],
    [counts.f.toLocaleString("th-TH"), "F"],
    [counts.p.toLocaleString("th-TH"), "P"],
    [`${counts.u.toLocaleString("th-TH")} | ${counts.remaining.toLocaleString("th-TH")}`, "U | Remaining"],
  ];
  els.progressStrip.innerHTML = items
    .map(([value, label]) => `<div class="progress-item"><strong>${value}</strong><span>${label}</span></div>`)
    .join("");
  els.prevIncomplete.disabled = !findIncompletePage(-1);
  els.nextIncomplete.disabled = !findIncompletePage(1);
  els.identityPanel.innerHTML = [
    `<strong>${state.data.canonicalGalleryPackage}</strong>`,
    `Model: ${state.data.experiment.modelProfile}`,
    `Threshold: ${state.data.experiment.threshold}`,
    `Cards: ${totalCards.toLocaleString("th-TH")} | Pages: ${totalPages}`,
  ].join("<br>");
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
  els.cardLayer.innerHTML = cardsOnPage()
    .map((card) => {
      const selected = cardSelection(card.cardId);
      const stateClass = selected ? `state-${selected.toLowerCase()}` : "";
      return `
        <div class="card-control ${stateClass}" style="${cardPositionStyle(card)}" data-card-id="${card.cardId}">
          <button type="button" class="open-card" data-card-id="${card.cardId}" aria-label="ขยาย ${card.cardId}"></button>
          <select data-card-select="${card.cardId}" aria-label="ผลตรวจ ${card.cardId}">
            ${optionHtml(selected)}
          </select>
          <span class="card-badge ${selected ? "" : "is-empty"}">${badgeLabels[selected] || ""}</span>
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
  els.pageComplete.checked = isPageComplete(page);
  els.pageMeta.textContent = `หน้า ${String(page).padStart(3, "0")} / ${state.data.pages.length} - card ${item.cardStart} ถึง ${item.cardEnd}, score ${formatScore(item.scoreMin)}-${formatScore(item.scoreMax)}`;
  els.prevPage.disabled = page === 1;
  els.nextPage.disabled = page === state.data.pages.length;
  renderCardLayer();
  renderProgress();
  renderThumbs();
  if (state.modalCardId) renderModal();
}

function renderThumbs() {
  els.thumbGrid.querySelectorAll("button").forEach((button) => {
    const page = Number(button.dataset.page);
    button.setAttribute("aria-current", page === state.page ? "page" : "false");
    button.dataset.complete = String(isPageComplete(page));
  });
}

function renderAll() {
  renderProgress();
  renderThumbs();
  els.pageComplete.checked = isPageComplete(state.page);
  renderCardLayer();
  if (state.modalCardId) renderModal();
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
  const page = state.data.pages[card.page - 1];
  const geometry = state.data.reviewUi.cardGeometry;
  const cardX = geometry.x0 + (card.column - 1) * (geometry.cardWidth + geometry.gapX);
  const cardY = geometry.y0 + (card.row - 1) * (geometry.cardHeight + geometry.gapY);
  const cropWidth = els.modalCrop.clientWidth || geometry.cardWidth;
  const scale = cropWidth / geometry.cardWidth;
  els.modalTitle.textContent = `${card.cardId} | Source ${card.sourceId}`;
  els.modalMeta.textContent = `${card.predictionId} | score ${formatScore(card.score)} | page ${card.page} pos ${card.position}`;
  els.modalCrop.style.backgroundImage = `url("${page.image}")`;
  els.modalCrop.style.backgroundSize = `${geometry.pageWidth * scale}px ${geometry.pageHeight * scale}px`;
  els.modalCrop.style.backgroundPosition = `-${cardX * scale}px -${cardY * scale}px`;
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

function downloadCsv() {
  const rows = buildResultRows();
  const fields = Object.keys(rows[0]);
  const csv = [fields.join(","), ...rows.map((row) => fields.map((field) => csvEscape(row[field])).join(","))].join("\n");
  download("small_anchor_0125_expert_review_results.csv", "text/csv;charset=utf-8", csv);
}

function downloadJson() {
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

function initEvents() {
  els.pageSelect.addEventListener("change", (event) => setPage(Number(event.target.value)));
  els.prevPage.addEventListener("click", () => setPage(state.page - 1));
  els.nextPage.addEventListener("click", () => setPage(state.page + 1));
  els.pageComplete.addEventListener("change", (event) => setPageComplete(state.page, event.target.checked));
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
  });
  els.cardLayer.addEventListener("click", (event) => {
    const button = event.target.closest(".open-card");
    if (button) openModal(button.dataset.cardId);
  });
  els.cardLayer.addEventListener("change", (event) => {
    const select = event.target.closest("select[data-card-select]");
    if (select) setCardSelection(select.dataset.cardSelect, select.value);
  });
  els.thumbGrid.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-page]");
    if (button) setPage(Number(button.dataset.page));
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
    if (state.modalCardId) renderModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && els.cardModal.classList.contains("is-open")) closeModal();
    if (event.key === "ArrowLeft" && !els.cardModal.classList.contains("is-open")) setPage(state.page - 1);
    if (event.key === "ArrowRight" && !els.cardModal.classList.contains("is-open")) setPage(state.page + 1);
  });
}

async function init() {
  const response = await fetch("data/review-data.json");
  if (!response.ok) throw new Error(`Unable to load review metadata: ${response.status}`);
  state.data = await response.json();
  state.data.cards.forEach((card) => state.cardsById.set(card.cardId, card));
  loadReviewState();
  renderSelector();
  renderProvenance();
  initEvents();
  setPage(1);
}

init().catch((error) => {
  els.pageMeta.textContent = error.message;
});
