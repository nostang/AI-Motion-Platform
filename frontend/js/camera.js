(function () {
  "use strict";

  const modal = document.getElementById("cameraModal");
  const openButton = document.getElementById("cameraButton");
  const closeButton = document.getElementById("cameraCloseButton");
  const startButton = document.getElementById("cameraStartButton");
  const stopButton = document.getElementById("cameraStopButton");
  const retryButton = document.getElementById("cameraRetryButton");
  const useButton = document.getElementById("cameraUseButton");
  const livePreview = document.getElementById("cameraPreview");
  const recordedPreview = document.getElementById("recordedPreview");
  const bodyGuide = document.getElementById("bodyGuide");
  const countdown = document.getElementById("cameraCountdown");
  const recordingBadge = document.getElementById("recordingBadge");
  const recordingText = recordingBadge.querySelector("span");
  const status = document.getElementById("cameraStatus");
  const motionLabel = document.getElementById("cameraMotionLabel");

  const labels = {
    footwork: "步法 FOOTWORK",
    serve: "正手發球 FOREHAND SERVE",
    clear: "高遠球 CLEAR"
  };

  let stream = null;
  let recorder = null;
  let chunks = [];
  let recordedBlob = null;
  let recordedUrl = null;
  let timer = null;
  let elapsedSeconds = 0;
  let closing = false;

  function selectedMotion() {
    return document.querySelector(".motion-card.is-selected")?.dataset.motion || "footwork";
  }

  function bestMimeType() {
    return ["video/mp4;codecs=avc1", "video/mp4"].find((type) => MediaRecorder.isTypeSupported(type)) || null;
  }

  async function ensureStream() {
    if (stream?.active) return stream;
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false
    });
    livePreview.srcObject = stream;
    await livePreview.play();
    return stream;
  }

  function releaseStream() {
    stream?.getTracks().forEach((track) => track.stop());
    stream = null;
    livePreview.srcObject = null;
  }

  function clearRecording() {
    if (recordedUrl) URL.revokeObjectURL(recordedUrl);
    recordedUrl = null;
    recordedBlob = null;
    recordedPreview.removeAttribute("src");
    recordedPreview.load();
  }

  function resetUi() {
    clearInterval(timer);
    timer = null;
    elapsedSeconds = 0;
    countdown.hidden = true;
    recordingBadge.hidden = true;
    stopButton.hidden = true;
    stopButton.disabled = true;
    retryButton.hidden = true;
    useButton.hidden = true;
    startButton.hidden = false;
    livePreview.hidden = false;
    recordedPreview.hidden = true;
    bodyGuide.hidden = false;
    status.textContent = "按下開始後將倒數 3 秒。";
  }

  async function openCamera() {
    if (!window.MediaRecorder || !navigator.mediaDevices?.getUserMedia) {
      alert("這個瀏覽器不支援 Camera Recording，請改用影片上傳。");
      return;
    }
    if (!bestMimeType()) {
      alert("這個瀏覽器無法錄製 Backend 支援的 MP4，請改用影片上傳。");
      return;
    }
    closing = false;
    motionLabel.textContent = labels[selectedMotion()];
    resetUi();
    clearRecording();
    modal.hidden = false;
    document.body.classList.add("camera-open");
    try {
      status.textContent = "正在開啟相機…";
      await ensureStream();
      status.textContent = "確認全身入鏡，按下開始後將倒數 3 秒。";
    } catch (error) {
      console.error(error);
      status.textContent = "無法開啟相機，請允許相機權限或改用影片上傳。";
      startButton.disabled = true;
    }
  }

  async function closeCamera() {
    closing = true;
    if (recorder?.state === "recording") recorder.stop();
    clearInterval(timer);
    releaseStream();
    clearRecording();
    modal.hidden = true;
    document.body.classList.remove("camera-open");
    startButton.disabled = false;
  }

  async function runCountdown() {
    startButton.hidden = true;
    status.textContent = `即將錄製：${labels[selectedMotion()]}`;
    countdown.hidden = false;
    for (const value of [3, 2, 1]) {
      countdown.textContent = value;
      await new Promise((resolve) => setTimeout(resolve, 800));
    }
    countdown.textContent = "GO";
    await new Promise((resolve) => setTimeout(resolve, 450));
    countdown.hidden = true;
  }

  function updateTimer() {
    elapsedSeconds += 1;
    const minutes = String(Math.floor(elapsedSeconds / 60)).padStart(2, "0");
    const seconds = String(elapsedSeconds % 60).padStart(2, "0");
    recordingText.textContent = `REC ${minutes}:${seconds}`;
    status.textContent = elapsedSeconds < 3 ? `請持續錄影，至少還要 ${3 - elapsedSeconds} 秒。` : "錄影中，完成動作後按停止。";
    if (elapsedSeconds >= 3) stopButton.disabled = false;
    if (elapsedSeconds >= 30 && recorder?.state === "recording") recorder.stop();
  }

  async function startRecording() {
    const mimeType = bestMimeType();
    try {
      await ensureStream();
      await runCountdown();
      chunks = [];
      recorder = new MediaRecorder(stream, { mimeType });
      recorder.addEventListener("dataavailable", (event) => { if (event.data.size) chunks.push(event.data); });
      recorder.addEventListener("stop", finishRecording, { once: true });
      recorder.start(250);
      elapsedSeconds = 0;
      recordingText.textContent = "REC 00:00";
      recordingBadge.hidden = false;
      stopButton.hidden = false;
      stopButton.disabled = true;
      status.textContent = "錄影中，請完整做出所選動作。";
      timer = setInterval(updateTimer, 1000);
    } catch (error) {
      console.error(error);
      status.textContent = `無法開始錄影：${error.message}`;
      startButton.hidden = false;
    }
  }

  function finishRecording() {
    clearInterval(timer);
    timer = null;
    recordingBadge.hidden = true;
    stopButton.hidden = true;
    if (closing || elapsedSeconds < 3) return;
    recordedBlob = new Blob(chunks, { type: recorder.mimeType });
    recordedUrl = URL.createObjectURL(recordedBlob);
    recordedPreview.src = recordedUrl;
    recordedPreview.hidden = false;
    livePreview.hidden = true;
    bodyGuide.hidden = true;
    retryButton.hidden = false;
    useButton.hidden = false;
    status.textContent = `錄影完成：${elapsedSeconds} 秒 · ${(recordedBlob.size / 1024 / 1024).toFixed(1)} MB`;
  }

  async function retryRecording() {
    clearRecording();
    resetUi();
    await ensureStream();
    status.textContent = "確認全身入鏡，再重新開始錄影。";
  }

  async function useRecording() {
    if (!recordedBlob) return;
    const motion = selectedMotion();
    const timestamp = new Date().toISOString().replaceAll(":", "-").replace(".", "-");
    const file = new File([recordedBlob], `camera_${motion}_${timestamp}.mp4`, { type: "video/mp4", lastModified: Date.now() });
    window.dispatchEvent(new CustomEvent("aimotion:camera-recorded", { detail: { file, motion } }));
    await closeCamera();
    document.getElementById("fileBar")?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  openButton.addEventListener("click", openCamera);
  closeButton.addEventListener("click", closeCamera);
  startButton.addEventListener("click", startRecording);
  stopButton.addEventListener("click", () => { if (recorder?.state === "recording") recorder.stop(); });
  retryButton.addEventListener("click", retryRecording);
  useButton.addEventListener("click", useRecording);
  modal.addEventListener("click", (event) => { if (event.target === modal && recorder?.state !== "recording") closeCamera(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !modal.hidden && recorder?.state !== "recording") closeCamera(); });
})();
