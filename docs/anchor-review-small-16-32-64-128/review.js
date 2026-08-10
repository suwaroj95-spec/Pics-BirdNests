const state = {
  page: 1,
  data: null,
};

const els = {
  pageSelect: document.getElementById("pageSelect"),
  prevPage: document.getElementById("prevPage"),
  nextPage: document.getElementById("nextPage"),
  directLink: document.getElementById("directLink"),
  reviewImage: document.getElementById("reviewImage"),
  pageMeta: document.getElementById("pageMeta"),
  thumbGrid: document.getElementById("thumbGrid"),
  provenance: document.getElementById("provenance"),
  openViewer: document.getElementById("openViewer"),
  viewer: document.getElementById("viewer"),
  viewerImage: document.getElementById("viewerImage"),
  closeViewer: document.getElementById("closeViewer"),
};

function formatScore(value) {
  return Number(value).toFixed(3);
}

function renderProvenance(data) {
  const pkg = data.packages.map((item) => `${item.package_id}: ${item.threshold}`).join(" / ");
  const entries = [
    ["Checkpoint SHA-256", data.experiment.checkpointSha256],
    ["Anchor profile", data.experiment.smallAnchors.join(" / ")],
    ["Threshold", data.experiment.threshold],
    ["Card count", data.experiment.cardCount.toLocaleString("th-TH")],
    ["Page count", data.experiment.pageCount.toLocaleString("th-TH")],
    ["Package identity", pkg],
    ["A/B status", data.packageComparison.reasonSingleGallery],
  ];
  els.provenance.innerHTML = entries.map(([label, value]) => `<div><span>${label}</span>${value}</div>`).join("");
}

function renderSelector(data) {
  els.pageSelect.innerHTML = data.pages
    .map((page) => `<option value="${page.page}">หน้า ${page.page.toString().padStart(3, "0")}</option>`)
    .join("");
  els.thumbGrid.innerHTML = data.pages
    .map((page) => `<button type="button" data-page="${page.page}" aria-label="ไปหน้า ${page.page}">${page.page}</button>`)
    .join("");
}

function setPage(pageNumber) {
  const data = state.data;
  const page = Math.max(1, Math.min(data.pages.length, pageNumber));
  const item = data.pages[page - 1];
  state.page = page;
  els.pageSelect.value = String(page);
  els.reviewImage.src = item.image;
  els.reviewImage.alt = `Review page ${page}`;
  els.directLink.href = item.image;
  els.pageMeta.textContent = `หน้า ${page.toString().padStart(3, "0")} / ${data.pages.length} - card ${item.cardStart} ถึง ${item.cardEnd}, score ${formatScore(item.scoreMin)}-${formatScore(item.scoreMax)}`;
  els.viewerImage.src = item.image;
  els.viewerImage.alt = `Expanded review page ${page}`;
  els.prevPage.disabled = page === 1;
  els.nextPage.disabled = page === data.pages.length;
  els.thumbGrid.querySelectorAll("button").forEach((button) => {
    button.setAttribute("aria-current", Number(button.dataset.page) === page ? "page" : "false");
  });
}

function openViewer() {
  els.viewer.classList.add("is-open");
  els.viewer.setAttribute("aria-hidden", "false");
  els.closeViewer.focus();
}

function closeViewer() {
  els.viewer.classList.remove("is-open");
  els.viewer.setAttribute("aria-hidden", "true");
  els.openViewer.focus();
}

async function init() {
  const response = await fetch("data/review-data.json");
  if (!response.ok) throw new Error(`Unable to load review metadata: ${response.status}`);
  state.data = await response.json();
  renderSelector(state.data);
  renderProvenance(state.data);
  setPage(1);
}

els.pageSelect.addEventListener("change", (event) => setPage(Number(event.target.value)));
els.prevPage.addEventListener("click", () => setPage(state.page - 1));
els.nextPage.addEventListener("click", () => setPage(state.page + 1));
els.thumbGrid.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-page]");
  if (button) setPage(Number(button.dataset.page));
});
els.openViewer.addEventListener("click", openViewer);
els.closeViewer.addEventListener("click", closeViewer);
els.viewer.addEventListener("click", (event) => {
  if (event.target === els.viewer) closeViewer();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "ArrowLeft") setPage(state.page - 1);
  if (event.key === "ArrowRight") setPage(state.page + 1);
  if (event.key === "Escape" && els.viewer.classList.contains("is-open")) closeViewer();
});

init().catch((error) => {
  els.pageMeta.textContent = error.message;
});
