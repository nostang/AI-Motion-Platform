document.addEventListener("DOMContentLoaded", async () => {
  "use strict";

  const elements = {
    overallScore: document.getElementById("overallScore"),
    coachStatus: document.getElementById("coachStatus"),
    confidence: document.getElementById("confidenceValue"),
    evaluationStatus: document.getElementById("evaluationStatus"),
    feedbackList: document.getElementById("feedbackList"),
    coachMessage: document.getElementById("coachMessage"),
    dimensionList: document.getElementById("dimensionList"),
    dimensionEmpty: document.getElementById("dimensionEmpty"),
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
    non_racket_arm: "非持拍手平衡",
    swing_smoothness: "揮拍流暢度",
    movement_completion: "動作完成度",
    recovery_speed: "回位速度",
    direction_coverage: "方向覆蓋",
    motion_quality: "動作品質",
    body_stability: "身體穩定",
    return_center: "回到中心",
    motion_continuous: "動作連續性"
  };

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
  const confidence =
    report?.summary?.system_confidence ??
    report?.observation?.system_confidence;

  const coachStatusLabels = {
    PASS: "通過",
    NEEDS_REVIEW: "建議改善",
    FAIL: "未通過",
    NOT_EVALUATED: "尚未評估",
    UNKNOWN: "尚未評估",
  };

  const coachStatusLabel =
    coachStatusLabels[coachStatus] ||
    coachStatus.replaceAll("_", " ");

  const evaluationLabel =
    evaluation === "EVALUATED"
      ? "已完成評估"
      : evaluation === "NOT_EVALUATED" || evaluation === "UNKNOWN"
        ? "尚無評估狀態"
        : evaluation.replaceAll("_", " ");

  elements.overallScore.textContent = valueOrDash(score);
  elements.coachStatus.textContent = coachStatusLabel;
  elements.coachStatus.dataset.status = statusType(coachStatus);
  elements.evaluationStatus.textContent = evaluationLabel;
  elements.confidence.textContent = Number.isFinite(Number(confidence))
    ? `${Math.round(Number(confidence) * 100)}%`
    : "--";
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
    const strengths = Array.isArray(report?.highlights?.strengths) ? report.highlights.strengths : [];
    const priorities = Array.isArray(report?.highlights?.improvement_priorities) ? report.highlights.improvement_priorities : [];

    if (strengths.length) {
      elements.feedbackList.appendChild(createFeedbackItem(
        "本次優勢",
        strengths.map(formatMetric).join("、"),
        "success"
      ));
    }

    if (priorities.length) {
      elements.feedbackList.appendChild(createFeedbackItem(
        "優先改善",
        priorities.map(formatMetric).join("、"),
        "warning"
      ));
    }

    const shouldShowDetailedFeedback = !strengths.length && !priorities.length;
    if (shouldShowDetailedFeedback) feedback.forEach((entry) => {
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

  function normalizedMetricKey(value) {
    return String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  function feedbackForDimension(feedback, label, index, dimensionCount) {
    const labelKey = normalizedMetricKey(label);
    const exact = feedback.find((entry) => {
      if (!entry || typeof entry !== "object") return false;
      return [entry.metric, entry.title, entry.name]
        .map(normalizedMetricKey)
        .some((key) => key && (key === labelKey || key.includes(labelKey) || labelKey.includes(key)));
    });
    if (exact) return exact;
    return feedback.length === dimensionCount ? feedback[index] : null;
  }

  function reportEntryForDimension(report, label) {
  const labelKey = normalizedMetricKey(label);
  const sources = [
    report?.skill_score,
    report?.assessment_metrics,
  ];

  for (const source of sources) {
    if (!source || typeof source !== "object") continue;

    for (const [key, entry] of Object.entries(source)) {
      if (
        normalizedMetricKey(key) === labelKey &&
        entry &&
        typeof entry === "object"
      ) {
        return entry;
      }
    }
  }

  return null;
}

function renderDimensions(report) {
    const labels = Array.isArray(report?.radar_chart?.labels) ? report.radar_chart.labels : [];
    const rawScores = Array.isArray(report?.radar_chart?.scores) ? report.radar_chart.scores : [];
    const maximumScore = Number(report?.radar_chart?.max_score) || 25;
    const nestedFeedback = Array.isArray(report?.coach?.feedback) ? report.coach.feedback : [];
    const legacyFeedback = Array.isArray(report?.feedback) ? report.feedback : [];
    const feedback = nestedFeedback.length ? nestedFeedback : legacyFeedback;

    elements.dimensionList.innerHTML = "";
    if (!labels.length || !rawScores.length) {
      elements.dimensionEmpty.hidden = false;
      return;
    }
    elements.dimensionEmpty.hidden = true;

    labels.forEach((label, index) => {
      const score = rawScores[index];
      const numericScore = Number(score);
      const evaluated = score !== null && score !== undefined && Number.isFinite(numericScore);
      const coachEntry = feedbackForDimension(feedback, label, index, labels.length);
      const reportEntry = reportEntryForDimension(report, label);
      const level = normalized(
        reportEntry?.level ||
        coachEntry?.level ||
        coachEntry?.status ||
        coachEntry?.result ||
        "NOT PROVIDED"
      );
      const item = document.createElement("div");
      item.className = "dimension-item";
      item.dataset.level = level;
      const percentage = evaluated ? Math.max(0, Math.min(100, (numericScore / maximumScore) * 100)) : 0;
      item.innerHTML = `
        <div class="dimension-topline">
          <strong class="dimension-name"></strong>
          <span class="dimension-score">${evaluated ? `${numericScore} / ${maximumScore}` : "NOT EVALUATED"}</span>
          <span class="level-badge" data-level="${level}">${level.replaceAll("_", " ")}</span>
        </div>
        <div class="dimension-track" role="progressbar" aria-valuemin="0" aria-valuemax="${maximumScore}" aria-valuenow="${evaluated ? numericScore : 0}">
          <div class="dimension-fill" style="width:${percentage}%"></div>
        </div>
      `;
      item.querySelector(".dimension-name").textContent = formatMetric(String(label).toLowerCase().replaceAll(" ", "_"));
      const message = coachEntry?.message || coachEntry?.description || coachEntry?.explanation;
      if (message) {
        const note = document.createElement("p");
        note.className = "dimension-note";
        note.textContent = message;
        item.appendChild(note);
      }
      elements.dimensionList.appendChild(item);
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
    renderDimensions(report);
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

  const returnParameters = new URLSearchParams(
    window.location.search
  );
  const returnSource = returnParameters.get("from");
  const returnUserId =
    Number(returnParameters.get("user_id")) || 1;

  elements.backButton.textContent = "再測一次 ↻";

  elements.backButton.addEventListener("click", () => {
    window.location.href = "index.html";
  });
  await loadReport();
});
