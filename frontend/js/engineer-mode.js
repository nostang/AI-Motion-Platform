document.addEventListener("DOMContentLoaded", () => {
  "use strict";

  const toggle = document.getElementById("engineerToggle");
  const panel = document.getElementById("engineerMode");
  const state = document.getElementById("engineerState");
  const sections = document.getElementById("engineerSections");
  const exportCsv = document.getElementById("engineerExportCsv");
  if (
    !toggle
    || !panel
    || !state
    || !sections
    || !exportCsv
  ) return;

  let loaded = false;
  let engineerPayload = null;

  function assessmentId() {
    const query = new URLSearchParams(window.location.search);
    return query.get("id") || query.get("assessment_id");
  }

  function text(value) {
    if (value === null || value === undefined || value === "") return "--";
    if (typeof value === "boolean") return value ? "是" : "否";
    if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(4)));
    if (typeof value === "object") return JSON.stringify(value, null, 2);
    return String(value);
  }

  function compact(value) {
    if (value === null || value === undefined) return "--";
    if (typeof value !== "object") return text(value);
    return Object.entries(value)
      .filter(([, item]) => item !== null && item !== undefined)
      .map(([key, item]) => `${key}: ${typeof item === "object" ? JSON.stringify(item) : text(item)}`)
      .join(" · ") || "--";
  }

  function csvCell(value) {
    const raw = value === null || value === undefined
      ? ""
      : String(value);
    return `"${raw.replaceAll('"', '""')}"`;
  }

  function flattenEvidence(value, path, rows) {
    if (value === null || value === undefined) {
      rows.push([path, ""]);
      return;
    }

    if (Array.isArray(value)) {
      if (!value.length) {
        rows.push([path, "[]"]);
        return;
      }
      value.forEach((item, index) => {
        flattenEvidence(
          item,
          `${path}[${index}]`,
          rows
        );
      });
      return;
    }

    if (typeof value === "object") {
      const entries = Object.entries(value);
      if (!entries.length) {
        rows.push([path, "{}"]);
        return;
      }
      entries.forEach(([key, item]) => {
        flattenEvidence(
          item,
          path ? `${path}.${key}` : key,
          rows
        );
      });
      return;
    }

    rows.push([path, value]);
  }

  function exportEvidenceCsv() {
    if (!engineerPayload) return;

    const rows = [];
    flattenEvidence(engineerPayload, "", rows);
    const id = (
      engineerPayload.assessment?.assessment_id
      || assessmentId()
      || "unknown"
    );
    const motion = (
      engineerPayload.assessment?.motion_type
      || "unknown"
    );
    const header = [
      "assessment_id",
      "motion_type",
      "evidence_path",
      "value"
    ];
    const csvRows = [header, ...rows.map(([path, value]) => [
      id,
      motion,
      path,
      value
    ])];
    const content = "\ufeff" + csvRows
      .map((row) => row.map(csvCell).join(","))
      .join("\r\n");
    const blob = new Blob(
      [content],
      { type: "text/csv;charset=utf-8" }
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const safeId = String(id).replaceAll(
      /[^a-zA-Z0-9_-]/g,
      "_"
    );
    link.href = url;
    link.download = `ai_motion_engineer_${motion}_${safeId}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function article(title, subtitle) {
    const node = document.createElement("article");
    node.className = "engineer-section";
    const header = document.createElement("header");
    const heading = document.createElement("h3");
    const source = document.createElement("span");
    heading.textContent = title;
    source.textContent = subtitle;
    header.append(heading, source);
    const body = document.createElement("div");
    body.className = "engineer-body";
    node.append(header, body);
    return { node, body };
  }

  function overview(rows) {
    const { node, body } = article("分析摘要", "BACKEND EVIDENCE");
    const grid = document.createElement("dl");
    grid.className = "engineer-overview";
    rows.forEach((row) => {
      const item = document.createElement("div");
      const label = document.createElement("dt");
      const value = document.createElement("dd");
      label.textContent = row.label;
      value.textContent = compact(row.value) + (row.unit && row.value !== null ? ` ${row.unit}` : "");
      item.append(label, value);
      grid.appendChild(item);
    });
    body.appendChild(grid);
    return node;
  }

  function measurementLines(row, field) {
    const wrapper = document.createElement("div");
    wrapper.className = "engineer-lines";
    (row.measurements || []).forEach((measurement) => {
      const line = document.createElement("div");
      if (field === "feature") line.textContent = measurement.feature || "--";
      if (field === "value") line.textContent = `${compact(measurement.value)}${measurement.unit ? ` ${measurement.unit}` : ""}`;
      if (field === "threshold") line.textContent = compact(measurement.threshold);
      wrapper.appendChild(line);
    });
    if (!wrapper.children.length) wrapper.textContent = "--";
    return wrapper;
  }

  function scoring(rows, overallScore) {
    const { node, body } = article("評分來源", "STORED SCORE · NO FRONTEND RESCORING");
    const scroll = document.createElement("div");
    scroll.className = "engineer-table-scroll";
    const table = document.createElement("table");
    table.className = "engineer-wide-table";
    const headings = ["項目", "Feature", "實測值", "判定門檻", "等級", "得分", "計入總分"];
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    headings.forEach((label) => {
      const th = document.createElement("th");
      th.textContent = label;
      headRow.appendChild(th);
    });
    head.appendChild(headRow);
    const tbody = document.createElement("tbody");
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      const values = [
        row.label,
        measurementLines(row, "feature"),
        measurementLines(row, "value"),
        measurementLines(row, "threshold"),
        row.level || "--",
        `${text(row.score)} / ${text(row.max_score)}`,
        row.included_in_overall ? "是" : "否（診斷）"
      ];
      values.forEach((value, index) => {
        const cell = document.createElement("td");
        cell.dataset.label = headings[index];
        if (value instanceof Node) cell.appendChild(value);
        else cell.textContent = value;
        if (index === 4 && value !== "--") cell.dataset.level = String(value).toLowerCase();
        if (index === 6) cell.dataset.included = String(row.included_in_overall);
        tr.appendChild(cell);
      });
      tbody.appendChild(tr);
    });
    table.append(head, tbody);
    scroll.appendChild(table);
    body.appendChild(scroll);
    const total = document.createElement("p");
    total.className = "engineer-total";
    total.textContent = `Backend 最終總分：${text(overallScore)} / 100`;
    body.appendChild(total);
    return node;
  }

  function detailsTable(detail) {
    const isEvents = detail.kind === "EVENTS";
    const { node, body } = article(isEvents ? "Event 解析" : "Window 解析", "PIPELINE TRACE");
    const rows = detail.rows || [];
    const keys = isEvents
      ? ["event", "direction", "move_s", "recovery_s", "total_s", "completion", "return", "confidence"]
      : ["name", "source", "status", "start_ms", "end_ms", "duration_ms", "duration_seconds"];
    const labels = {
      event: "編號", direction: "方向", move_s: "移動(s)", recovery_s: "回位(s)",
      total_s: "總計(s)", completion: "完成方式", return: "回中心", confidence: "信心",
      name: "區間", source: "來源", status: "狀態", start_ms: "開始(ms)",
      end_ms: "結束(ms)", duration_ms: "長度(ms)", duration_seconds: "長度(s)"
    };
    const scroll = document.createElement("div");
    scroll.className = "engineer-table-scroll";
    const table = document.createElement("table");
    table.className = `engineer-wide-table engineer-detail-table ${isEvents ? "engineer-event-table" : "engineer-window-table"}`;
    const thead = document.createElement("thead");
    const header = document.createElement("tr");
    keys.forEach((key) => {
      const th = document.createElement("th");
      th.textContent = labels[key] || key;
      header.appendChild(th);
    });
    thead.appendChild(header);
    const tbody = document.createElement("tbody");
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      keys.forEach((key) => {
        const td = document.createElement("td");
        td.dataset.label = labels[key] || key;
        td.textContent = compact(row[key]);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.append(thead, tbody);
    scroll.appendChild(table);
    body.appendChild(scroll);
    return node;
  }

  function rawJson(payload) {
    const details = document.createElement("details");
    details.className = "engineer-raw";
    const summary = document.createElement("summary");
    summary.textContent = "查看 Raw JSON（工程稽核）";
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(payload, null, 2);
    details.append(summary, pre);
    return details;
  }

  function render(payload) {
    const presentation = payload.presentation || {};
    const overall = payload.scoring_evidence?.overall_score
      ?? payload.scoring_evidence?.public_report_summary?.overall_score
      ?? "--";
    sections.innerHTML = "";
    sections.append(
      overview(presentation.overview_rows || []),
      scoring(presentation.score_rows || [], overall),
      detailsTable(presentation.detail || {}),
      rawJson(payload)
    );
    engineerPayload = payload;
    exportCsv.hidden = false;
    state.hidden = true;
  }

  async function load() {
    if (loaded) return;
    const id = assessmentId();
    if (!id) {
      state.textContent = "缺少 Assessment ID。";
      state.dataset.status = "error";
      return;
    }
    state.hidden = false;
    state.textContent = "正在讀取工程證據…";
    try {
      const response = await window.motionAPI.getEngineerDebug(id);
      if (!response?.success) throw new Error(response?.error?.message || "工程證據讀取失敗");
      render(response.data);
      loaded = true;
    } catch (error) {
      state.textContent = `工程模式載入失敗：${error.message || "未知錯誤"}`;
      state.dataset.status = "error";
    }
  }

  async function setOpen(open) {
    panel.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    toggle.textContent = open ? "關閉工程模式" : "工程模式";
    if (open) {
      await load();
      panel.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  toggle.addEventListener("click", () => setOpen(panel.hidden));
  exportCsv.addEventListener("click", exportEvidenceCsv);
  if (new URLSearchParams(window.location.search).get("engineer") === "1") setOpen(true);
});
