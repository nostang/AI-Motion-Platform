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
  const adjustWindowButton =
    document.getElementById("adjustWindowButton");
  const annotationState =
    document.getElementById("annotationState");
  const annotationWindow =
    document.getElementById("annotationWindow");
  const fileBar = document.getElementById("fileBar");
  const fileName = document.getElementById("fileName");
  const fileMeta = document.getElementById("fileMeta");
  const statusPanel = document.getElementById("statusPanel");
  const statusMessage = document.getElementById("statusMessage");
  const toast = document.getElementById("toast");
  const motionGuard = document.getElementById("motionGuard");
  const motionGuardLabel = document.getElementById("motionGuardLabel");

  let selectedMotion = "footwork";
  let selectedFile = null;
  let busy = false;
  let pendingAssessment = null;

  const PENDING_ASSESSMENT_KEY =
    "aiMotionPendingAssessment";

  const motionNames = {
    footwork: "步法 FOOTWORK",
    serve: "正手發球 FOREHAND SERVE",
    clear: "高遠球 CLEAR"
  };

  function updateMotionGuard() {
    if (!selectedFile) return;
    motionGuardLabel.textContent = motionNames[selectedMotion];
    fileMeta.textContent =
      `${formatBytes(selectedFile.size)} · ${selectedMotion.toUpperCase()}`;
  }

  function selectMotion(card) {
    selectedMotion = card.dataset.motion;
    motionCards.forEach((item) => {
      const selected = item === card;
      item.classList.toggle("is-selected", selected);
      item.setAttribute("aria-checked", String(selected));
    });
    updateMotionGuard();
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
    motionGuard.hidden = false;
    updateMotionGuard();
    analyzeButton.disabled = false;
    adjustWindowButton.disabled = false;
    annotationState.hidden = true;
    pendingAssessment = null;
    sessionStorage.removeItem(
      PENDING_ASSESSMENT_KEY
    );
  }

  function clearFile() {
    selectedFile = null;
    videoInput.value = "";
    fileBar.hidden = true;
    motionGuard.hidden = true;
    annotationState.hidden = true;
    analyzeButton.disabled = true;
    adjustWindowButton.disabled = true;
    pendingAssessment = null;
    sessionStorage.removeItem(
      PENDING_ASSESSMENT_KEY
    );
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

  function formatAnnotationTime(ms) {
    const totalSeconds = ms / 1000;
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds - minutes * 60;

    return (
      `${String(minutes).padStart(2, "0")}:`
      + `${seconds.toFixed(3).padStart(6, "0")}`
    );
  }

  function restorePendingAssessment() {
    const stored = sessionStorage.getItem(
      PENDING_ASSESSMENT_KEY
    );

    if (!stored) return;

    try {
      const restored = JSON.parse(stored);

      if (
        !restored?.assessmentId
        || !restored?.motion
      ) {
        throw new Error("待分析資料不完整");
      }

      pendingAssessment = restored;
      selectedFile = null;
      selectedMotion = restored.motion;

      const motionCard = motionCards.find(
        (card) =>
          card.dataset.motion === selectedMotion
      );

      if (motionCard) {
        selectMotion(motionCard);
      }

      fileName.textContent =
        restored.fileName || "已上傳影片";
      fileMeta.textContent =
        `${selectedMotion.toUpperCase()}`
        + " · 原始影片已保留";
      fileBar.hidden = false;
      motionGuard.hidden = false;
      motionGuardLabel.textContent =
        motionNames[selectedMotion];

      adjustWindowButton.disabled = false;

      if (restored.annotation) {
        annotationState.hidden = false;
        annotationWindow.textContent =
          `${
            formatAnnotationTime(
              restored.annotation.startMs
            )
          }－${
            formatAnnotationTime(
              restored.annotation.endMs
            )
          }`;

        analyzeButton.disabled = false;
      } else {
        annotationState.hidden = true;
        analyzeButton.disabled = true;
      }
    } catch (error) {
      console.error(error);
      sessionStorage.removeItem(
        PENDING_ASSESSMENT_KEY
      );
      pendingAssessment = null;
    }
  }

  async function openActionWindow() {
    if (busy) return;

    if (pendingAssessment?.assessmentId) {
      const parameters = new URLSearchParams({
        id: pendingAssessment.assessmentId,
        return: "home"
      });

      window.location.href =
        `review.html?${parameters.toString()}`;
      return;
    }

    if (!selectedFile) return;

    const error = validateFile(selectedFile);
    if (error) {
      showToast(error);
      return;
    }

    busy = true;
    analyzeButton.disabled = true;
    adjustWindowButton.disabled = true;
    statusPanel.hidden = false;
    statusPanel.scrollIntoView({
      behavior: "smooth",
      block: "center"
    });
    setPipeline(
      "upload",
      "正在上傳影片，準備調整完整動作區間…"
    );

    try {
      const created = await api.createAssessment(
        selectedFile,
        selectedMotion,
        { deferAnalysis: true }
      );
      const assessmentId =
        api.extractAssessmentId(created);

      if (!assessmentId) {
        throw new Error(
          "API 未回傳 assessment_id"
        );
      }

      pendingAssessment = {
        assessmentId,
        motion: selectedMotion,
        fileName: selectedFile.name,
        fileSize: selectedFile.size,
        annotation: null
      };

      sessionStorage.setItem(
        PENDING_ASSESSMENT_KEY,
        JSON.stringify(pendingAssessment)
      );

      const parameters = new URLSearchParams({
        id: assessmentId,
        return: "home"
      });

      window.location.href =
        `review.html?${parameters.toString()}`;
    } catch (errorObject) {
      console.error(errorObject);
      showToast(
        errorObject.message
          || "影片上傳失敗",
        7000
      );
      statusMessage.textContent =
        `尚未進入動作區間調整：${
          errorObject.message || "未知錯誤"
        }`;
    } finally {
      busy = false;

      if (window.location.pathname.endsWith(
        "index.html"
      )) {
        analyzeButton.disabled = !selectedFile;
        adjustWindowButton.disabled =
          !selectedFile;
      }
    }
  }

  async function startAnalysis() {
    const hasAnnotatedAssessment = Boolean(
      pendingAssessment?.assessmentId
      && pendingAssessment?.annotation
    );

    if (
      busy
      || (!selectedFile && !hasAnnotatedAssessment)
    ) {
      return;
    }

    if (selectedFile) {
      const error = validateFile(selectedFile);

      if (error) {
        showToast(error);
        return;
      }
    }

    busy = true;
    analyzeButton.disabled = true;
    statusPanel.hidden = false;
    statusPanel.scrollIntoView({ behavior: "smooth", block: "center" });
    setPipeline("upload", `正在上傳 ${selectedMotion.toUpperCase()} 影片…`);

    try {
      let assessmentId;

      if (hasAnnotatedAssessment) {
        assessmentId =
          pendingAssessment.assessmentId;

        setPipeline(
          "upload",
          "正在套用已選取的完整動作區間…"
        );

        await api.analyzeAnnotation(
          assessmentId
        );
      } else {
        const created =
          await api.createAssessment(
            selectedFile,
            selectedMotion
          );

        assessmentId =
          api.extractAssessmentId(created);

        if (!assessmentId) {
          throw new Error(
            "API 未回傳 assessment_id"
          );
        }
      }

      setPipeline(
        "pose",
        `Assessment ${assessmentId}：`
        + "正在進行姿態與動作分析…"
      );
      await api.pollAssessment(assessmentId, (payload) => {
        const stage = inferStage(payload);
        setPipeline(stage, `Assessment ${assessmentId}：${api.normalizeStatus(payload) || "PROCESSING"}`);
      });

      setPipeline("report", "分析完成，正在開啟報告…");

      if (hasAnnotatedAssessment) {
        sessionStorage.removeItem(
          PENDING_ASSESSMENT_KEY
        );
        pendingAssessment = null;
      }

      const completedReportUrl = new URL(
        reportUrl(assessmentId),
        window.location.href
      );

      if (pageParameters.get("source") === "summary") {
        completedReportUrl.searchParams.set("from", "summary");
        completedReportUrl.searchParams.set(
          "user_id",
          pageParameters.get("user_id") || "1"
        );
      }

      window.setTimeout(() => {
        window.location.href =
          completedReportUrl.pathname +
          completedReportUrl.search;
      }, 500);
    } catch (errorObject) {
      console.error(errorObject);
      showToast(errorObject.message || "分析失敗，請確認 Backend 是否已啟動", 7000);
      statusMessage.textContent = `分析未完成：${errorObject.message || "未知錯誤"}`;
    } finally {
      busy = false;
      analyzeButton.disabled = !(
        selectedFile
        || pendingAssessment?.annotation
      );
      adjustWindowButton.disabled = !(
        selectedFile
        || pendingAssessment?.assessmentId
      );
    }
  }

  motionCards.forEach((card) => {
  card.addEventListener("click", () => selectMotion(card));
});

const pageParameters = new URLSearchParams(
  window.location.search
);
const requestedMotion = pageParameters.get("motion");
const requestedMotionCard = motionCards.find(
  (card) => card.dataset.motion === requestedMotion
);

if (requestedMotionCard) {
  selectMotion(requestedMotionCard);

  window.requestAnimationFrame(() => {
    const inputSection =
      document.getElementById("input-heading");

    inputSection?.scrollIntoView({
      behavior: "smooth",
      block: "start"
    });
  });
}
  chooseFileButton.addEventListener("click", () => videoInput.click());
  videoInput.addEventListener("change", () => setFile(videoInput.files[0]));
  removeFileButton.addEventListener("click", clearFile);
  adjustWindowButton.addEventListener(
    "click",
    openActionWindow
  );
  analyzeButton.addEventListener(
    "click",
    startAnalysis
  );
  window.addEventListener("aimotion:camera-recorded", (event) => {
    if (event.detail?.file) setFile(event.detail.file);
  });

  ["dragenter", "dragover"].forEach((eventName) => uploadZone.addEventListener(eventName, (event) => {
    event.preventDefault(); uploadZone.classList.add("is-dragging");
  }));
  ["dragleave", "drop"].forEach((eventName) => uploadZone.addEventListener(eventName, (event) => {
    event.preventDefault(); uploadZone.classList.remove("is-dragging");
  }));
  uploadZone.addEventListener("drop", (event) => setFile(event.dataTransfer.files[0]));

  restorePendingAssessment();
})();
