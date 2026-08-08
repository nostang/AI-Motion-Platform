document.addEventListener("DOMContentLoaded", async () => {
  "use strict";

  const elements = {
    overallScore: document.getElementById("overallScore"),
    coachStatus: document.getElementById("coachStatus"),
    confidence: document.getElementById("confidenceValue"),
    evaluationStatus: document.getElementById("evaluationStatus"),
    feedbackList: document.getElementById("feedbackList"),
    coachMessage: document.getElementById("coachMessage"),
    radarCanvas: document.getElementById("radarChart"),
    chartEmpty: document.getElementById("chartEmpty"),
    motionChip: document.getElementById("motionChip"),
    motionSubtitle: document.getElementById("motionSubtitle"),
    motionType: document.getElementById("motionTypeValue"),
    hand: document.getElementById("handValue"),
    engine: document.getElementById("engineValue"),
    calibration: document.getElementById("calibrationValue"),
    limitationsDetails: document.getElementById("limitationsDetails"),
    limitationsList: document.getElementById("limitationsList"),
    assessmentLabel: document.getElementById("assessmentLabel"),
    errorBanner: document.getElementById("errorBanner"),
    backButton: document.getElementById("backButton")
  };

  const motionLabels = {
    footwork: { zh: "步法", en: "FOOTWORK" },
    serve: { zh: "正手發球", en: "FOREHAND SERVE" },
    clear: { zh: "高遠球", en: "CLEAR" }
  };

  const metricLabels = {
    preparation_stability: "準備姿勢穩定度",
    swing_completeness: "揮拍完整性",
    body_coordination: "身體協調",
    motion_smoothness: "動作流暢度",
    sideways_preparation: "側身準備",
    weight_transfer: "重心轉移",
    non_racket_arm_balance: "非持拍手平衡",
    swing_smoothness: "揮拍流暢度",
    return_center: "回到中心",
    motion_continuous: "動作連續性"
  };

  let radarChartInstance = null;

  function getAssessmentId() {
    const parameters = new URLSearchParams(window.location.search);
    return parameters.get("id") || parameters.get("assessment_id");
  }

  function valueOrDash(value) {
    return value === null || value === undefined || value === "" ? "--" : String(value);
  }

  function normalized(value) {
    return String(value || "UNKNOWN").trim().toUpperCase();
  }

  function statusType(value) {
    const status = normalized(value);
    if (["PASS", "COMPLETED", "EXCELLENT", "GOOD"].includes(status)) return "success";
    if (["NEEDS_REVIEW", "NOT_EVALUATED", "FAIR", "POOR", "WARNING"].includes(status)) return "warning";
    if (["FAILED", "ERROR", "REJECTED"].includes(status)) return "error";
    return "default";
  }

  function inferMotion(report) {
    const source = [
      report?.motion_type,
      report?.assessment_type,
      report?.serve_type ? "serve" : "",
      report?.meta?.engine_version,
      report?.meta?.config_version,
      report?.video_id
    ].filter(Boolean).join(" ").toLowerCase();

    if (source.includes("serve")) return "serve";
    if (source.includes("clear")) return "clear";
    if (source.includes("footwork")) return "footwork";
    return "unknown";
  }

  function formatMetric(metric) {
    if (!metric) return "教練回饋";
    return metricLabels[metric] || String(metric).replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function createFeedbackItem(title, description, status = "default") {
    const item = document.createElement("li");
    item.className = "feedback-item";
    item.dataset.status = status;
    const titleElement = document.createElement("strong");
    const descriptionElement = document.createElement("span");
    titleElement.textContent = title;
    descriptionElement.textContent = description;
    item.append(titleElement, descriptionElement);
    return item;
  }

  function renderHeader(report, motion) {
    const label = motionLabels[motion] || { zh: "羽球動作", en: "MOTION" };
    elements.motionChip.textContent = label.en;
    elements.motionSubtitle.textContent = `${label.zh}動作品質評估與教練建議`;
    elements.motionType.textContent = label.zh;
  }

  function renderSummary(report) {
    const score = report?.summary?.overall_score;
    const coachStatus = normalized(report?.summary?.coach_status);
    const evaluation = normalized(report?.summary?.evaluation_status);
    const confidence = report?.summary?.system_confidence;
    elements.overallScore.textContent = valueOrDash(score);
    elements.coachStatus.textContent = coachStatus.replaceAll("_", " ");
    elements.coachStatus.dataset.status = statusType(coachStatus);
    elements.evaluationStatus.textContent = evaluation === "UNKNOWN" ? "尚無評估狀態" : evaluation.replaceAll("_", " ");
    elements.confidence.textContent = Number.isFinite(Number(confidence)) ? `${Math.round(Number(confidence) * 100)}%` : "--";
  }

  function renderFeedback(report, motion) {
    elements.feedbackList.innerHTML = "";
    const coachMessage = report?.coach?.overall_message;
    if (coachMessage) {
      elements.coachMessage.textContent = coachMessage;
      elements.coachMessage.hidden = false;
    }

    const nestedFeedback = Array.isArray(report?.coach?.feedback) ? report.coach.feedback : [];
    const legacyFeedback = Array.isArray(report?.feedback) ? report.feedback : [];
    const feedback = nestedFeedback.length ? nestedFeedback : legacyFeedback;

    feedback.forEach((entry) => {
      if (typeof entry === "string") {
        elements.feedbackList.appendChild(createFeedbackItem("教練回饋", entry));
        return;
      }
      if (!entry || typeof entry !== "object") return;
      const title = entry.title || entry.name || formatMetric(entry.metric);
      const description = entry.message || entry.description || entry.explanation || "目前沒有補充說明。";
      const status = statusType(entry.level || entry.status || entry.result);
      elements.feedbackList.appendChild(createFeedbackItem(title, description, status));
    });

    if (motion === "footwork") {
      const observation = report?.observation || {};
      if (observation.return_center === true) elements.feedbackList.appendChild(createFeedbackItem("回到中心", "已偵測到動作後回到中心位置。", "success"));
      if (observation.motion_continuous === true) elements.feedbackList.appendChild(createFeedbackItem("動作連續性", "步法動作已連續完成。", "success"));
      const missing = Array.isArray(observation.missing_directions) ? observation.missing_directions : [];
      if (missing.length) elements.feedbackList.appendChild(createFeedbackItem("方向覆蓋待確認", `尚未完整覆蓋：${missing.join("、")}`, "warning"));
    }

    if (!elements.feedbackList.children.length) {
      elements.feedbackList.appendChild(createFeedbackItem("目前沒有教練回饋", "這份報告尚未提供額外的 Coach Feedback。"));
    }
  }

  function renderRadar(report) {
    const labels = Array.isArray(report?.radar_chart?.labels) ? report.radar_chart.labels : [];
    const rawScores = Array.isArray(report?.radar_chart?.scores) ? report.radar_chart.scores : [];
    const maximumScore = Number(report?.radar_chart?.max_score) || 25;
    if (!labels.length || !rawScores.length || typeof window.Chart === "undefined") {
      elements.radarCanvas.hidden = true;
      elements.chartEmpty.hidden = false;
      return;
    }

    const scores = rawScores.map((score) => score === null || score === undefined ? null : Number(score));
    if (radarChartInstance) radarChartInstance.destroy();
    radarChartInstance = new Chart(elements.radarCanvas, {
      type: "radar",
      data: {
        labels,
        datasets: [{
          label: "AI Motion Assessment",
          data: scores,
          spanGaps: false,
          borderWidth: 3,
          borderColor: "#075d3b",
          backgroundColor: "rgba(216,255,82,.24)",
          pointBackgroundColor: "#d8ff52",
          pointBorderColor: "#075d3b",
          pointRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        layout: {
          padding: 32
        },
        scales: { r: {
          beginAtZero: true,
          min: 0,
          max: maximumScore,
          ticks: { display: false, stepSize: Math.max(1, maximumScore / 5) },
          grid: { color: "rgba(7,93,59,.22)" },
          angleLines: { color: "rgba(7,93,59,.22)" },
          pointLabels: { color: "#0b2419", font: { size: 12, weight: "700" } }
        } },
        plugins: {
          legend: { labels: { color: "#0b2419" } },
          tooltip: { callbacks: { label(context) {
            const value = rawScores[context.dataIndex];
            return `${labels[context.dataIndex]}: ${value ?? "Not evaluated"}${value === null || value === undefined ? "" : `/${maximumScore}`}`;
          } } }
        }
      }
    });
  }

  function renderEvidence(report, motion) {
    const hand = report?.features?.dominant_hand || report?.features?.racket_hand || report?.dominant_hand || report?.racket_hand;
    const estimatedHand = typeof hand === "string" ? hand : hand?.estimated;
    const handConfidence = typeof hand === "object" ? hand?.confidence : null;
    elements.hand.textContent = estimatedHand ? `${estimatedHand === "right" ? "右手" : estimatedHand === "left" ? "左手" : estimatedHand}${Number.isFinite(Number(handConfidence)) ? ` · ${Math.round(Number(handConfidence) * 100)}%` : ""}` : "--";
    elements.engine.textContent = valueOrDash(report?.meta?.engine_version);
    elements.calibration.textContent = valueOrDash(report?.meta?.calibration_status);
    elements.motionType.textContent = (motionLabels[motion] || { zh: "羽球動作" }).zh;

    const limitations = Array.isArray(report?.limitations) ? report.limitations : Array.isArray(report?.features?.limitations) ? report.features.limitations : [];
    if (limitations.length) {
      elements.limitationsDetails.hidden = false;
      elements.limitationsList.innerHTML = "";
      limitations.forEach((text) => {
        const item = document.createElement("li");
        item.textContent = text;
        elements.limitationsList.appendChild(item);
      });
    }
  }

  function renderReport(report) {
    const motion = inferMotion(report);
    renderHeader(report, motion);
    renderSummary(report);
    renderFeedback(report, motion);
    renderRadar(report);
    renderEvidence(report, motion);
  }

  function showError(message) {
    elements.errorBanner.textContent = `報告載入失敗：${message}`;
    elements.errorBanner.hidden = false;
    elements.motionSubtitle.textContent = "無法取得這次測驗的報告資料";
  }

  async function loadReport() {
    const assessmentId = getAssessmentId();
    elements.assessmentLabel.textContent = assessmentId ? `ASSESSMENT / ${assessmentId}` : "";
    if (!assessmentId) {
      showError("網址缺少 Assessment ID");
      return;
    }
    try {
      const response = await window.motionAPI.getReport(assessmentId);
      if (!response?.success) throw new Error(response?.error?.message || "Unable to retrieve the report.");
      sessionStorage.setItem("aiMotionReport", JSON.stringify(response.data));
      renderReport(response.data);
    } catch (error) {
      console.error(error);
      showError(error.message || "發生未知錯誤");
    }
  }

  elements.backButton.addEventListener("click", () => { window.location.href = "index.html"; });
  await loadReport();
});
