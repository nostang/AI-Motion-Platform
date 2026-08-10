(function () {
  "use strict";

  const config = window.AI_MOTION_CONFIG;
  const parameters = new URLSearchParams(window.location.search);
  const assessmentId = parameters.get("id");

  const elements = {
    video: document.getElementById("reviewVideo"),
    motionChip: document.getElementById("motionChip"),
    currentTime: document.getElementById("currentTime"),
    totalTime: document.getElementById("totalTime"),
    playPause: document.getElementById("playPause"),
    trimTrack: document.getElementById("trimTrack"),
    trimSelection: document.getElementById("trimSelection"),
    playhead: document.getElementById("timelinePlayhead"),
    startHandle: document.getElementById("startHandle"),
    endHandle: document.getElementById("endHandle"),
    startRange: document.getElementById("startRange"),
    endRange: document.getElementById("endRange"),
    startMarker: document.getElementById("startMarker"),
    endMarker: document.getElementById("endMarker"),
    startValue: document.getElementById("startValue"),
    endValue: document.getElementById("endValue"),
    durationValue: document.getElementById("durationValue"),
    previousFrame: document.getElementById("previousFrame"),
    nextFrame: document.getElementById("nextFrame"),
    boundaryTarget: document.getElementById("boundaryTarget"),
    jumpStart: document.getElementById("jumpStart"),
    jumpEnd: document.getElementById("jumpEnd"),
    previewWindow: document.getElementById("previewWindow"),
    autoWindow: document.getElementById("autoWindow"),
    form: document.getElementById("annotationForm"),
    annotationDetails: document.getElementById("annotationDetails"),
    actionType: document.getElementById("actionType"),
    racketSide: document.getElementById("racketSide"),
    notes: document.getElementById("notes"),
    saveButton: document.getElementById("saveAnnotation"),
    saveStatus: document.getElementById("saveStatus"),
    assessmentLabel: document.getElementById("assessmentLabel"),
    errorBanner: document.getElementById("errorBanner")
  };

  let previewing = false;
  let pendingAnnotation = null;
  let motionType = "";
  let activeBoundary = "start";

  const FRAME_STEP_SECONDS = 1 / 30;

  function endpoint(path) {
    return `${config.API_BASE_URL}${path}`;
  }

  async function request(path, options) {
    const response = await fetch(endpoint(path), options);
    const payload = await response.json();

    if (!response.ok || payload?.success === false) {
      throw new Error(
        payload?.error?.message
        || payload?.detail
        || `API request failed (${response.status})`
      );
    }

    return payload?.data;
  }

  function formatTime(seconds) {
    const safe = Math.max(0, Number(seconds) || 0);
    const minutes = Math.floor(safe / 60);
    const remainder = safe - minutes * 60;

    return (
      String(minutes).padStart(2, "0")
      + ":"
      + remainder.toFixed(3).padStart(6, "0")
    );
  }

  function startSeconds() {
    return Number(elements.startRange.value);
  }

  function endSeconds() {
    return Number(elements.endRange.value);
  }

  function markerPosition(seconds) {
    const duration = elements.video.duration || 1;
    return Math.max(
      0,
      Math.min(100, seconds / duration * 100)
    );
  }

  function updateTimelineMarkers() {
    const duration = elements.video.duration;

    if (!Number.isFinite(duration) || duration <= 0) return;

    const start = startSeconds();
    const end = endSeconds();
    const startPercent = markerPosition(start);
    const endPercent = markerPosition(end);

    elements.startMarker.style.left = `${startPercent}%`;
    elements.endMarker.style.left = `${endPercent}%`;

    elements.trimSelection.style.left =
      `${startPercent}%`;
    elements.trimSelection.style.width =
      `${Math.max(0, endPercent - startPercent)}%`;

    elements.startHandle.value = String(start);
    elements.endHandle.value = String(end);
  }

  function selectBoundary(boundary) {
    activeBoundary = boundary;

    elements.boundaryTarget.textContent =
      boundary === "start" ? "開始" : "結束";

    elements.startHandle.classList.toggle(
      "is-active",
      boundary === "start"
    );
    elements.endHandle.classList.toggle(
      "is-active",
      boundary === "end"
    );
  }

  function nudgeActiveBoundary(deltaSeconds) {
    if (activeBoundary === "start") {
      const value = Math.max(
        0,
        Math.min(
          endSeconds() - 0.001,
          startSeconds() + deltaSeconds
        )
      );

      elements.startRange.value = String(value);
      elements.startHandle.value = String(value);
      seek(value);
    } else {
      const value = Math.max(
        startSeconds() + 0.001,
        Math.min(
          elements.video.duration,
          endSeconds() + deltaSeconds
        )
      );

      elements.endRange.value = String(value);
      elements.endHandle.value = String(value);
      seek(value);
    }

    updateWindowDisplay();
  }

  function updateWindowDisplay() {
    const start = startSeconds();
    const end = endSeconds();

    elements.startValue.textContent = formatTime(start);
    elements.endValue.textContent = formatTime(end);
    elements.durationValue.textContent =
      `${Math.max(0, end - start).toFixed(3)} 秒`;

    updateTimelineMarkers();
  }

  function applyAnnotation(annotation) {
    if (!annotation?.window) return;

    elements.startRange.value = String(
      annotation.window.start_ms / 1000
    );
    elements.endRange.value = String(
      annotation.window.end_ms / 1000
    );
    elements.actionType.value = annotation.action_type || "";
    elements.racketSide.value = annotation.racket_side || "";
    elements.notes.value = annotation.notes || "";
    elements.saveStatus.textContent = "已載入先前標注";

    if (
      annotation.action_type
      || annotation.racket_side
      || annotation.notes
    ) {
      elements.annotationDetails.open = true;
    }

    updateWindowDisplay();
  }

  function showError(message) {
    elements.errorBanner.textContent = message;
    elements.errorBanner.hidden = false;
  }

  function seek(seconds) {
    elements.video.currentTime = Math.max(
      0,
      Math.min(
        elements.video.duration || seconds,
        seconds
      )
    );
  }

  async function initialize() {
    if (!assessmentId) {
      throw new Error("網址缺少 Assessment ID");
    }

    elements.assessmentLabel.textContent =
      `ASSESSMENT / ${assessmentId}`;

    const encodedId = encodeURIComponent(assessmentId);

    elements.video.src = endpoint(
      `/motion-assessments/${encodedId}/video`
    );

    const [assessment, annotation, report] =
      await Promise.all([
        request(`/motion-assessments/${encodedId}`),
        request(`/motion-assessments/${encodedId}/annotation`),
        request(`/motion-assessments/${encodedId}/report`)
          .catch(() => null)
      ]);

    motionType = String(
      assessment?.assessment_type || ""
    ).toLowerCase();

    elements.motionChip.textContent =
      motionType.toUpperCase() || "MOTION";

    pendingAnnotation =
      annotation?.annotation === null
        ? null
        : annotation;

    const automatic =
      report?.features?.analysis_window;

    if (automatic) {
      elements.autoWindow.hidden = false;
      elements.autoWindow.textContent =
        `系統自動窗口：`
        + `${formatTime(automatic.start_ms / 1000)}`
        + ` → ${formatTime(automatic.end_ms / 1000)}`
        + `（${(
          (automatic.end_ms - automatic.start_ms)
          / 1000
        ).toFixed(3)} 秒）`;
    }
  }

  elements.video.addEventListener(
    "loadedmetadata",
    () => {
      const duration = elements.video.duration;

      elements.startHandle.max = String(duration);
      elements.endHandle.max = String(duration);
      elements.startHandle.value = "0";
      elements.endHandle.value = String(duration);
      elements.totalTime.textContent =
        formatTime(duration);

      elements.startRange.value = "0";
      elements.endRange.value = String(duration);

      if (pendingAnnotation) {
        applyAnnotation(pendingAnnotation);
      } else {
        updateWindowDisplay();
      }

      selectBoundary("start");
    }
  );

  elements.video.addEventListener("timeupdate", () => {
    elements.currentTime.textContent =
      formatTime(elements.video.currentTime);

    elements.playhead.style.left =
      `${markerPosition(elements.video.currentTime)}%`;

    if (
      previewing
      && elements.video.currentTime >= endSeconds()
    ) {
      elements.video.pause();
      previewing = false;
      elements.previewWindow.textContent =
        "▶ 預覽選取區段";
    }
  });

  elements.startHandle.addEventListener(
    "input",
    () => {
      previewing = false;
      selectBoundary("start");
      elements.video.pause();

      const maximumStart = Math.max(
        0,
        endSeconds() - 0.001
      );
      const value = Math.min(
        Number(elements.startHandle.value),
        maximumStart
      );

      elements.startRange.value = String(value);
      seek(value);
      updateWindowDisplay();
    }
  );

  elements.endHandle.addEventListener(
    "input",
    () => {
      previewing = false;
      selectBoundary("end");
      elements.video.pause();

      const minimumEnd = Math.min(
        elements.video.duration,
        startSeconds() + 0.001
      );
      const value = Math.max(
        Number(elements.endHandle.value),
        minimumEnd
      );

      elements.endRange.value = String(value);
      seek(value);
      updateWindowDisplay();
    }
  );

  elements.trimTrack.addEventListener(
    "pointerdown",
    (event) => {
      if (
        event.target === elements.startHandle
        || event.target === elements.endHandle
      ) {
        return;
      }

      const rect =
        elements.trimTrack.getBoundingClientRect();
      const ratio = Math.max(
        0,
        Math.min(
          1,
          (event.clientX - rect.left) / rect.width
        )
      );

      seek(ratio * elements.video.duration);
    }
  );

  elements.playPause.addEventListener(
    "click",
    async () => {
      if (elements.video.paused) {
        try {
          await elements.video.play();
        } catch (error) {
          showError("影片目前無法播放");
        }
      } else {
        elements.video.pause();
      }
    }
  );

  elements.video.addEventListener(
    "click",
    () => elements.playPause.click()
  );
  elements.video.addEventListener(
    "play",
    () => {
      elements.playPause.textContent = "Ⅱ";
    }
  );
  elements.video.addEventListener(
    "pause",
    () => {
      elements.playPause.textContent = "▶";
    }
  );

  elements.previousFrame.addEventListener(
    "click",
    () => nudgeActiveBoundary(
      -FRAME_STEP_SECONDS
    )
  );

  elements.nextFrame.addEventListener(
    "click",
    () => nudgeActiveBoundary(
      FRAME_STEP_SECONDS
    )
  );
  elements.jumpStart.addEventListener(
    "click",
    () => seek(startSeconds())
  );
  elements.jumpEnd.addEventListener(
    "click",
    () => seek(endSeconds())
  );

  elements.previewWindow.addEventListener(
    "click",
    async () => {
      seek(startSeconds());
      previewing = true;
      elements.previewWindow.textContent = "■ 預覽中";

      try {
        await elements.video.play();
      } catch (error) {
        previewing = false;
        elements.previewWindow.textContent =
          "▶ 預覽選取區段";
      }
    }
  );

  elements.form.addEventListener(
    "submit",
    async (event) => {
      event.preventDefault();

      const startMs = Math.round(
        startSeconds() * 1000
      );
      const endMs = Math.round(
        endSeconds() * 1000
      );

      if (endMs <= startMs) {
        showError("結束時間必須晚於開始時間");
        return;
      }

      elements.saveButton.disabled = true;
      elements.saveStatus.textContent = "正在儲存…";

      try {
        await request(
          `/motion-assessments/${
            encodeURIComponent(assessmentId)
          }/annotation`,
          {
            method: "PUT",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              start_ms: startMs,
              end_ms: endMs,
              status: "COMPLETE",
              motion_type: motionType,
              action_type:
                elements.actionType.value || null,
              racket_side:
                elements.racketSide.value || null,
              calibration_eligibility: "INCLUDED",
              notes:
                elements.notes.value.trim() || null
            })
          }
        );

        elements.saveStatus.textContent =
          "✓ 完整動作區段已儲存";
        elements.errorBanner.hidden = true;

        const returnTarget =
          new URLSearchParams(
            window.location.search
          ).get("return");

        if (returnTarget === "home") {
          const storageKey =
            "aiMotionPendingAssessment";
          const stored =
            sessionStorage.getItem(storageKey);

          if (!stored) {
            throw new Error(
              "找不到待分析影片資訊"
            );
          }

          const pending = JSON.parse(stored);

          if (
            pending.assessmentId
            !== assessmentId
          ) {
            throw new Error(
              "Assessment ID 與暫存資料不一致"
            );
          }

          pending.annotation = {
            startMs,
            endMs,
            durationMs: endMs - startMs
          };

          sessionStorage.setItem(
            storageKey,
            JSON.stringify(pending)
          );

          window.setTimeout(() => {
            const parameters =
              new URLSearchParams({
                annotation: assessmentId
              });

            window.location.href =
              `index.html?${
                parameters.toString()
              }`;
          }, 450);
        }
      } catch (error) {
        elements.saveStatus.textContent = "儲存失敗";
        showError(error.message);
      } finally {
        elements.saveButton.disabled = false;
      }
    }
  );

  initialize().catch((error) => {
    showError(error.message);
  });
})();
