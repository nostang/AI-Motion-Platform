(function () {
  "use strict";

  const config = window.AI_MOTION_CONFIG;
  const api = window.AIMotionAPI;
  const motionCards = [...document.querySelectorAll(".motion-card")];
  const videoInput = document.getElementById("videoInput");
  const uploadZone = document.getElementById("uploadZone");
  const chooseFileButton = document.getElementById("chooseFileButton");
  const removeFileButton = document.getElementById("removeFileButton");
  const analyzeButton = document.getElementById("analyzeButton");
  const cameraButton = document.getElementById("cameraButton");
  const fileBar = document.getElementById("fileBar");
  const fileName = document.getElementById("fileName");
  const fileMeta = document.getElementById("fileMeta");
  const statusPanel = document.getElementById("statusPanel");
  const statusMessage = document.getElementById("statusMessage");
  const toast = document.getElementById("toast");

  let selectedMotion = "footwork";
  let selectedFile = null;
  let busy = false;

  function selectMotion(card) {
    selectedMotion = card.dataset.motion;
    motionCards.forEach((item) => {
      const selected = item === card;
      item.classList.toggle("is-selected", selected);
      item.setAttribute("aria-checked", String(selected));
    });
  }

  function formatBytes(bytes) {
    return bytes < 1024 * 1024
      ? `${Math.ceil(bytes / 1024)} KB`
      : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  function showToast(message, duration = 4200) {
    toast.textContent = message;
    toast.hidden = false;
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => { toast.hidden = true; }, duration);
  }

  function validateFile(file) {
    if (!file) return "請選擇影片";
    const extension = file.name.split(".").pop().toLowerCase();
    if (!config.ACCEPTED_EXTENSIONS.includes(extension)) return "目前僅支援 MP4 或 MOV 影片";
    if (file.size > config.MAX_FILE_SIZE_BYTES) return "影片不可超過 100 MB";
    return null;
  }

  function setFile(file) {
    const error = validateFile(file);
    if (error) { showToast(error); return; }
    selectedFile = file;
    fileName.textContent = file.name;
    fileMeta.textContent = `${formatBytes(file.size)} · ${selectedMotion.toUpperCase()}`;
    fileBar.hidden = false;
    analyzeButton.disabled = false;
  }

  function clearFile() {
    selectedFile = null;
    videoInput.value = "";
    fileBar.hidden = true;
    analyzeButton.disabled = true;
  }

  function setPipeline(stage, message) {
    const stages = ["upload", "pose", "feature", "assessment", "report"];
    const activeIndex = Math.max(0, stages.indexOf(stage));
    document.querySelectorAll("#pipeline [data-stage]").forEach((item, index) => {
      item.classList.toggle("done", index < activeIndex);
      item.classList.toggle("active", index === activeIndex);
    });
    statusMessage.textContent = message;
  }

  function inferStage(payload) {
    const raw = `${api.normalizeStatus(payload)} ${payload?.current_stage || ""}`.toUpperCase();
    if (raw.includes("REPORT") || raw.includes("COMPLETE") || raw.includes("SUCCESS")) return "report";
    if (raw.includes("ASSESS") || raw.includes("COACH")) return "assessment";
    if (raw.includes("FEATURE") || raw.includes("ANALYZ")) return "feature";
    return "pose";
  }

  function reportUrl(assessmentId) {
    const params = new URLSearchParams({ id: assessmentId });
    return `${config.REPORT_PAGE}?${params.toString()}`;
  }

  async function startAnalysis() {
    if (busy || !selectedFile) return;
    const error = validateFile(selectedFile);
    if (error) { showToast(error); return; }

    busy = true;
    analyzeButton.disabled = true;
    statusPanel.hidden = false;
    statusPanel.scrollIntoView({ behavior: "smooth", block: "center" });
    setPipeline("upload", `正在上傳 ${selectedMotion.toUpperCase()} 影片…`);

    try {
      const created = await api.createAssessment(selectedFile, selectedMotion);
      const assessmentId = api.extractAssessmentId(created);
      if (!assessmentId) throw new Error("API 未回傳 assessment_id");

      setPipeline("pose", `Assessment ${assessmentId}：正在進行姿態與動作分析…`);
      await api.pollAssessment(assessmentId, (payload) => {
        const stage = inferStage(payload);
        setPipeline(stage, `Assessment ${assessmentId}：${api.normalizeStatus(payload) || "PROCESSING"}`);
      });

      setPipeline("report", "分析完成，正在開啟報告…");
      window.setTimeout(() => { window.location.href = reportUrl(assessmentId); }, 500);
    } catch (errorObject) {
      console.error(errorObject);
      showToast(errorObject.message || "分析失敗，請確認 Backend 是否已啟動", 7000);
      statusMessage.textContent = `分析未完成：${errorObject.message || "未知錯誤"}`;
    } finally {
      busy = false;
      analyzeButton.disabled = !selectedFile;
    }
  }

  motionCards.forEach((card) => card.addEventListener("click", () => selectMotion(card)));
  chooseFileButton.addEventListener("click", () => videoInput.click());
  videoInput.addEventListener("change", () => setFile(videoInput.files[0]));
  removeFileButton.addEventListener("click", clearFile);
  analyzeButton.addEventListener("click", startAnalysis);
  cameraButton.addEventListener("click", () => showToast("Camera Recording V1.1 將在下一階段實作"));

  ["dragenter", "dragover"].forEach((eventName) => uploadZone.addEventListener(eventName, (event) => {
    event.preventDefault(); uploadZone.classList.add("is-dragging");
  }));
  ["dragleave", "drop"].forEach((eventName) => uploadZone.addEventListener(eventName, (event) => {
    event.preventDefault(); uploadZone.classList.remove("is-dragging");
  }));
  uploadZone.addEventListener("drop", (event) => setFile(event.dataTransfer.files[0]));
})();
