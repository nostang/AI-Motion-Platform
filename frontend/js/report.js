document.addEventListener("DOMContentLoaded", async () => {
  "use strict";

  const elements = {
    overallScore: document.getElementById("overallScore"),
    coachStatus: document.getElementById("coachStatus"),
    confidence: document.getElementById("confidenceValue"),
    evaluationStatus: document.getElementById("evaluationStatus"),
    feedbackList: document.getElementById("feedbackList"),
    coachMessage: document.getElementById("coachMessage"),
    coachV2: document.getElementById("coachV2"),
    coachV2Strengths: document.getElementById("coachV2Strengths"),
    coachV2Priorities: document.getElementById("coachV2Priorities"),
    coachV2Training: document.getElementById("coachV2Training"),
    coachV2NextFocus: document.getElementById("coachV2NextFocus"),
    coachV2RecentTrend: document.getElementById("coachV2RecentTrend"),
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
    backButton: document.getElementById("backButton"),
    keyMotionSection: document.getElementById("keyMotionSection"),
    keyMotionPlayer: document.getElementById("keyMotionPlayer"),
    keyMotionStage: document.getElementById("keyMotionStage"),
    keyMotionIndicators: document.getElementById("keyMotionIndicators"),
    keyMotionPlayback: document.getElementById("keyMotionPlayback"),
    keyMotionPlaybackIcon: document.getElementById("keyMotionPlaybackIcon"),
    keyMotionPlaybackLabel: document.getElementById("keyMotionPlaybackLabel"),
    keyMotionCounter: document.getElementById("keyMotionCounter"),
    keyMotionSkeletonToggle: document.getElementById("keyMotionSkeletonToggle"),
    keyMotionSkeletonState: document.getElementById("keyMotionSkeletonState"),
    footworkReachSection: document.getElementById("footworkReachSection"),
    footworkReachGrid: document.getElementById("footworkReachGrid"),
    footworkReachSkeletonToggle: document.getElementById("footworkReachSkeletonToggle"),
    footworkReachSkeletonState: document.getElementById("footworkReachSkeletonState")
  };

  const poseLandmarkNames = [
    "nose",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle"
  ];

  const poseConnections = [
    ["nose", "left_shoulder"],
    ["nose", "right_shoulder"],
    ["left_shoulder", "right_shoulder"],
    ["left_shoulder", "left_elbow"],
    ["left_elbow", "left_wrist"],
    ["right_shoulder", "right_elbow"],
    ["right_elbow", "right_wrist"],
    ["left_shoulder", "left_hip"],
    ["right_shoulder", "right_hip"],
    ["left_hip", "right_hip"],
    ["left_hip", "left_knee"],
    ["left_knee", "left_ankle"],
    ["right_hip", "right_knee"],
    ["right_knee", "right_ankle"]
  ];

  const svgNamespace = "http://www.w3.org/2000/svg";
  const poseViewBox = { width: 300, height: 340, padding: 24 };
  const sourceAspectRatio = 16 / 9;
  const motionSequenceFrameCount = 6;
  const motionSequenceIntervalMs = 425;
  const posePalette = {
    deepGreen: "#043f2a",
    courtGreen: "#075d3b",
    lime: "#d8ff52",
    pale: "#f7fff9"
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

  function svgElement(name, attributes = {}) {
    const element = document.createElementNS(svgNamespace, name);
    Object.entries(attributes).forEach(([key, value]) => {
      element.setAttribute(key, String(value));
    });
    return element;
  }

  function cleanPoseLandmarks(value) {
    if (!value || typeof value !== "object") return {};
    const landmarks = {};
    poseLandmarkNames.forEach((name) => {
      const point = value[name];
      if (!point || typeof point !== "object") return;
      if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) return;
      if (point.x < 0 || point.x > 1 || point.y < 0 || point.y > 1) return;
      landmarks[name] = { x: point.x, y: point.y };
    });
    return landmarks;
  }

  function poseOnlyLandmarks(landmarks) {
    return Object.fromEntries(
      Object.entries(landmarks).map(([name, point]) => [
        name,
        { x: point.x * sourceAspectRatio, y: point.y }
      ])
    );
  }

  function poseBounds(landmarks) {
    const points = Object.values(landmarks);
    if (!points.length) return null;
    const xs = points.map((point) => point.x);
    const ys = points.map((point) => point.y);
    return {
      minX: Math.min(...xs),
      maxX: Math.max(...xs),
      minY: Math.min(...ys),
      maxY: Math.max(...ys)
    };
  }

  function sharedPoseScale(snapshotLandmarks) {
    const bounds = snapshotLandmarks.map(poseBounds).filter(Boolean);
    const maximumWidth = Math.max(...bounds.map((box) => box.maxX - box.minX), 0.12);
    const maximumHeight = Math.max(...bounds.map((box) => box.maxY - box.minY), 0.24);
    const drawableWidth = poseViewBox.width - poseViewBox.padding * 2;
    const drawableHeight = poseViewBox.height - poseViewBox.padding * 2;
    return Math.min(drawableWidth / maximumWidth, drawableHeight / maximumHeight);
  }

  function canvasPoint(point, bounds, scale) {
    const centerX = (bounds.minX + bounds.maxX) / 2;
    const centerY = (bounds.minY + bounds.maxY) / 2;
    return {
      x: poseViewBox.width / 2 + (point.x - centerX) * scale,
      y: poseViewBox.height / 2 + (point.y - centerY) * scale
    };
  }

  function renderPoseSvg(landmarks, racketSide, scale, stageLabel, keyframe = null) {
    const usesImageCoordinates = Boolean(keyframe);
    const viewBoxWidth = usesImageCoordinates ? keyframe.width : poseViewBox.width;
    const viewBoxHeight = usesImageCoordinates ? keyframe.height : poseViewBox.height;
    const svg = svgElement("svg", {
      class: "key-motion-pose-overlay",
      viewBox: `0 0 ${viewBoxWidth} ${viewBoxHeight}`,
      role: "img",
      "aria-label": `${stageLabel}的代表姿勢`,
      "data-coordinate-mode": usesImageCoordinates ? "image" : "centered"
    });
    const renderLandmarks = usesImageCoordinates
      ? landmarks
      : poseOnlyLandmarks(landmarks);
    const bounds = poseBounds(renderLandmarks);
    if (!bounds) return svg;

    const points = Object.fromEntries(Object.entries(renderLandmarks).map(
      ([name, point]) => [
        name,
        usesImageCoordinates
          ? { x: point.x * viewBoxWidth, y: point.y * viewBoxHeight }
          : canvasPoint(point, bounds, scale)
      ]
    ));
    const strokeScale = usesImageCoordinates
      ? Math.max(1, Math.min(viewBoxWidth / 300, viewBoxHeight / 340))
      : 1;
    const normalOpacity = usesImageCoordinates ? 0.58 : 1;
    const racketOpacity = usesImageCoordinates ? 0.88 : 1;

    const torsoNames = [
      "left_shoulder",
      "right_shoulder",
      "right_hip",
      "left_hip"
    ];
    if (torsoNames.every((name) => points[name])) {
      svg.appendChild(svgElement("polygon", {
        class: "pose-torso",
        points: torsoNames.map((name) => `${points[name].x},${points[name].y}`).join(" "),
        fill: posePalette.courtGreen,
        "fill-opacity": usesImageCoordinates ? 0.06 : 0.11,
        stroke: posePalette.courtGreen,
        "stroke-opacity": usesImageCoordinates ? 0.28 : 0.3,
        "stroke-width": 2 * strokeScale,
        "stroke-linejoin": "round",
        opacity: 1
      }));
    }

    poseConnections.forEach(([from, to]) => {
      if (!points[from] || !points[to]) return;
      const isRacketArm = (
        from.startsWith(`${racketSide}_`) &&
        to.startsWith(`${racketSide}_`) &&
        [from, to].some((name) => name.endsWith("elbow") || name.endsWith("wrist"))
      );
      if (isRacketArm) {
        svg.appendChild(svgElement("line", {
          class: "pose-limb-racket-outline",
          x1: points[from].x,
          y1: points[from].y,
          x2: points[to].x,
          y2: points[to].y,
          fill: "none",
          stroke: posePalette.deepGreen,
          "stroke-width": 14 * strokeScale,
          "stroke-linecap": "round",
          "stroke-linejoin": "round",
          opacity: usesImageCoordinates ? 0.72 : 1,
          "aria-hidden": "true"
        }));
      }
      const line = svgElement("line", {
        class: isRacketArm ? "pose-limb pose-limb-racket" : "pose-limb",
        x1: points[from].x,
        y1: points[from].y,
        x2: points[to].x,
        y2: points[to].y,
        fill: "none",
        stroke: isRacketArm ? posePalette.lime : posePalette.deepGreen,
        "stroke-width": (isRacketArm ? 9 : 6) * strokeScale,
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
        opacity: isRacketArm ? racketOpacity : normalOpacity,
        "data-from": from,
        "data-to": to
      });
      svg.appendChild(line);
    });

    const racketWrist = points[`${racketSide}_wrist`];
    if (racketWrist) {
      svg.appendChild(svgElement("circle", {
        class: "pose-wrist-focus",
        cx: racketWrist.x,
        cy: racketWrist.y,
        r: 12 * strokeScale,
        fill: "none",
        stroke: posePalette.lime,
        "stroke-width": 3 * strokeScale,
        opacity: usesImageCoordinates ? 0.82 : 0.9,
        "aria-hidden": "true"
      }));
    }

    poseLandmarkNames.forEach((name) => {
      if (!points[name]) return;
      const isRacketJoint = name.startsWith(`${racketSide}_`) && (
        name.endsWith("shoulder") ||
        name.endsWith("elbow") ||
        name.endsWith("wrist")
      );
      const isNose = name === "nose";
      svg.appendChild(svgElement("circle", {
        class: isRacketJoint ? "pose-joint pose-joint-racket" : "pose-joint",
        cx: points[name].x,
        cy: points[name].y,
        r: (isNose ? 7 : isRacketJoint ? 6 : 4) * strokeScale,
        fill: isRacketJoint
          ? posePalette.lime
          : isNose
            ? posePalette.pale
            : posePalette.courtGreen,
        stroke: posePalette.deepGreen,
        "stroke-width": (isRacketJoint ? 3 : isNose ? 4 : 2) * strokeScale,
        opacity: isRacketJoint ? racketOpacity : normalOpacity,
        "data-landmark": name,
        "data-source-x": landmarks[name].x,
        "data-source-y": landmarks[name].y
      }));
    });
    return svg;
  }

  function readyKeyframe(value) {
    if (!value || value.status !== "READY") return null;
    if (!Number.isInteger(value.width) || value.width <= 0) return null;
    if (!Number.isInteger(value.height) || value.height <= 0) return null;
    if (typeof value.url !== "string" || !value.url.startsWith("/api/v1/")) return null;
    return { url: value.url, width: value.width, height: value.height };
  }

  let motionSequencePlayback = null;

  function motionSequenceFrame(frame, racketSide, scale) {
    const container = document.createElement("article");
    container.className = "motion-sequence-frame";
    container.dataset.sequenceIndex = String(frame.index);
    container.hidden = true;
    const visual = document.createElement("div");
    visual.className = "key-motion-visual";
    const background = document.createElement("div");
    background.className = "key-motion-background";
    background.setAttribute("aria-hidden", "true");
    visual.appendChild(background);

    const landmarks = cleanPoseLandmarks(frame.landmarks);
    const keyframe = readyKeyframe(frame.image);
    const renderableConnectionCount = poseConnections.filter(
      ([from, to]) => landmarks[from] && landmarks[to]
    ).length;
    const frameLabel = `動作序列第 ${frame.index} 張`;
    if (renderableConnectionCount) {
      if (keyframe) {
        visual.classList.add("has-keyframe");
        visual.style.aspectRatio = `${keyframe.width} / ${keyframe.height}`;
        const image = document.createElement("img");
        image.className = "key-motion-keyframe";
        image.src = keyframe.url;
        image.loading = "eager";
        image.decoding = "async";
        image.alt = "";
        image.setAttribute("aria-hidden", "true");
        image.addEventListener("error", () => {
          image.remove();
          visual.classList.remove("has-keyframe");
          visual.style.removeProperty("aspect-ratio");
          const overlay = visual.querySelector(".key-motion-pose-overlay");
          overlay?.replaceWith(
            renderPoseSvg(landmarks, racketSide, scale, frameLabel)
          );
        }, { once: true });
        visual.append(
          image,
          renderPoseSvg(landmarks, racketSide, scale, frameLabel, keyframe)
        );
      } else {
        visual.appendChild(
          renderPoseSvg(landmarks, racketSide, scale, frameLabel)
        );
      }
    } else {
      const unavailable = document.createElement("p");
      unavailable.className = "key-motion-unavailable";
      unavailable.textContent = "本張動作畫面暫無法顯示";
      visual.appendChild(unavailable);
    }
    container.appendChild(visual);
    return container;
  }

  function hideKeyMotion() {
    motionSequencePlayback?.destroy();
    motionSequencePlayback = null;
    elements.keyMotionStage.replaceChildren();
    elements.keyMotionIndicators.replaceChildren();
    elements.keyMotionSection.hidden = true;
  }

  function hideFootworkReachGrid() {
    elements.footworkReachGrid.replaceChildren();
    elements.footworkReachSection.hidden = true;
  }

  function setFootworkSkeletonVisibility(visible) {
    elements.footworkReachGrid.dataset.skeletonVisible = visible ? "true" : "false";
    elements.footworkReachSkeletonToggle.setAttribute("aria-checked", String(visible));
    elements.footworkReachSkeletonState.textContent = visible ? "ON" : "OFF";
  }

  function footworkReachCell(cell) {
    const container = document.createElement("article");
    container.className = "footwork-reach-cell";
    container.dataset.gridKey = cell.key;
    container.style.gridRow = String(cell.row);
    container.style.gridColumn = String(cell.column);
    const heading = document.createElement("strong");
    heading.className = "footwork-reach-label";
    heading.textContent = cell.label;
    container.appendChild(heading);

    if (cell.status !== "READY") {
      container.classList.add("is-incomplete");
      const unavailable = document.createElement("p");
      unavailable.className = "footwork-reach-empty";
      unavailable.textContent = "未完成";
      container.appendChild(unavailable);
      return container;
    }

    const landmarks = cleanPoseLandmarks(cell.landmarks);
    const keyframe = readyKeyframe(cell.image);
    const visual = document.createElement("div");
    visual.className = "key-motion-visual footwork-reach-visual";
    if (!keyframe || Object.keys(landmarks).length !== poseLandmarkNames.length) {
      const unavailable = document.createElement("p");
      unavailable.className = "key-motion-unavailable";
      unavailable.textContent = "畫面暫不可用";
      visual.appendChild(unavailable);
      container.appendChild(visual);
      return container;
    }

    visual.classList.add("has-keyframe");
    visual.style.aspectRatio = `${keyframe.width} / ${keyframe.height}`;
    const image = document.createElement("img");
    image.className = "key-motion-keyframe";
    image.src = keyframe.url;
    image.loading = "eager";
    image.decoding = "async";
    image.alt = `${cell.label}方向代表畫面`;
    const overlay = renderPoseSvg(
      landmarks,
      "none",
      null,
      `${cell.label}方向姿勢`,
      keyframe
    );
    image.addEventListener("error", () => {
      visual.replaceChildren();
      visual.classList.remove("has-keyframe");
      const unavailable = document.createElement("p");
      unavailable.className = "key-motion-unavailable";
      unavailable.textContent = "畫面暫不可用";
      visual.appendChild(unavailable);
    }, { once: true });
    visual.append(image, overlay);
    container.appendChild(visual);
    return container;
  }

  function renderFootworkReachGrid(data, motion) {
    hideFootworkReachGrid();
    const grid = data?.reach_grid;
    if (
      motion !== "footwork" ||
      !["READY", "PARTIAL"].includes(grid?.status) ||
      grid?.motion_type !== "footwork" ||
      !Array.isArray(grid?.cells) ||
      grid.cells.length !== 9
    ) return;
    const cells = [...grid.cells].sort(
      (left, right) => (left.row - right.row) || (left.column - right.column)
    );
    const validLayout = cells.every((cell, index) => (
      cell?.row === Math.floor(index / 3) + 1 &&
      cell?.column === (index % 3) + 1 &&
      typeof cell?.label === "string"
    ));
    if (!validLayout) return;
    cells.forEach((cell) => {
      elements.footworkReachGrid.appendChild(footworkReachCell(cell));
    });
    elements.footworkReachSection.hidden = false;
  }

  function setSkeletonVisibility(visible) {
    elements.keyMotionPlayer.dataset.skeletonVisible = visible ? "true" : "false";
    elements.keyMotionSkeletonToggle.setAttribute("aria-checked", String(visible));
    elements.keyMotionSkeletonState.textContent = visible ? "ON" : "OFF";
  }

  function setPlaybackState(playing) {
    elements.keyMotionPlayback.dataset.playing = String(playing);
    elements.keyMotionPlayback.setAttribute(
      "aria-label",
      playing ? "暫停動作序列" : "播放動作序列"
    );
    elements.keyMotionPlaybackIcon.textContent = playing ? "❚❚" : "▶";
    elements.keyMotionPlaybackLabel.textContent = playing ? "暫停" : "播放";
  }

  function showSequenceFrame(index) {
    [...elements.keyMotionStage.children].forEach((frame, frameIndex) => {
      frame.hidden = frameIndex !== index;
    });
    [...elements.keyMotionIndicators.children].forEach((indicator, frameIndex) => {
      indicator.setAttribute("aria-current", frameIndex === index ? "true" : "false");
    });
    elements.keyMotionCounter.textContent = `${String(index + 1).padStart(2, "0")} / 06`;
  }

  function renderKeyMotion(data, motion) {
    hideKeyMotion();
    const sequence = data?.sequence;
    if (
      !["clear", "serve"].includes(motion) ||
      sequence?.status !== "READY" ||
      sequence?.motion_type !== motion ||
      !["left", "right"].includes(sequence?.racket_side) ||
      !Array.isArray(sequence?.frames) ||
      sequence.frames.length !== motionSequenceFrameCount ||
      typeof window.MotionSequencePlayer !== "function"
    ) return;

    const frames = [...sequence.frames].sort((left, right) => left.index - right.index);
    if (!frames.every((frame, index) => frame?.index === index + 1)) return;
    const cleaned = frames.map((frame) => (
      poseOnlyLandmarks(cleanPoseLandmarks(frame.landmarks))
    ));
    const scale = sharedPoseScale(cleaned);
    frames.forEach((frame) => {
      elements.keyMotionStage.appendChild(
        motionSequenceFrame(frame, sequence.racket_side, scale)
      );
      const indicator = document.createElement("button");
      indicator.className = "motion-sequence-indicator";
      indicator.type = "button";
      indicator.setAttribute("aria-label", `顯示動作序列第 ${frame.index} 張`);
      indicator.addEventListener("click", () => {
        motionSequencePlayback?.select(frame.index - 1);
      });
      elements.keyMotionIndicators.appendChild(indicator);
    });
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
    motionSequencePlayback = new window.MotionSequencePlayer({
      frameCount: motionSequenceFrameCount,
      intervalMs: motionSequenceIntervalMs,
      reducedMotion,
      onFrame: showSequenceFrame,
      onStateChange: setPlaybackState
    });
    showSequenceFrame(0);
    setPlaybackState(false);
    elements.keyMotionSection.hidden = false;
    motionSequencePlayback.start();
  }

  function toggleSkeletonVisibility() {
    const visible = elements.keyMotionSkeletonToggle.getAttribute("aria-checked") !== "true";
    setSkeletonVisibility(visible);
  }

  elements.keyMotionSkeletonToggle.addEventListener("click", toggleSkeletonVisibility);
  elements.keyMotionPlayback.addEventListener("click", () => {
    if (!motionSequencePlayback) return;
    if (motionSequencePlayback.isPlaying) {
      motionSequencePlayback.pause();
    } else {
      motionSequencePlayback.play();
    }
  });
  elements.footworkReachSkeletonToggle.addEventListener("click", () => {
    const visible = (
      elements.footworkReachSkeletonToggle.getAttribute("aria-checked") !== "true"
    );
    setFootworkSkeletonVisibility(visible);
  });
  setSkeletonVisibility(true);
  setFootworkSkeletonVisibility(true);

  async function loadKeyMotion(assessmentId, motion) {
    hideKeyMotion();
    hideFootworkReachGrid();
    if (!["clear", "serve", "footwork"].includes(motion)) return;
    try {
      const response = await window.motionAPI.getVisualization(assessmentId);
      if (!response?.success) return;
      if (motion === "footwork") {
        renderFootworkReachGrid(response.data, motion);
      } else {
        renderKeyMotion(response.data, motion);
      }
    } catch (error) {
      console.debug("Key Motion visualization unavailable", error);
      hideKeyMotion();
      hideFootworkReachGrid();
    }
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

  function createCoachV2Item(title, description, meta = "") {
    const item = document.createElement("li");
    const heading = document.createElement("strong");
    const copy = document.createElement("span");
    heading.textContent = title;
    copy.textContent = description;
    item.append(heading, copy);
    if (meta) {
      const detail = document.createElement("small");
      detail.textContent = meta;
      item.appendChild(detail);
    }
    return item;
  }

  function renderCoachV2(data) {
    if (!data || data.status !== "READY") return false;

    const strengths = Array.isArray(data.strengths) ? data.strengths : [];
    const priorities = Array.isArray(data.priorities) ? data.priorities : [];
    const training = Array.isArray(data.training_plan) ? data.training_plan : [];
    elements.coachV2Strengths.replaceChildren();
    elements.coachV2Priorities.replaceChildren();
    elements.coachV2Training.replaceChildren();

    strengths.forEach((item) => {
      elements.coachV2Strengths.appendChild(createCoachV2Item(
        item.label || formatMetric(item.metric),
        item.message || "本次表現相對穩定。",
        `${valueOrDash(item.score)} / ${valueOrDash(item.max_score)}`
      ));
    });
    if (!strengths.length) {
      elements.coachV2Strengths.appendChild(createCoachV2Item(
        "資料不足",
        "目前沒有足夠 evidence 選出本次亮點。"
      ));
    }

    priorities.forEach((item) => {
      elements.coachV2Priorities.appendChild(createCoachV2Item(
        item.label || formatMetric(item.metric),
        item.message || "建議列為近期練習重點。",
        `${valueOrDash(item.score)} / ${valueOrDash(item.max_score)}`
      ));
    });
    if (!priorities.length) {
      elements.coachV2Priorities.appendChild(createCoachV2Item(
        "暫無明確弱項",
        "本次既有評估沒有選出需要優先改善的項目。"
      ));
    }

    training.forEach((item) => {
      const sets = Number(item.sets);
      const repetitions = Number(item.repetitions_per_set);
      const prescription = Number.isFinite(sets) && Number.isFinite(repetitions)
        ? `建議 ${sets} 組 × 每組 ${repetitions} 次`
        : "建議短期練習";
      elements.coachV2Training.appendChild(createCoachV2Item(
        item.title || "建議練習",
        item.instruction || "依目前主要弱項進行練習。",
        `${prescription} · ${item.focus_label || formatMetric(item.focus_metric)}`
      ));
    });
    if (!training.length) {
      elements.coachV2Training.appendChild(createCoachV2Item(
        "維持目前練習",
        "本次沒有足夠 weak-point evidence 建立額外菜單。"
      ));
    }

    elements.coachV2NextFocus.textContent = data.next_focus?.message
      || "目前沒有足夠 evidence 指定下次觀察重點。";
    elements.coachV2RecentTrend.textContent = data.recent_trend?.message
      || "近期測驗資料不足。";
    elements.coachV2RecentTrend.dataset.status = data.recent_trend?.status
      || "INSUFFICIENT_DATA";

    elements.coachMessage.hidden = true;
    elements.feedbackList.hidden = true;
    elements.coachV2.hidden = false;
    return true;
  }

  async function loadCoachV2(assessmentId) {
    if (typeof window.motionAPI.getCoachV2 !== "function") return;
    try {
      const response = await window.motionAPI.getCoachV2(assessmentId);
      if (response?.success) renderCoachV2(response.data);
    } catch (error) {
      console.debug("AI Coach V2 unavailable; preserving existing Coach", error);
    }
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

  const numericScore = Number(score);
  elements.overallScore.textContent = Number.isFinite(numericScore)
    ? (Number.isInteger(numericScore)
        ? String(numericScore)
        : numericScore.toFixed(1))
    : "--";
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
  const hand =
    report?.features?.dominant_hand
    || report?.features?.racket_hand
    || report?.dominant_hand
    || report?.racket_hand;

  const estimatedHand =
    typeof hand === "string"
      ? hand
      : hand?.estimated || hand?.side;

  const handConfidence =
    typeof hand === "object"
      ? hand?.confidence
      : null;

  const handStatus =
    typeof hand === "object"
      ? hand?.status
      : null;

  const handSource =
    typeof hand === "object"
      ? hand?.source
      : null;

  const handLabel =
    estimatedHand === "right"
      ? "右手"
      : estimatedHand === "left"
        ? "左手"
        : (
          estimatedHand
          && estimatedHand !== "unknown"
            ? estimatedHand
            : null
        );

  if (!handLabel) {
    elements.hand.textContent =
      "尚無法判定";
  } else if (
    handStatus === "HUMAN_CONFIRMED"
    || handSource === "HUMAN_ANNOTATION"
  ) {
    elements.hand.textContent =
      `${handLabel} · 人工確認`;
  } else if (
    Number.isFinite(
      Number(handConfidence)
    )
  ) {
    elements.hand.textContent =
      `${handLabel} · 信心 ${
        Math.round(
          Number(handConfidence) * 100
        )
      }%`;
  } else {
    elements.hand.textContent =
      handLabel;
  }

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
    return motion;
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
      const motion = renderReport(response.data);
      await Promise.all([
        loadKeyMotion(assessmentId, motion),
        loadCoachV2(assessmentId)
      ]);
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
    window.location.href = "/";
  });
  await loadReport();
});
