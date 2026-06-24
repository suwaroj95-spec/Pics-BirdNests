from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
MAX_LOG_LINES = 900
MAX_REQUEST_BYTES = 64 * 1024
STATE_LOCK = threading.Lock()
RUN_STATE = {
    "running": False,
    "started_at": "",
    "finished_at": "",
    "status": "idle",
    "error": "",
    "logs": [],
    "outputs": {},
}


DEFAULT_CONFIG = {
    "steps": {
        "crop": False,
        "backtest": True,
        "anomaly": True,
    },
    "crop": {
        "rawDir": "RawPics",
        "outputDir": "Crops",
        "patchSize": 256,
        "coverageStep": 48,
        "minEdgeShift": 24,
        "maskDilation": 20,
        "minContentRatio": 0.35,
        "positiveJitterCrops": 3,
        "positiveJitterRadius": 64,
        "minBlueComponentArea": 20,
        "randomSeed": 42,
        "dirtyCropSource": "registered_original",
        "generateClean": True,
        "generateDirty": True,
        "clearOutput": False,
    },
    "backtest": {
        "cropsDir": "Crops",
        "outputDir": "BacktestSelection",
        "cleanTarget": 300,
        "dirtyPairTarget": 200,
        "copyFiles": True,
        "sourceDiversity": True,
    },
    "anomaly": {
        "backtestRun": "",
        "backtestRoot": "BacktestSelection",
        "cropsDir": "Crops",
        "outputDir": "AnomalyDetection",
        "contamination": 0.08,
        "consensusThreshold": 0.85,
        "minVotes": 2,
        "isolationForest": True,
        "lof": True,
        "pca": True,
        "isolationTrees": 96,
        "isolationSubsample": 256,
        "neighborK": 20,
        "pcaComponents": 6,
        "topN": 24,
        "randomSeed": 42,
        "makePreviews": True,
        "copyAnomalies": False,
    },
}


INDEX_HTML = r"""<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bird Nest Pipeline Panel</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #f5f7f8;
      --ink: #1e2a32;
      --muted: #60717d;
      --line: #d8e0e5;
      --panel: #ffffff;
      --field: #fbfcfd;
      --green: #167c64;
      --blue: #2e6f95;
      --amber: #aa6b12;
      --red: #a33d3d;
      --shadow: 0 18px 38px rgba(31, 45, 55, 0.10);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Sarabun", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    .shell {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
    }
    aside {
      background: #17242c;
      color: #f4f7f8;
      padding: 24px 20px;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }
    .brand h1 {
      margin: 0 0 8px;
      font-size: 22px;
      line-height: 1.16;
      font-weight: 760;
    }
    .brand p {
      margin: 0;
      color: #b8c5cc;
      font-size: 13px;
      line-height: 1.45;
    }
    .statusBox {
      border: 1px solid rgba(255,255,255,0.12);
      background: rgba(255,255,255,0.06);
      border-radius: 8px;
      padding: 14px;
    }
    .statusLine {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }
    .pill {
      display: inline-flex;
      min-height: 28px;
      align-items: center;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      background: #e7eef2;
      color: #253742;
    }
    .pill.running { background: #e6f4ef; color: var(--green); }
    .pill.error { background: #f7e8e8; color: var(--red); }
    .pill.done { background: #e7eff7; color: var(--blue); }
    .meta {
      color: #b8c5cc;
      font-size: 12px;
      line-height: 1.5;
      word-break: break-word;
    }
    button {
      border: 0;
      border-radius: 8px;
      min-height: 42px;
      padding: 0 16px;
      font-family: inherit;
      font-weight: 760;
      cursor: pointer;
      transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
    }
    button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    button.primary {
      width: 100%;
      color: #ffffff;
      background: var(--green);
      box-shadow: 0 12px 24px rgba(22, 124, 100, 0.22);
    }
    button.secondary {
      color: var(--ink);
      background: #e8eef2;
    }
    button:not(:disabled):hover {
      transform: translateY(-1px);
      box-shadow: 0 10px 20px rgba(20, 32, 40, 0.12);
    }
    main {
      padding: 24px;
      overflow: auto;
    }
    .topbar {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 20px;
    }
    .topbar h2 {
      margin: 0 0 5px;
      font-size: 24px;
      line-height: 1.2;
    }
    .topbar p {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(250px, 1fr));
      gap: 16px;
    }
    section.panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      min-width: 0;
    }
    .panelHead {
      min-height: 68px;
      border-bottom: 1px solid var(--line);
      padding: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .panelHead h3 {
      margin: 0;
      font-size: 16px;
      line-height: 1.25;
    }
    .panelBody {
      padding: 16px;
      display: grid;
      gap: 12px;
    }
    label.field {
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    input, select {
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--field);
      color: var(--ink);
      padding: 8px 10px;
      font: inherit;
      font-size: 14px;
    }
    input[type="checkbox"] {
      width: 18px;
      min-height: 18px;
      accent-color: var(--green);
    }
    .two {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .toggle {
      min-height: 42px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 10px;
      color: var(--ink);
      background: #ffffff;
      font-size: 13px;
      font-weight: 720;
    }
    .logPanel {
      margin-top: 16px;
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
      gap: 16px;
    }
    pre {
      margin: 0;
      min-height: 320px;
      max-height: 520px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
      background: #111b21;
      color: #d9e8ec;
      border-radius: 8px;
      padding: 16px;
      font: 12px/1.55 "Sarabun", ui-sans-serif, system-ui, sans-serif;
    }
    .outputs {
      display: grid;
      gap: 10px;
      padding: 16px;
    }
    .pathLine {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #ffffff;
      min-height: 56px;
    }
    .pathLine b {
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 4px;
    }
    .pathLine span {
      display: block;
      color: var(--ink);
      font-size: 13px;
      line-height: 1.35;
      word-break: break-word;
    }
    @media (max-width: 1120px) {
      .shell { grid-template-columns: 1fr; }
      aside { position: static; }
      .grid, .logPanel { grid-template-columns: 1fr; }
    }
    @media (max-width: 620px) {
      main { padding: 16px; }
      .topbar { display: grid; }
      .two { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <div class="brand">
        <h1>Bird Nest Pipeline Panel</h1>
        <p>Crop generation, backtest selection, and anomaly review in one local workflow.</p>
      </div>
      <div class="statusBox">
        <div class="statusLine">
          <span>Run status</span>
          <span id="statusPill" class="pill">Idle</span>
        </div>
        <div id="statusMeta" class="meta">Ready.</div>
      </div>
      <button id="runButton" class="primary">Run Pipeline</button>
      <button id="refreshButton" class="secondary">Refresh Status</button>
    </aside>

    <main>
      <div class="topbar">
        <div>
          <h2>Pipeline Configuration</h2>
          <p>Choose the stages and tune the values before running the full flow.</p>
        </div>
      </div>

      <div class="grid">
        <section class="panel">
          <div class="panelHead">
            <h3>Crop Stage</h3>
            <label class="toggle"><span>Run</span><input id="stepCrop" type="checkbox"></label>
          </div>
          <div class="panelBody">
            <div class="two">
              <label class="field">Raw dir<input id="cropRawDir" value="RawPics"></label>
              <label class="field">Output dir<input id="cropOutputDir" value="Crops"></label>
            </div>
            <div class="two">
              <label class="field">Patch size<input id="patchSize" type="number" min="64" value="256"></label>
              <label class="field">Coverage step<input id="coverageStep" type="number" min="1" value="48"></label>
            </div>
            <div class="two">
              <label class="field">Min edge shift<input id="minEdgeShift" type="number" min="0" value="24"></label>
              <label class="field">Mask dilation<input id="maskDilation" type="number" min="0" value="20"></label>
            </div>
            <div class="two">
              <label class="field">Min content<input id="minContentRatio" type="number" step="0.01" min="0" max="1" value="0.35"></label>
              <label class="field">Random seed<input id="cropSeed" type="number" value="42"></label>
            </div>
            <div class="two">
              <label class="field">Jitter crops<input id="positiveJitterCrops" type="number" min="0" value="3"></label>
              <label class="field">Jitter radius<input id="positiveJitterRadius" type="number" min="0" value="64"></label>
            </div>
            <label class="field">Dirty crop source
              <select id="dirtyCropSource">
                <option value="registered_original">registered_original</option>
                <option value="matched_original">matched_original</option>
                <option value="inpainted_marked">inpainted_marked</option>
              </select>
            </label>
            <label class="toggle"><span>Generate clean</span><input id="generateClean" type="checkbox" checked></label>
            <label class="toggle"><span>Generate dirty</span><input id="generateDirty" type="checkbox" checked></label>
            <label class="toggle"><span>Clear output first</span><input id="clearOutput" type="checkbox"></label>
          </div>
        </section>

        <section class="panel">
          <div class="panelHead">
            <h3>BacktestSelection</h3>
            <label class="toggle"><span>Run</span><input id="stepBacktest" type="checkbox" checked></label>
          </div>
          <div class="panelBody">
            <div class="two">
              <label class="field">Crops dir<input id="backtestCropsDir" value="Crops"></label>
              <label class="field">Output root<input id="backtestOutputDir" value="BacktestSelection"></label>
            </div>
            <div class="two">
              <label class="field">Clean target<input id="cleanTarget" type="number" min="1" value="300"></label>
              <label class="field">Dirty pair target<input id="dirtyPairTarget" type="number" min="1" value="200"></label>
            </div>
            <label class="toggle"><span>Copy selected files</span><input id="copyFiles" type="checkbox" checked></label>
            <label class="toggle"><span>Source diversity</span><input id="sourceDiversity" type="checkbox" checked></label>
          </div>
        </section>

        <section class="panel">
          <div class="panelHead">
            <h3>Anomaly Detection</h3>
            <label class="toggle"><span>Run</span><input id="stepAnomaly" type="checkbox" checked></label>
          </div>
          <div class="panelBody">
            <label class="field">Backtest run<input id="backtestRun" placeholder="blank = latest or current run"></label>
            <div class="two">
              <label class="field">Backtest root<input id="anomalyBacktestRoot" value="BacktestSelection"></label>
              <label class="field">Output root<input id="anomalyOutputDir" value="AnomalyDetection"></label>
            </div>
            <div class="two">
              <label class="field">Contamination<input id="contamination" type="number" step="0.01" min="0" max="0.5" value="0.08"></label>
              <label class="field">Threshold<input id="consensusThreshold" type="number" step="0.01" min="0" max="1" value="0.85"></label>
            </div>
            <div class="two">
              <label class="field">Min votes<input id="minVotes" type="number" min="1" max="3" value="2"></label>
              <label class="field">Top previews<input id="topN" type="number" min="1" value="24"></label>
            </div>
            <label class="toggle"><span>Isolation Forest</span><input id="methodIsolation" type="checkbox" checked></label>
            <label class="toggle"><span>Local Outlier Factor</span><input id="methodLof" type="checkbox" checked></label>
            <label class="toggle"><span>PCA reconstruction</span><input id="methodPca" type="checkbox" checked></label>
            <div class="two">
              <label class="field">Trees<input id="isolationTrees" type="number" min="1" value="96"></label>
              <label class="field">Subsample<input id="isolationSubsample" type="number" min="2" value="256"></label>
            </div>
            <div class="two">
              <label class="field">LOF neighbors<input id="neighborK" type="number" min="2" value="20"></label>
              <label class="field">PCA components<input id="pcaComponents" type="number" min="1" value="6"></label>
            </div>
            <label class="toggle"><span>Create previews</span><input id="makePreviews" type="checkbox" checked></label>
            <label class="toggle"><span>Copy anomaly files</span><input id="copyAnomalies" type="checkbox"></label>
          </div>
        </section>
      </div>

      <div class="logPanel">
        <section class="panel">
          <div class="panelHead"><h3>Run Log</h3></div>
          <pre id="runLog">Ready.</pre>
        </section>
        <section class="panel">
          <div class="panelHead"><h3>Outputs</h3></div>
          <div id="outputs" class="outputs"></div>
        </section>
      </div>
    </main>
  </div>

  <script>
    const $ = (id) => document.getElementById(id);
    const numberValue = (id) => Number($(id).value);
    const textValue = (id) => $(id).value.trim();
    const checked = (id) => $(id).checked;

    function collectConfig() {
      return {
        steps: {
          crop: checked("stepCrop"),
          backtest: checked("stepBacktest"),
          anomaly: checked("stepAnomaly")
        },
        crop: {
          rawDir: textValue("cropRawDir"),
          outputDir: textValue("cropOutputDir"),
          patchSize: numberValue("patchSize"),
          coverageStep: numberValue("coverageStep"),
          minEdgeShift: numberValue("minEdgeShift"),
          maskDilation: numberValue("maskDilation"),
          minContentRatio: numberValue("minContentRatio"),
          positiveJitterCrops: numberValue("positiveJitterCrops"),
          positiveJitterRadius: numberValue("positiveJitterRadius"),
          minBlueComponentArea: 20,
          randomSeed: numberValue("cropSeed"),
          dirtyCropSource: textValue("dirtyCropSource"),
          generateClean: checked("generateClean"),
          generateDirty: checked("generateDirty"),
          clearOutput: checked("clearOutput")
        },
        backtest: {
          cropsDir: textValue("backtestCropsDir"),
          outputDir: textValue("backtestOutputDir"),
          cleanTarget: numberValue("cleanTarget"),
          dirtyPairTarget: numberValue("dirtyPairTarget"),
          copyFiles: checked("copyFiles"),
          sourceDiversity: checked("sourceDiversity")
        },
        anomaly: {
          backtestRun: textValue("backtestRun"),
          backtestRoot: textValue("anomalyBacktestRoot"),
          cropsDir: textValue("backtestCropsDir"),
          outputDir: textValue("anomalyOutputDir"),
          contamination: numberValue("contamination"),
          consensusThreshold: numberValue("consensusThreshold"),
          minVotes: numberValue("minVotes"),
          isolationForest: checked("methodIsolation"),
          lof: checked("methodLof"),
          pca: checked("methodPca"),
          isolationTrees: numberValue("isolationTrees"),
          isolationSubsample: numberValue("isolationSubsample"),
          neighborK: numberValue("neighborK"),
          pcaComponents: numberValue("pcaComponents"),
          topN: numberValue("topN"),
          randomSeed: 42,
          makePreviews: checked("makePreviews"),
          copyAnomalies: checked("copyAnomalies")
        }
      };
    }

    function renderStatus(data) {
      const pill = $("statusPill");
      pill.className = "pill";
      if (data.running) pill.classList.add("running");
      if (data.status === "complete") pill.classList.add("done");
      if (data.status === "error") pill.classList.add("error");
      pill.textContent = data.running ? "Running" : data.status;
      $("runButton").disabled = data.running;

      const bits = [];
      if (data.started_at) bits.push("Started: " + data.started_at);
      if (data.finished_at) bits.push("Finished: " + data.finished_at);
      if (data.error) bits.push("Error: " + data.error);
      $("statusMeta").textContent = bits.join("\n") || "Ready.";
      $("runLog").textContent = (data.logs || []).join("\n") || "Ready.";

      const outputs = data.outputs || {};
      const outputBox = $("outputs");
      outputBox.innerHTML = "";
      const keys = Object.keys(outputs);
      if (!keys.length) {
        outputBox.innerHTML = '<div class="pathLine"><b>Nothing yet</b><span>Run the pipeline to create outputs.</span></div>';
      } else {
        keys.forEach((key) => {
          const div = document.createElement("div");
          const label = document.createElement("b");
          const value = document.createElement("span");
          div.className = "pathLine";
          label.textContent = key;
          value.textContent = outputs[key];
          div.appendChild(label);
          div.appendChild(value);
          outputBox.appendChild(div);
        });
      }
      const pre = $("runLog");
      pre.scrollTop = pre.scrollHeight;
    }

    async function refreshStatus() {
      const response = await fetch("/api/status");
      renderStatus(await response.json());
    }

    async function runPipeline() {
      const response = await fetch("/api/run", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(collectConfig())
      });
      const data = await response.json();
      renderStatus(data);
    }

    $("runButton").addEventListener("click", runPipeline);
    $("refreshButton").addEventListener("click", refreshStatus);
    refreshStatus();
    setInterval(refreshStatus, 1400);
  </script>
</body>
</html>
"""


def timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def update_state(**changes: object) -> None:
    with STATE_LOCK:
        RUN_STATE.update(changes)


def append_log(line: str) -> None:
    with STATE_LOCK:
        logs = RUN_STATE["logs"]
        logs.append(line.rstrip())
        if len(logs) > MAX_LOG_LINES:
            del logs[: len(logs) - MAX_LOG_LINES]


def set_output(key: str, value: str) -> None:
    with STATE_LOCK:
        outputs = RUN_STATE["outputs"]
        outputs[key] = value


def snapshot_state() -> dict:
    with STATE_LOCK:
        return {
            "running": RUN_STATE["running"],
            "started_at": RUN_STATE["started_at"],
            "finished_at": RUN_STATE["finished_at"],
            "status": RUN_STATE["status"],
            "error": RUN_STATE["error"],
            "logs": list(RUN_STATE["logs"]),
            "outputs": dict(RUN_STATE["outputs"]),
        }


def merged_config(config: dict) -> dict:
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    for section, section_value in config.items():
        if isinstance(section_value, dict) and isinstance(merged.get(section), dict):
            merged[section].update(section_value)
        else:
            merged[section] = section_value
    return merged


def ensure_bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be true or false")
    return value


def ensure_number(
    value: object,
    field_name: str,
    minimum: float,
    maximum: float,
    *,
    integer: bool = False,
) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    number = int(value) if integer else float(value)
    if integer and number != value:
        raise ValueError(f"{field_name} must be an integer")
    if number < minimum or number > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
    return number


def ensure_choice(value: object, field_name: str, choices: set[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"{field_name} must be one of: {', '.join(sorted(choices))}")
    return value


def ensure_project_path(value: object, field_name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a path string")
    text = value.strip()
    if not text:
        if allow_empty:
            return ""
        raise ValueError(f"{field_name} must not be empty")
    path = Path(text)
    if path.is_absolute():
        raise ValueError(f"{field_name} must be relative to the project folder")
    if any(part == ".." for part in path.parts):
        raise ValueError(f"{field_name} must stay inside the project folder")
    resolved = (BASE_DIR / path).resolve()
    try:
        resolved.relative_to(BASE_DIR)
    except ValueError as exc:
        raise ValueError(f"{field_name} must stay inside the project folder") from exc
    return str(path)


def validate_config(config: dict) -> dict:
    if not isinstance(config, dict):
        raise ValueError("config must be a JSON object")

    validated = merged_config(config)

    steps = validated["steps"]
    for key in ("crop", "backtest", "anomaly"):
        steps[key] = ensure_bool(steps[key], f"steps.{key}")

    crop = validated["crop"]
    crop["rawDir"] = ensure_project_path(crop["rawDir"], "crop.rawDir")
    crop["outputDir"] = ensure_project_path(crop["outputDir"], "crop.outputDir")
    crop["patchSize"] = ensure_number(crop["patchSize"], "crop.patchSize", 32, 4096, integer=True)
    crop["coverageStep"] = ensure_number(crop["coverageStep"], "crop.coverageStep", 1, 4096, integer=True)
    crop["minEdgeShift"] = ensure_number(crop["minEdgeShift"], "crop.minEdgeShift", 0, 4096, integer=True)
    crop["maskDilation"] = ensure_number(crop["maskDilation"], "crop.maskDilation", 0, 512, integer=True)
    crop["minContentRatio"] = ensure_number(crop["minContentRatio"], "crop.minContentRatio", 0.0, 1.0)
    crop["positiveJitterCrops"] = ensure_number(
        crop["positiveJitterCrops"],
        "crop.positiveJitterCrops",
        0,
        100,
        integer=True,
    )
    crop["positiveJitterRadius"] = ensure_number(
        crop["positiveJitterRadius"],
        "crop.positiveJitterRadius",
        0,
        4096,
        integer=True,
    )
    crop["minBlueComponentArea"] = ensure_number(
        crop["minBlueComponentArea"],
        "crop.minBlueComponentArea",
        1,
        1_000_000,
        integer=True,
    )
    crop["randomSeed"] = ensure_number(crop["randomSeed"], "crop.randomSeed", 0, 2**31 - 1, integer=True)
    crop["dirtyCropSource"] = ensure_choice(
        crop["dirtyCropSource"],
        "crop.dirtyCropSource",
        {"registered_original", "matched_original", "inpainted_marked"},
    )
    for key in ("generateClean", "generateDirty", "clearOutput"):
        crop[key] = ensure_bool(crop[key], f"crop.{key}")

    backtest = validated["backtest"]
    backtest["cropsDir"] = ensure_project_path(backtest["cropsDir"], "backtest.cropsDir")
    backtest["outputDir"] = ensure_project_path(backtest["outputDir"], "backtest.outputDir")
    backtest["cleanTarget"] = ensure_number(
        backtest["cleanTarget"],
        "backtest.cleanTarget",
        0,
        1_000_000,
        integer=True,
    )
    backtest["dirtyPairTarget"] = ensure_number(
        backtest["dirtyPairTarget"],
        "backtest.dirtyPairTarget",
        0,
        1_000_000,
        integer=True,
    )
    for key in ("copyFiles", "sourceDiversity"):
        backtest[key] = ensure_bool(backtest[key], f"backtest.{key}")

    anomaly = validated["anomaly"]
    anomaly["backtestRun"] = ensure_project_path(
        anomaly["backtestRun"],
        "anomaly.backtestRun",
        allow_empty=True,
    )
    anomaly["backtestRoot"] = ensure_project_path(anomaly["backtestRoot"], "anomaly.backtestRoot")
    anomaly["cropsDir"] = ensure_project_path(anomaly["cropsDir"], "anomaly.cropsDir")
    anomaly["outputDir"] = ensure_project_path(anomaly["outputDir"], "anomaly.outputDir")
    anomaly["contamination"] = ensure_number(anomaly["contamination"], "anomaly.contamination", 0.0, 0.5)
    anomaly["consensusThreshold"] = ensure_number(
        anomaly["consensusThreshold"],
        "anomaly.consensusThreshold",
        0.0,
        1.0,
    )
    anomaly["minVotes"] = ensure_number(anomaly["minVotes"], "anomaly.minVotes", 1, 3, integer=True)
    anomaly["isolationTrees"] = ensure_number(
        anomaly["isolationTrees"],
        "anomaly.isolationTrees",
        1,
        10_000,
        integer=True,
    )
    anomaly["isolationSubsample"] = ensure_number(
        anomaly["isolationSubsample"],
        "anomaly.isolationSubsample",
        2,
        1_000_000,
        integer=True,
    )
    anomaly["neighborK"] = ensure_number(anomaly["neighborK"], "anomaly.neighborK", 2, 1_000_000, integer=True)
    anomaly["pcaComponents"] = ensure_number(
        anomaly["pcaComponents"],
        "anomaly.pcaComponents",
        1,
        10_000,
        integer=True,
    )
    anomaly["topN"] = ensure_number(anomaly["topN"], "anomaly.topN", 1, 1_000, integer=True)
    anomaly["randomSeed"] = ensure_number(anomaly["randomSeed"], "anomaly.randomSeed", 0, 2**31 - 1, integer=True)
    for key in ("isolationForest", "lof", "pca", "makePreviews", "copyAnomalies"):
        anomaly[key] = ensure_bool(anomaly[key], f"anomaly.{key}")

    return validated


def parse_run_config(payload: bytes, content_length: int) -> dict:
    if content_length > MAX_REQUEST_BYTES:
        raise ValueError("Request body is too large")
    text = payload.decode("utf-8") if payload else "{}"
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc.msg}") from exc
    return validate_config(decoded)


def maybe_add_flag(command: list[str], condition: bool, flag: str) -> None:
    if condition:
        command.append(flag)


def crop_command(config: dict) -> list[str]:
    crop = config["crop"]
    command = [
        sys.executable,
        str(BASE_DIR / "crop_clean_patches.py"),
        "--raw-dir",
        str(crop["rawDir"]),
        "--output-dir",
        str(crop["outputDir"]),
        "--patch-size",
        str(crop["patchSize"]),
        "--coverage-step",
        str(crop["coverageStep"]),
        "--min-edge-shift",
        str(crop["minEdgeShift"]),
        "--mask-dilation",
        str(crop["maskDilation"]),
        "--min-content-ratio",
        str(crop["minContentRatio"]),
        "--positive-jitter-crops",
        str(crop["positiveJitterCrops"]),
        "--positive-jitter-radius",
        str(crop["positiveJitterRadius"]),
        "--min-blue-component-area",
        str(crop["minBlueComponentArea"]),
        "--random-seed",
        str(crop["randomSeed"]),
        "--dirty-crop-source",
        str(crop["dirtyCropSource"]),
    ]
    maybe_add_flag(command, not bool(crop["generateClean"]), "--no-clean")
    maybe_add_flag(command, not bool(crop["generateDirty"]), "--no-dirty")
    maybe_add_flag(command, bool(crop["clearOutput"]), "--clear-output")
    maybe_add_flag(command, not bool(crop["clearOutput"]), "--keep-existing")
    return command


def backtest_command(config: dict) -> list[str]:
    backtest = config["backtest"]
    command = [
        sys.executable,
        str(BASE_DIR / "select_birdnest_samples.py"),
        "--crops-dir",
        str(backtest["cropsDir"]),
        "--output-dir",
        str(backtest["outputDir"]),
        "--clean-target",
        str(backtest["cleanTarget"]),
        "--dirty-pair-target",
        str(backtest["dirtyPairTarget"]),
    ]
    maybe_add_flag(command, not bool(backtest["copyFiles"]), "--no-copy")
    maybe_add_flag(command, not bool(backtest["sourceDiversity"]), "--no-diversity")
    return command


def anomaly_command(config: dict) -> list[str]:
    anomaly = config["anomaly"]
    methods: list[str] = []
    if anomaly["isolationForest"]:
        methods.append("isolation_forest")
    if anomaly["lof"]:
        methods.append("lof")
    if anomaly["pca"]:
        methods.append("pca")
    if not methods:
        methods = ["isolation_forest", "lof", "pca"]

    command = [
        sys.executable,
        str(BASE_DIR / "anomaly_detection.py"),
        "--backtest-root",
        str(anomaly["backtestRoot"]),
        "--crops-dir",
        str(anomaly["cropsDir"]),
        "--output-dir",
        str(anomaly["outputDir"]),
        "--methods",
        ",".join(methods),
        "--contamination",
        str(anomaly["contamination"]),
        "--consensus-threshold",
        str(anomaly["consensusThreshold"]),
        "--min-votes",
        str(anomaly["minVotes"]),
        "--isolation-trees",
        str(anomaly["isolationTrees"]),
        "--isolation-subsample",
        str(anomaly["isolationSubsample"]),
        "--neighbor-k",
        str(anomaly["neighborK"]),
        "--pca-components",
        str(anomaly["pcaComponents"]),
        "--top-n",
        str(anomaly["topN"]),
        "--random-seed",
        str(anomaly["randomSeed"]),
    ]
    if anomaly.get("backtestRun"):
        command.extend(["--backtest-run", str(anomaly["backtestRun"])])
    maybe_add_flag(command, not bool(anomaly["makePreviews"]), "--no-previews")
    maybe_add_flag(command, bool(anomaly["copyAnomalies"]), "--copy-anomalies")
    return command


def command_for_log(command: list[str]) -> str:
    return " ".join(f'"{part}"' if " " in part else part for part in command)


def parse_output_line(line: str) -> None:
    if line.startswith("Run directory:"):
        set_output("backtest_run", line.split(":", 1)[1].strip())
    elif line.startswith("Comparison:"):
        set_output("backtest_comparison", line.split(":", 1)[1].strip())
    elif line.startswith("Output directory:"):
        set_output("anomaly_run", line.split(":", 1)[1].strip())
    elif line.startswith("Review CSV:"):
        set_output("anomaly_review", line.split(":", 1)[1].strip())


def run_command(name: str, command: list[str]) -> None:
    append_log("")
    append_log(f"[{timestamp()}] {name}")
    append_log(command_for_log(command))
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        command,
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=creationflags,
    )
    assert process.stdout is not None
    for line in process.stdout:
        append_log(line)
        parse_output_line(line.strip())
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"{name} failed with exit code {return_code}")


def run_pipeline(config: dict) -> None:
    config = validate_config(config)
    update_state(
        running=True,
        started_at=timestamp(),
        finished_at="",
        status="running",
        error="",
        logs=[],
        outputs={},
    )
    append_log("Pipeline started.")
    try:
        if config["steps"].get("crop"):
            run_command("Crop generation", crop_command(config))
        if config["steps"].get("backtest"):
            run_command("BacktestSelection", backtest_command(config))
        if config["steps"].get("anomaly"):
            if config["steps"].get("backtest") and not config["anomaly"].get("backtestRun"):
                latest_backtest = snapshot_state()["outputs"].get("backtest_run", "")
                if latest_backtest:
                    config["anomaly"]["backtestRun"] = latest_backtest
            run_command("Anomaly detection", anomaly_command(config))
        append_log("")
        append_log("Pipeline complete.")
        update_state(running=False, finished_at=timestamp(), status="complete")
    except Exception as exc:
        append_log("")
        append_log(f"ERROR: {exc}")
        update_state(
            running=False,
            finished_at=timestamp(),
            status="error",
            error=str(exc),
        )


class PanelHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self.send_text(INDEX_HTML, "text/html; charset=utf-8")
        elif path == "/api/status":
            self.send_json(snapshot_state())
        elif path == "/api/defaults":
            self.send_json(DEFAULT_CONFIG)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/run":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        with STATE_LOCK:
            if RUN_STATE["running"]:
                self.send_json(snapshot_state(), status=HTTPStatus.CONFLICT)
                return

        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length > MAX_REQUEST_BYTES:
                self.send_json({"error": "Request body is too large"}, status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                return
            payload = self.rfile.read(length) if length else b"{}"
            config = parse_run_config(payload, length)
        except (UnicodeDecodeError, ValueError) as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        thread = threading.Thread(target=run_pipeline, args=(config,), daemon=True)
        thread.start()
        self.send_json(snapshot_state())

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text: str, content_type: str) -> None:
        body = text.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local bird-nest pipeline panel.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8769)
    parser.add_argument("--open", action="store_true", help="Open the panel in the default browser.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), PanelHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"Project panel running at {url}")
    if args.open:
        webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
