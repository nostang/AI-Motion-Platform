(function () {
  "use strict";

  const modal = document.getElementById("cameraModal");
  const openButton = document.getElementById("cameraButton");
  const closeButton = document.getElementById("cameraCloseButton");
  const startButton = document.getElementById("cameraStartButton");
  const retryButton = document.getElementById("cameraRetryButton");
  const useButton = document.getElementById("cameraUseButton");
  const livePreview = document.getElementById("cameraPreview");
  const recordedPreview = document.getElementById("recordedPreview");
  const captureGuide = document.getElementById("captureGuide");
  const poseGuideImage = document.getElementById("poseGuideImage");
  const poseGuideLabel = document.getElementById("poseGuideLabel");
  const qualityCanvas = document.getElementById("qualityCanvas");
  const countdown = document.getElementById("cameraCountdown");
  const recordingBadge = document.getElementById("recordingBadge");
  const recordingText = recordingBadge.querySelector("span");
  const status = document.getElementById("cameraStatus");
  const motionLabel = document.getElementById("cameraMotionLabel");
  const cameraStage = document.getElementById("cameraStage");

  const qualityElements = {
    fullBody: document.getElementById("qualityFullBody"),
    distance: document.getElementById("qualityDistance"),
    light: document.getElementById("qualityLight")
  };

  const labels = {
    footwork: "步法 FOOTWORK",
    serve: "正手發球 FOREHAND SERVE",
    clear: "高遠球 CLEAR"
  };

  const poseGuideLabels = {
    serve: "站在引導位置，保持完整身體與球拍入鏡",
    clear: "站在引導位置，上方保留揮拍空間"
  };

  const guideSteps = {
    serve: [
      ["assets/capture-guides/serve_step_1_ready.png", "準備", 1.38],
      ["assets/capture-guides/serve_step_2_swing.png", "揮拍", 1.38],
      ["assets/capture-guides/serve_step_3_finish.png", "完成動作", 1.20]
    ],
    clear: [
      ["assets/capture-guides/clear_step_1_ready.png", "架拍", 1.02],
      ["assets/capture-guides/clear_step_2_overhead.png", "引拍至頭頂", 1.02],
      ["assets/capture-guides/clear_step_3_contact.png", "高點揮拍", 1.04]
    ]
  };

  const distanceRanges = {
    footwork: { minimum: 0.28, maximum: 0.72 },
    serve: { minimum: 0.48, maximum: 0.88 },
    clear: { minimum: 0.44, maximum: 0.82 }
  };

  const QUALITY_SAMPLE_MS = 250;
  const GUIDE_FRAME_MS = 1050;
  const PASS_SAMPLE_COUNT = 4;
  const FAIL_SAMPLE_COUNT = 3;
  const MEDIAPIPE_VERSION = "0.10.21";
  const MEDIAPIPE_MODULE =
    `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}/+esm`;
  const MEDIAPIPE_WASM =
    `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}/wasm`;
  const POSE_MODEL =
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/" +
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task";

  let stream = null;
  let recorder = null;
  let chunks = [];
  let recordedBlob = null;
  let recordedUrl = null;
  let timer = null;
  let elapsedSeconds = 0;
  let closing = false;
  let qualityTimer = null;
  let qualityBusy = false;
  let poseLandmarker = null;
  let poseLandmarkerPromise = null;
  let poseQualityAvailable = true;
  let guideAnimationTimer = null;
  let guideAnimationTimeout = null;

  const qualityState = {
    fullBody: qualityEntry(),
    distance: qualityEntry(),
    light: qualityEntry()
  };

  function qualityEntry() {
    return {
      state: "pending",
      passSamples: 0,
      failSamples: 0
    };
  }

  function selectedMotion() {
    return document.querySelector(
      ".motion-card.is-selected"
    )?.dataset.motion || "footwork";
  }

  function bestMimeType() {
    return [
      "video/mp4;codecs=avc1",
      "video/mp4"
    ].find((type) => (
      MediaRecorder.isTypeSupported(type)
    )) || null;
  }

  function setCaptureGuide(motion) {
    stopGuideAnimation();
    captureGuide.className =
      `capture-guide guide-${motion}`;

    const steps = guideSteps[motion];

    if (poseGuideLabels[motion] && steps) {
      poseGuideLabel.textContent =
        poseGuideLabels[motion];
      poseGuideImage.src = steps[0][0];
      poseGuideImage.style.setProperty(
        "--guide-scale",
        steps[0][2]
      );
      startGuideAnimation(steps);
    } else {
      poseGuideImage.removeAttribute("src");
    }
  }

  function stopGuideAnimation() {
    clearInterval(guideAnimationTimer);
    clearTimeout(guideAnimationTimeout);
    guideAnimationTimer = null;
    guideAnimationTimeout = null;
    poseGuideImage.classList.remove("is-changing");
  }

  function startGuideAnimation(steps) {
    let frameIndex = 0;

    guideAnimationTimer = setInterval(() => {
      poseGuideImage.classList.add("is-changing");

      guideAnimationTimeout = window.setTimeout(() => {
        frameIndex = (frameIndex + 1) % steps.length;
        poseGuideImage.src = steps[frameIndex][0];
        poseGuideImage.style.setProperty(
          "--guide-scale",
          steps[frameIndex][2]
        );
        poseGuideImage.classList.remove("is-changing");
        guideAnimationTimeout = null;
      }, 170);
    }, GUIDE_FRAME_MS);
  }

  function renderQuality(key, state) {
    const element = qualityElements[key];
    const stateLabel = element.querySelector("strong");

    element.classList.remove(
      "is-pending",
      "is-pass",
      "is-fail",
      "is-unavailable"
    );
    element.classList.add(`is-${state}`);

    const labelsByState = {
      pending: "檢查中",
      pass: "PASS",
      fail: "NOT READY",
      unavailable: "暫無法檢查"
    };

    stateLabel.textContent = labelsByState[state];
  }

  function resetQuality() {
    for (const key of Object.keys(qualityState)) {
      qualityState[key] = qualityEntry();
      renderQuality(key, "pending");
    }
    poseQualityAvailable = true;
  }

  function markPoseQualityUnavailable() {
    poseQualityAvailable = false;

    for (const key of ["fullBody", "distance"]) {
      qualityState[key].state = "unavailable";
      renderQuality(key, "unavailable");
    }
  }

  function updateStableQuality(key, passes) {
    const entry = qualityState[key];

    if (entry.state === "unavailable") {
      return;
    }

    if (passes) {
      entry.passSamples += 1;
      entry.failSamples = 0;

      if (entry.passSamples >= PASS_SAMPLE_COUNT) {
        entry.state = "pass";
      }
    } else {
      entry.failSamples += 1;
      entry.passSamples = 0;

      if (entry.failSamples >= FAIL_SAMPLE_COUNT) {
        entry.state = "fail";
      }
    }

    renderQuality(key, entry.state);
  }

  async function createPoseLandmarker(delegate) {
    const vision = await import(MEDIAPIPE_MODULE);
    const fileset = await vision.FilesetResolver.forVisionTasks(
      MEDIAPIPE_WASM
    );

    return vision.PoseLandmarker.createFromOptions(
      fileset,
      {
        baseOptions: {
          modelAssetPath: POSE_MODEL,
          delegate
        },
        runningMode: "VIDEO",
        numPoses: 1,
        minPoseDetectionConfidence: 0.55,
        minPosePresenceConfidence: 0.55,
        minTrackingConfidence: 0.55,
        outputSegmentationMasks: false
      }
    );
  }

  async function ensurePoseLandmarker() {
    if (poseLandmarker) {
      return poseLandmarker;
    }

    if (!poseLandmarkerPromise) {
      poseLandmarkerPromise = (async () => {
        try {
          return await createPoseLandmarker("GPU");
        } catch (gpuError) {
          console.warn(
            "[CAPTURE_QUALITY] GPU unavailable; using CPU.",
            gpuError
          );
          return createPoseLandmarker("CPU");
        }
      })();
    }

    try {
      poseLandmarker = await poseLandmarkerPromise;
      return poseLandmarker;
    } catch (error) {
      poseLandmarkerPromise = null;
      console.warn(
        "[CAPTURE_QUALITY] Pose check unavailable.",
        error
      );
      markPoseQualityUnavailable();
      return null;
    }
  }

  function measureLight() {
    const context = qualityCanvas.getContext(
      "2d",
      { willReadFrequently: true }
    );

    context.drawImage(
      livePreview,
      0,
      0,
      qualityCanvas.width,
      qualityCanvas.height
    );

    const pixels = context.getImageData(
      0,
      0,
      qualityCanvas.width,
      qualityCanvas.height
    ).data;

    let luminanceTotal = 0;
    let darkPixels = 0;
    let samples = 0;

    for (let index = 0; index < pixels.length; index += 16) {
      const luminance = (
        pixels[index] * 0.2126
        + pixels[index + 1] * 0.7152
        + pixels[index + 2] * 0.0722
      );
      luminanceTotal += luminance;
      darkPixels += luminance < 35 ? 1 : 0;
      samples += 1;
    }

    const average = luminanceTotal / samples;
    const darkRatio = darkPixels / samples;

    return (
      average >= 48
      && average <= 225
      && darkRatio <= 0.62
    );
  }

  function visibleLandmark(landmark) {
    return Boolean(
      landmark
      && (landmark.visibility ?? 1) >= 0.45
      && (landmark.presence ?? 1) >= 0.45
    );
  }

  function evaluatePose(landmarks) {
    const requiredIndices = [
      0,
      11, 12,
      23, 24,
      25, 26,
      27, 28
    ];
    const required = requiredIndices.map(
      (index) => landmarks[index]
    );
    const fullBody = required.every((landmark) => (
      visibleLandmark(landmark)
      && landmark.x >= 0.025
      && landmark.x <= 0.975
      && landmark.y >= 0.02
      && landmark.y <= 0.98
    ));

    const visible = landmarks.filter(visibleLandmark);

    if (!visible.length) {
      return {
        fullBody: false,
        distance: false
      };
    }

    const ys = visible.map((landmark) => landmark.y);
    const bodyHeight = Math.max(...ys) - Math.min(...ys);
    const range = distanceRanges[selectedMotion()];

    return {
      fullBody,
      distance: (
        bodyHeight >= range.minimum
        && bodyHeight <= range.maximum
      )
    };
  }

  async function runQualityCheck() {
    if (
      qualityBusy
      || !stream?.active
      || livePreview.hidden
      || livePreview.readyState < 2
    ) {
      return;
    }

    qualityBusy = true;

    try {
      updateStableQuality("light", measureLight());

      if (!poseQualityAvailable || !poseLandmarker) {
        return;
      }

      const result = poseLandmarker.detectForVideo(
        livePreview,
        performance.now()
      );
      const landmarks = result.landmarks?.[0];

      if (!landmarks) {
        updateStableQuality("fullBody", false);
        updateStableQuality("distance", false);
        return;
      }

      const poseQuality = evaluatePose(landmarks);
      updateStableQuality(
        "fullBody",
        poseQuality.fullBody
      );
      updateStableQuality(
        "distance",
        poseQuality.distance
      );
    } catch (error) {
      console.warn(
        "[CAPTURE_QUALITY] Frame check failed.",
        error
      );
    } finally {
      qualityBusy = false;
    }
  }

  function stopQualityMonitoring() {
    clearInterval(qualityTimer);
    qualityTimer = null;
    qualityBusy = false;
  }

  function startQualityMonitoring() {
    stopQualityMonitoring();
    resetQuality();

    qualityTimer = setInterval(
      runQualityCheck,
      QUALITY_SAMPLE_MS
    );

    ensurePoseLandmarker().then((landmarker) => {
      if (
        landmarker
        && stream?.active
        && !modal.hidden
      ) {
        runQualityCheck();
      }
    });
  }

  async function ensureStream() {
    if (stream?.active) {
      return stream;
    }

    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: "environment" },
        width: { ideal: 1280 },
        height: { ideal: 720 }
      },
      audio: false
    });
    livePreview.srcObject = stream;
    await livePreview.play();
    return stream;
  }

  function releaseStream() {
    stopQualityMonitoring();
    stopGuideAnimation();
    stream?.getTracks().forEach((track) => track.stop());
    stream = null;
    livePreview.srcObject = null;
  }

  function clearRecording() {
    if (recordedUrl) {
      URL.revokeObjectURL(recordedUrl);
    }
    recordedUrl = null;
    recordedBlob = null;
    recordedPreview.removeAttribute("src");
    recordedPreview.load();
  }

  function setRecordControl(state) {
    const icon = startButton.querySelector(".record-control-icon");
    const label = startButton.querySelector(".record-control-label");
    const recording = state === "recording";

    startButton.dataset.recordState = state;
    startButton.classList.toggle("stop", recording);
    startButton.classList.toggle("primary", !recording);
    startButton.setAttribute("aria-label", recording ? "停止錄影" : "開始錄影");
    icon?.classList.toggle("record-control-dot", !recording);
    icon?.classList.toggle("record-control-stop", recording);
    if (label) label.textContent = recording ? "停止錄影" : "開始錄影";
    startButton.hidden = false;
    startButton.disabled = false;
  }

  function resetUi() {
    clearInterval(timer);
    timer = null;
    elapsedSeconds = 0;
    countdown.hidden = true;
    recordingBadge.hidden = true;
    setRecordControl("ready");
    retryButton.hidden = true;
    useButton.hidden = true;
    startButton.hidden = false;
    livePreview.hidden = false;
    recordedPreview.hidden = true;
    captureGuide.hidden = false;
    resetQuality();
    cameraStage.dataset.mode = "ready";
    status.textContent =
      "按下錄影鍵後倒數 3 秒，最長 30 秒。";
  }

  async function openCamera() {
    if (
      !window.MediaRecorder
      || !navigator.mediaDevices?.getUserMedia
    ) {
      alert(
        "這個瀏覽器不支援 Camera Recording，請改用影片上傳。"
      );
      return;
    }

    if (!bestMimeType()) {
      alert(
        "這個瀏覽器無法錄製 Backend 支援的 MP4，請改用影片上傳。"
      );
      return;
    }

    closing = false;
    const motion = selectedMotion();
    motionLabel.textContent = labels[motion];
    setCaptureGuide(motion);
    resetUi();
    clearRecording();
    modal.hidden = false;
    document.body.classList.add("camera-open");

    try {
      status.textContent = "正在開啟相機…";
      await ensureStream();
      startQualityMonitoring();
      status.textContent =
        "依畫面引導調整站位，確認後即可開始錄影。";
    } catch (error) {
      console.error(error);
      status.textContent =
        "無法開啟相機，請允許相機權限或改用影片上傳。";
      startButton.disabled = true;
    }
  }

  async function closeCamera() {
    closing = true;

    if (recorder?.state === "recording") {
      recorder.stop();
    }

    clearInterval(timer);
    releaseStream();
    clearRecording();
    modal.hidden = true;
    document.body.classList.remove("camera-open");
    startButton.disabled = false;
  }

  async function runCountdown() {
    startButton.hidden = true;
    cameraStage.dataset.mode = "countdown";
    status.textContent =
      `即將錄製：${labels[selectedMotion()]}`;
    countdown.hidden = false;

    for (const value of [3, 2, 1]) {
      countdown.textContent = value;
      await new Promise((resolve) => (
        setTimeout(resolve, 800)
      ));
    }

    countdown.textContent = "GO";
    await new Promise((resolve) => (
      setTimeout(resolve, 450)
    ));
    countdown.hidden = true;
  }

  function updateTimer() {
    elapsedSeconds += 1;
    const minutes = String(
      Math.floor(elapsedSeconds / 60)
    ).padStart(2, "0");
    const seconds = String(
      elapsedSeconds % 60
    ).padStart(2, "0");
    recordingText.textContent =
      `REC ${minutes}:${seconds}`;

    if (elapsedSeconds < 3) {
      status.textContent =
        `請持續錄影，至少還要 ${
          3 - elapsedSeconds
        } 秒。`;
    } else if (elapsedSeconds >= 25) {
      status.textContent =
        `錄影將在 ${
          Math.max(0, 30 - elapsedSeconds)
        } 秒後自動停止。`;
    } else {
      status.textContent =
        "錄影中，完成動作後可提前停止。";
    }

    if (elapsedSeconds >= 3) {
      startButton.disabled = false;
    }

    if (
      elapsedSeconds >= 30
      && recorder?.state === "recording"
    ) {
      recorder.stop();
    }
  }

  async function startRecording() {
    const mimeType = bestMimeType();

    try {
      await ensureStream();
      await runCountdown();
      // The guide is for framing before capture. Once REC starts,
      // remove it so it cannot obscure the athlete's real motion.
      stopGuideAnimation();
      captureGuide.hidden = true;
      chunks = [];
      recorder = new MediaRecorder(stream, { mimeType });
      recorder.addEventListener(
        "dataavailable",
        (event) => {
          if (event.data.size) {
            chunks.push(event.data);
          }
        }
      );
      recorder.addEventListener(
        "stop",
        finishRecording,
        { once: true }
      );
      recorder.start(250);
      elapsedSeconds = 0;
      recordingText.textContent = "REC 00:00";
      recordingBadge.hidden = false;
      cameraStage.dataset.mode = "recording";
      setRecordControl("recording");
      startButton.disabled = true;
      status.textContent =
        "錄影中，請完整做出所選動作。";
      timer = setInterval(updateTimer, 1000);
    } catch (error) {
      console.error(error);
      captureGuide.hidden = false;
      setCaptureGuide(selectedMotion());
      status.textContent =
        `無法開始錄影：${error.message}`;
      startButton.hidden = false;
    }
  }

  function finishRecording() {
    clearInterval(timer);
    timer = null;
    recordingBadge.hidden = true;
    startButton.hidden = true;

    if (closing || elapsedSeconds < 3) {
      return;
    }

    stopQualityMonitoring();
    stopGuideAnimation();
    recordedBlob = new Blob(
      chunks,
      { type: recorder.mimeType }
    );
    recordedUrl = URL.createObjectURL(recordedBlob);
    recordedPreview.src = recordedUrl;
    cameraStage.dataset.mode = "review";
    recordedPreview.hidden = false;
    livePreview.hidden = true;
    captureGuide.hidden = true;
    retryButton.hidden = false;
    useButton.hidden = false;
    status.textContent =
      `錄影完成：${elapsedSeconds} 秒 · ${
        (recordedBlob.size / 1024 / 1024).toFixed(1)
      } MB`;
  }

  async function retryRecording() {
    clearRecording();
    resetUi();
    await ensureStream();
    setCaptureGuide(selectedMotion());
    startQualityMonitoring();
    status.textContent =
      "依畫面引導重新調整站位，再開始錄影。";
  }

  async function useRecording() {
    if (!recordedBlob) {
      return;
    }

    const motion = selectedMotion();
    const timestamp = new Date()
      .toISOString()
      .replaceAll(":", "-")
      .replace(".", "-");
    const file = new File(
      [recordedBlob],
      `camera_${motion}_${timestamp}.mp4`,
      {
        type: "video/mp4",
        lastModified: Date.now()
      }
    );
    window.dispatchEvent(
      new CustomEvent(
        "aimotion:camera-recorded",
        { detail: { file, motion } }
      )
    );
    await closeCamera();
    document.getElementById("fileBar")?.scrollIntoView({
      behavior: "smooth",
      block: "center"
    });
  }

  openButton.addEventListener("click", openCamera);
  closeButton.addEventListener("click", closeCamera);
  startButton.addEventListener("click", () => {
    if (recorder?.state === "recording") {
      recorder.stop();
      return;
    }
    startRecording();
  });
  retryButton.addEventListener("click", retryRecording);
  useButton.addEventListener("click", useRecording);
  modal.addEventListener("click", (event) => {
    if (
      event.target === modal
      && recorder?.state !== "recording"
    ) {
      closeCamera();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape"
      && !modal.hidden
      && recorder?.state !== "recording"
    ) {
      closeCamera();
    }
  });
})();
