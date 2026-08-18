(() => {
  "use strict";

  const config = window.AI_MOTION_CONFIG || {};
  const apiBase = String(config.API_BASE_URL || "/api/v1").replace(/\/$/, "");
  const params = new URLSearchParams(window.location.search);
  const userId = Number(params.get("user_id")) || 1;
  const $ = (id) => document.getElementById(id);
  const elements = {
    loading: $("loadingState"), error: $("errorState"), errorMessage: $("errorMessage"),
    content: $("summaryContent"), retry: $("retryButton"), canvas: $("competencyRadar"),
    previousLegend: $("previousLegend"), comparisonNote: $("comparisonNote"), changes: $("axisChanges"),
    motions: $("motionCards"), headline: $("aiHeadline"), progress: $("progressSummary"),
    progressHighlights: $("progressHighlights"),
    historyChartWrap: $("historyTrendChartWrap"), historyChart: $("historyTrendChart"),
    historyDetail: $("historyTrendDetail"), historyEmpty: $("historyTrendEmpty"),
    focus: $("focusTags"), recommendations: $("recommendations"), hand: $("racketHand"),
    handConfidence: $("racketConfidence"), handContext:$("racketContext"), userReference: $("userReference")
  };
  let radarData = null;
  let radarHitPoints = [];
  let radarTooltip = null;
  let historyTrendData = null;
  let selectedHistoryMotion = "footwork";

  const directionLabels = { IMPROVED: "進步", DECLINED: "下降", UNCHANGED: "持平", NOT_INTERPRETED: "暫不解讀" };
  const motionLabels = { footwork: "步法", serve: "正手發球", clear: "高遠球" };

  const axisHelpText = {
    mobility: "綜合動作完成度、回位速度、方向覆蓋與動作品質。",
    preparation_quality: "綜合發球準備穩定度與高遠球側身準備。",
    swing_mechanics: "綜合發球揮拍完整度與高遠球揮拍流暢度。",
    body_coordination: "綜合身體協調、重心轉移與非持拍手平衡。",
    movement_stability: "綜合步法身體穩定度與發球動作流暢度。"
  };

  async function requestSummary() {
    const response = await fetch(`${apiBase}/users/${encodeURIComponent(userId)}/summary`);
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* handled below */ }
    if (!response.ok || !payload?.success) throw new Error(payload?.error?.message || `API request failed (${response.status})`);
    return payload.data;
  }

  async function requestHistoryTrend() {
    const response = await fetch(
      `${apiBase}/users/${encodeURIComponent(userId)}/history-trend`
    );
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* handled below */ }
    if (!response.ok || !payload?.success) {
      throw new Error(payload?.error?.message || `API request failed (${response.status})`);
    }
    return payload.data;
  }

  function number(value, fallback = null) { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : fallback; }
  function scoreText(value) { const n = number(value); return n === null ? "--" : Number.isInteger(n) ? String(n) : n.toFixed(1); }
  function historyDate(value) {
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return "日期未知";
    return new Intl.DateTimeFormat("zh-TW", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    }).format(date);
  }
  function showError(error) { elements.loading.hidden = true; elements.content.hidden = true; elements.error.hidden = false; elements.errorMessage.textContent = error?.message || "發生未知錯誤。"; }

  function renderComparison(competency) {
    const current = competency?.current?.radar_chart || {};
    const previous = competency?.previous?.radar_chart || {};
    const comparable = competency?.comparison_status === "COMPARABLE";
    radarData = {
      labels: Array.isArray(current.labels) ? current.labels : [],
      current: Array.isArray(current.scores) ? current.scores : [],
      previous: comparable && Array.isArray(previous.scores) ? previous.scores : null
    };
    elements.previousLegend.hidden = !radarData.previous;
    elements.comparisonNote.textContent = comparable
      ? "綠色為目前最新三項測驗整合結果；灰色虛線為三項動作各自的前一次可比較結果。"
      : "目前沒有完整且版本相容的前次資料，這次先顯示單一能力輪廓。";
    elements.changes.innerHTML = "";
    const changes = Array.isArray(competency?.changes) ? competency.changes : [];
    changes.forEach((entry) => {
      const direction = String(entry.direction || "NOT_INTERPRETED");
      const change = number(entry.change);
      const card = document.createElement("div");
      card.className = "axis-change";
      const titleRow = document.createElement("div");
      titleRow.className = "axis-title-row";

      const title = document.createElement("strong");
      title.textContent = entry.label || entry.key || "能力維度";

      const helpWrap = document.createElement("span");
      helpWrap.className = "axis-help-wrap";

      const helpButton = document.createElement("button");
      helpButton.type = "button";
      helpButton.className = "axis-help";
      helpButton.textContent = "?";
      helpButton.setAttribute("aria-label", `查看${title.textContent}包含項目`);
      helpButton.setAttribute("aria-expanded", "false");

      const tooltip = document.createElement("span");
      tooltip.className = "axis-tooltip";
      tooltip.setAttribute("role", "tooltip");
      tooltip.textContent =
        axisHelpText[entry.key] ||
        "此能力由目前支援的動作評估項目綜合整理。";

      helpButton.addEventListener("click", (event) => {
        event.stopPropagation();

        document.querySelectorAll(".axis-help-wrap.is-open").forEach((item) => {
          if (item !== helpWrap) {
            item.classList.remove("is-open");
            item.querySelector(".axis-help")?.setAttribute(
              "aria-expanded",
              "false"
            );
          }
        });

        const opened = helpWrap.classList.toggle("is-open");
        helpButton.setAttribute("aria-expanded", String(opened));
      });

      helpWrap.append(helpButton, tooltip);
      titleRow.append(title, helpWrap);

      const detail = document.createElement("small");
      detail.textContent =
        `前次 ${scoreText(entry.previous_score)} → 本次 ${scoreText(entry.current_score)}`;

      const delta = document.createElement("span");
      delta.className = `delta ${direction.toLowerCase()}`;
      delta.textContent =
        change === null
          ? directionLabels[direction]
          : `${change > 0 ? "+" : ""}${scoreText(change)}`;

      card.append(titleRow, detail, delta);
      elements.changes.appendChild(card);
    });
    if (!changes.length) {
      const empty = document.createElement("p");
      empty.className = "axis-comparison-empty";
      empty.textContent =
        "目前前次資料不足以完整比較能力維度，本次先顯示最新能力輪廓。";
      elements.changes.appendChild(empty);
    }
    drawRadar();
  }
  function ensureRadarTooltip() {
    if (radarTooltip) return radarTooltip;

    radarTooltip = document.createElement("div");
    radarTooltip.className = "radar-point-tooltip";
    radarTooltip.hidden = true;
    radarTooltip.setAttribute("role", "status");

    elements.canvas.parentElement.appendChild(radarTooltip);

    elements.canvas.addEventListener("pointermove", (event) => {
      if (event.pointerType === "mouse") {
        showRadarPointTooltip(event);
      }
    });

    elements.canvas.addEventListener("pointerdown", (event) => {
      showRadarPointTooltip(event);
    });

    elements.canvas.addEventListener("pointerleave", (event) => {
      if (event.pointerType === "mouse") {
        radarTooltip.hidden = true;
      }
    });

    return radarTooltip;
  }

  function showRadarPointTooltip(event) {
    const canvas = elements.canvas;
    const rect = canvas.getBoundingClientRect();
    const pointerX = event.clientX - rect.left;
    const pointerY = event.clientY - rect.top;

    let nearest = null;
    let nearestDistance = Infinity;

    radarHitPoints.forEach((item) => {
      const distance = Math.hypot(
        pointerX - item.x,
        pointerY - item.y
      );

      if (distance < nearestDistance) {
        nearest = item;
        nearestDistance = distance;
      }
    });

    const tooltip = ensureRadarTooltip();

    if (!nearest || nearestDistance > 30) {
      tooltip.hidden = true;
      return;
    }

    const previousText =
      nearest.previous === null
        ? ""
        : ` · 前次 ${scoreText(nearest.previous)}`;

    tooltip.textContent =
      `${nearest.label} · 本次 ${scoreText(nearest.current)}${previousText}`;

    tooltip.hidden = false;

    const parent = canvas.parentElement;
    const parentRect = parent.getBoundingClientRect();
    const canvasOffsetX = rect.left - parentRect.left;
    const canvasOffsetY = rect.top - parentRect.top;

    let left = canvasOffsetX + nearest.x;
    const top = canvasOffsetY + nearest.y - 16;
    const halfWidth = tooltip.offsetWidth / 2;

    left = Math.max(
      halfWidth + 8,
      Math.min(parent.clientWidth - halfWidth - 8, left)
    );

    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  }

  function drawRadar() {
    if (!radarData?.labels?.length) return;

    const canvas = elements.canvas;
    ensureRadarTooltip();

    const rect = canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(320, rect.width);
    const height = Math.max(360, rect.height);

    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);

    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const centerX = width / 2;
    const centerY = height / 2 + 8;
    const radius = Math.min(width, height) * 0.31;
    const count = radarData.labels.length;

    const point = (index, ratio) => {
      const angle =
        -Math.PI / 2 +
        (Math.PI * 2 * index) / count;

      return [
        centerX + Math.cos(angle) * radius * ratio,
        centerY + Math.sin(angle) * radius * ratio
      ];
    };

    ctx.lineWidth = 1.5;
    ctx.strokeStyle = "#b8ccc2";

    for (let level = 1; level <= 5; level += 1) {
      ctx.beginPath();

      for (let index = 0; index < count; index += 1) {
        const [x, y] = point(index, level / 5);
        index ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      }

      ctx.closePath();
      ctx.stroke();
    }

    for (let index = 0; index < count; index += 1) {
      const [x, y] = point(index, 1);
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.lineTo(x, y);
      ctx.stroke();
    }

    function polygon(values, stroke, fill, dashed) {
      if (!Array.isArray(values)) return;

      ctx.save();
      ctx.setLineDash(dashed ? [9, 7] : []);
      ctx.lineWidth = dashed ? 3 : 4;
      ctx.strokeStyle = stroke;
      ctx.fillStyle = fill;
      ctx.beginPath();

      values.forEach((value, index) => {
        const ratio = Math.max(
          0,
          Math.min(1, number(value, 0) / 100)
        );

        const [x, y] = point(index, ratio);
        index ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      });

      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      if (!dashed) {
        values.forEach((value, index) => {
          const ratio = Math.max(
            0,
            Math.min(1, number(value, 0) / 100)
          );

          const [x, y] = point(index, ratio);

          ctx.beginPath();
          ctx.arc(x, y, 6, 0, Math.PI * 2);
          ctx.fillStyle = "#d8ff52";
          ctx.fill();
          ctx.strokeStyle = "#075d3b";
          ctx.lineWidth = 3;
          ctx.stroke();
        });
      }

      ctx.restore();
    }

    polygon(
      radarData.previous,
      "#7d8b85",
      "rgba(125,139,133,.06)",
      true
    );

    polygon(
      radarData.current,
      "#08704c",
      "rgba(216,255,82,.26)",
      false
    );

    radarHitPoints = radarData.current.map((value, index) => {
      const ratio = Math.max(
        0,
        Math.min(1, number(value, 0) / 100)
      );

      const [x, y] = point(index, ratio);

      return {
        x,
        y,
        label: radarData.labels[index] || "能力維度",
        current: number(value),
        previous: Array.isArray(radarData.previous)
          ? number(radarData.previous[index])
          : null
      };
    });

    ctx.fillStyle = "#09271c";
    ctx.font = `800 ${width < 520 ? 13 : 16}px system-ui`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    radarData.labels.forEach((label, index) => {
      const [x, y] = point(index, 1.22);
      ctx.fillText(String(label), x, y);
    });
  }


  function renderMotions(motions) {
    elements.motions.innerHTML = "";
    (Array.isArray(motions) ? motions : []).forEach((motion) => {
      const score = number(motion.score);
const progress = motion.progress || {};
const direction = progress.direction;
const change = number(progress.change);
const hasCurrentScore = score !== null;
const hasComparison = (
  progress.status === "READY"
  && change !== null
  && direction
  && direction !== "NOT_INTERPRETED"
);

const normalizedLevel = (
  motion.level || ""
).toUpperCase();

const displayLevel = hasCurrentScore
  ? (normalizedLevel || "--")
  : "--";

const levelClass = normalizedLevel
  ? `level-${normalizedLevel.toLowerCase()}`
  : "level-empty";

const card = document.createElement("article");
card.className = "motion-card";

const header = document.createElement("header");
const title = document.createElement("h3");
title.textContent = (
  motion.label
  || motionLabels[motion.motion_type]
  || motion.motion_type
);

const level = document.createElement("span");
level.className =
  `motion-level ${levelClass}`;
level.textContent = displayLevel;
header.append(title, level);

const scoreNode = document.createElement("div");
scoreNode.className = "motion-score";
scoreNode.textContent = scoreText(score);

const max = document.createElement("small");
max.textContent = " / 100";
scoreNode.appendChild(max);

const track = document.createElement("div");
track.className = "motion-track";

const fill = document.createElement("div");
fill.className = "motion-fill";
fill.style.width = hasCurrentScore
  ? `${Math.max(0, Math.min(100, score))}%`
  : "0%";
track.appendChild(fill);

const progressNode = document.createElement("p");
progressNode.className = "motion-progress";

if (hasComparison) {
  progressNode.textContent = (
    `較前次 ${directionLabels[direction] || direction} `
    + `${change > 0 ? "+" : ""}${scoreText(change)}`
  );
} else if (hasCurrentScore) {
  progressNode.textContent =
    "首次測驗，尚無前次資料";
} else {
  progressNode.textContent =
    "尚未完成本次測驗";
}

const link = document.createElement("a");
      link.href =
        `report.html?id=${encodeURIComponent(motion.assessment_id || "")}` +
        `&from=summary&user_id=${encodeURIComponent(userId)}`;
      link.textContent = "查看單項報告 →";
      const retestLink = document.createElement("a");
      retestLink.className = "retest-link";
      retestLink.href =
        `/?motion=${encodeURIComponent(motion.motion_type)}` +
        `&source=summary&user_id=${encodeURIComponent(userId)}`;
      retestLink.textContent = "再測一次 ↻";

      const actions = document.createElement("div");
      actions.className = "motion-actions";
      actions.append(link, retestLink);

      card.append(
        header,
        scoreNode,
        track,
        progressNode,
        actions
      );
      elements.motions.appendChild(card);
    });
  }

  function svgNode(name, attributes = {}) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attributes).forEach(([key, value]) => {
      node.setAttribute(key, String(value));
    });
    return node;
  }

  function showHistoryPoint(point) {
    const timestamp = point.completed_at || point.created_at;
    elements.historyDetail.textContent = (
      `${historyDate(timestamp)} · ${scoreText(point.overall_score)} 分`
    );
  }

  function renderHistoryMotion(motionType) {
    selectedHistoryMotion = motionType;
    document.querySelectorAll("[data-history-motion]").forEach((button) => {
      button.setAttribute(
        "aria-selected",
        button.dataset.historyMotion === motionType ? "true" : "false"
      );
    });
    elements.historyChart.replaceChildren();
    const series = historyTrendData?.motions?.find(
      (item) => item?.motion_type === motionType
    );
    const points = Array.isArray(series?.points) ? series.points : [];
    if (series?.status !== "READY" || points.length < 2) {
      elements.historyChartWrap.hidden = true;
      elements.historyEmpty.hidden = false;
      return;
    }

    elements.historyChartWrap.hidden = false;
    elements.historyEmpty.hidden = true;
    const width = 760;
    const height = 300;
    const margin = { top: 22, right: 24, bottom: 52, left: 52 };
    const chartWidth = width - margin.left - margin.right;
    const chartHeight = height - margin.top - margin.bottom;
    const x = (index) => (
      margin.left + chartWidth * index / Math.max(1, points.length - 1)
    );
    const y = (score) => (
      margin.top + chartHeight * (1 - Math.max(0, Math.min(100, score)) / 100)
    );

    [0, 25, 50, 75, 100].forEach((score) => {
      const lineY = y(score);
      elements.historyChart.appendChild(svgNode("line", {
        class: "history-grid-line",
        x1: margin.left,
        y1: lineY,
        x2: width - margin.right,
        y2: lineY
      }));
      const label = svgNode("text", {
        class: "history-axis-label",
        x: margin.left - 12,
        y: lineY + 4,
        "text-anchor": "end"
      });
      label.textContent = String(score);
      elements.historyChart.appendChild(label);
    });

    const coordinates = points.map((point, index) => (
      `${x(index)},${y(number(point.overall_score, 0))}`
    ));
    elements.historyChart.appendChild(svgNode("polyline", {
      class: "history-trend-line",
      points: coordinates.join(" "),
      fill: "none"
    }));

    points.forEach((point, index) => {
      const timestamp = point.completed_at || point.created_at;
      const circle = svgNode("circle", {
        class: "history-trend-point",
        cx: x(index),
        cy: y(number(point.overall_score, 0)),
        r: 7,
        tabindex: 0,
        role: "img",
        "aria-label": `${historyDate(timestamp)}，${scoreText(point.overall_score)} 分`
      });
      const title = svgNode("title");
      title.textContent = `${historyDate(timestamp)} · ${scoreText(point.overall_score)} 分`;
      circle.appendChild(title);
      ["pointerenter", "click", "focus"].forEach((eventName) => {
        circle.addEventListener(eventName, () => showHistoryPoint(point));
      });
      elements.historyChart.appendChild(circle);

      const showDate = points.length <= 6 || index === 0 || index === points.length - 1;
      if (showDate) {
        const dateLabel = svgNode("text", {
          class: "history-date-label",
          x: x(index),
          y: height - 18,
          "text-anchor": index === 0 ? "start" : index === points.length - 1 ? "end" : "middle"
        });
        dateLabel.textContent = historyDate(timestamp).replace(/^\d{4}\//, "");
        elements.historyChart.appendChild(dateLabel);
      }
    });
    showHistoryPoint(points[points.length - 1]);
  }

  function renderHistoryTrend(data) {
    historyTrendData = data?.status === "READY" ? data : { motions: [] };
    renderHistoryMotion(selectedHistoryMotion);
  }

  function renderProgressHighlights(motions) {
    const container = elements.progressHighlights;
    if (!container) return;

    container.innerHTML = "";

    const comparable = (Array.isArray(motions) ? motions : [])
      .map((motion) => {
        const progress = motion?.progress || {};
        const change = number(progress.change);

        return { motion, progress, change };
      })
      .filter(({ progress, change }) => (
        progress.status === "READY"
        && progress.comparison_status === "COMPARABLE"
        && change !== null
        && progress.direction
        && progress.direction !== "NOT_INTERPRETED"
      ));

    if (!comparable.length) {
      container.hidden = true;
      return;
    }

    const improved = comparable
      .filter(({ change }) => change > 0)
      .sort((a, b) => b.change - a.change);

    const declined = comparable
      .filter(({ change }) => change < 0)
      .sort((a, b) => a.change - b.change);

    const unchanged = comparable
      .filter(({ change }) => change === 0);

    const displayEntries = [];

    improved.forEach((entry, index) => {
      displayEntries.push({
        ...entry,
        label: index === 0 ? "本輪最大進步" : "持續進步",
        tone: "improved"
      });
    });

    declined.forEach((entry, index) => {
      displayEntries.push({
        ...entry,
        label: index === 0 ? "優先改善" : "持續關注",
        tone: "declined"
      });
    });

    unchanged.forEach((entry) => {
      displayEntries.push({
        ...entry,
        label: "維持穩定",
        tone: "unchanged"
      });
    });

    displayEntries.forEach(({ motion, change, label, tone }) => {
      const card = document.createElement("article");
      card.className = `progress-highlight ${tone}`;

      const eyebrow = document.createElement("small");
      eyebrow.textContent = label;

      const row = document.createElement("div");
      row.className = "progress-highlight-row";

      const title = document.createElement("strong");
      title.textContent =
        motion.label
        || motionLabels[motion.motion_type]
        || motion.motion_type
        || "動作";

      const value = document.createElement("span");
      value.textContent =
        `${change > 0 ? "+" : ""}${scoreText(change)}`;

      row.append(title, value);
      card.append(eyebrow, row);
      container.appendChild(card);
    });

    container.hidden = false;
  }

  function renderCoach(aiSummary) {
    const ready = aiSummary?.status === "READY";
    elements.headline.textContent = ready ? aiSummary.headline : "完成步法、發球與高遠球後，即可產生完整摘要。";
    elements.progress.textContent = ready ? aiSummary.progress_summary : "目前資料尚未完整。";
    elements.focus.innerHTML = ""; (Array.isArray(aiSummary?.focus) ? aiSummary.focus : []).forEach((item) => { const tag = document.createElement("span"); tag.className = "tag"; tag.textContent = item; elements.focus.appendChild(tag); });
    elements.recommendations.innerHTML = ""; (Array.isArray(aiSummary?.recommendations) ? aiSummary.recommendations : []).forEach((item) => { const li = document.createElement("li"); li.textContent = item; elements.recommendations.appendChild(li); });
  }

  function renderContext(context) {
  const hand = context?.racket_hand || {};
  const estimated = String(hand.estimated || "").toLowerCase();
  const labels = {
    right: "右手持拍",
    left: "左手持拍"
  };
  const confidence = number(hand.confidence);

  if (!labels[estimated] || confidence === null) {
    elements.handContext.hidden = true;
    return;
  }

  elements.hand.textContent = labels[estimated];
  elements.handConfidence.textContent =
    `Confidence ${Math.round(confidence * 100)}% · 由高遠球推估`;
  elements.handContext.hidden = false;
}

async function load() {
  elements.loading.hidden = false;
  elements.error.hidden = true;
  elements.content.hidden = true;

  try {
    const [data, historyTrend] = await Promise.all([
      requestSummary(),
      requestHistoryTrend().catch(() => null)
    ]);

    renderComparison(data.competency_axes || {});
    renderMotions(data.motions);
    renderProgressHighlights(data.motions);
    renderCoach(data.ai_summary);
    renderContext(data.player_context);
    renderHistoryTrend(historyTrend);

    elements.userReference.textContent = `PLAYER / ${userId}`;
    elements.loading.hidden = true;
    elements.content.hidden = false;

    requestAnimationFrame(drawRadar);
  } catch (error) {
    showError(error);
  }
}

elements.retry.addEventListener("click", load);

document.querySelectorAll("[data-history-motion]").forEach((button) => {
  button.addEventListener("click", () => {
    renderHistoryMotion(button.dataset.historyMotion);
  });
});

window.addEventListener("resize", () => {
  requestAnimationFrame(drawRadar);
});

load();
})();
