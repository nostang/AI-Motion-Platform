(function () {
  "use strict";

  const DEFAULT_MAX_SECONDS = 30;
  let activeObjectUrl = null;

  function ensureUi() {
    if (document.getElementById("videoPreprocessModal")) return;

    const modal = document.createElement("div");
    modal.id = "videoPreprocessModal";
    modal.className = "video-preprocess-modal";
    modal.hidden = true;
    modal.innerHTML = `
      <div class="video-preprocess-dialog" role="dialog" aria-modal="true" aria-labelledby="videoPreprocessTitle">
        <div class="video-preprocess-head">
          <div>
            <p>LOCAL PRE-CHECK</p>
            <h3 id="videoPreprocessTitle">選擇分析片段</h3>
          </div>
          <button id="videoPreprocessClose" type="button" aria-label="關閉">×</button>
        </div>

        <p class="video-preprocess-copy">
          影片超過 30 秒，請選擇要讓 AI 分析的動作片段。原始影片不會被修改。
        </p>

        <video id="videoPreprocessPreview" controls playsinline muted></video>

        <div class="video-preprocess-meta" id="videoPreprocessMeta"></div>

        <div class="video-segment-picker">
          <div class="video-segment-labels">
            <span id="videoSegmentTimelineStart">00:00</span>
            <strong>分析片段</strong>
            <span id="videoSegmentTimelineEnd">00:00</span>
          </div>

          <div class="video-segment-track">
            <div id="videoSegmentSelection" class="video-segment-selection"></div>
            <input id="videoSegmentStartRange" class="video-segment-range video-segment-range-start"
              type="range" min="0" step="0.1" value="0" aria-label="分析片段開始時間">
            <input id="videoSegmentEndRange" class="video-segment-range video-segment-range-end"
              type="range" min="0" step="0.1" value="30" aria-label="分析片段結束時間">
          </div>

          <div class="video-segment-summary">
            <strong id="videoSegmentDuration">分析長度 30.0 秒</strong>
            <span id="videoSegmentValidity">✓ 符合分析條件</span>
          </div>
        </div>

        <div class="video-preprocess-range">
          <label>
            <span>開始時間</span>
            <input id="videoPreprocessStart" type="number" min="0" step="0.1" value="0">
          </label>
          <label>
            <span>結束時間</span>
            <input id="videoPreprocessEnd" type="number" min="0" step="0.1" value="30">
          </label>
        </div>

        <button class="video-segment-preview-button secondary-button"
          id="videoSegmentPreviewButton" type="button">
          ▶ 預覽分析片段
        </button>

        <div class="video-preprocess-status" id="videoPreprocessStatus"></div>

        <div class="video-preprocess-actions">
          <button class="secondary-button" id="videoPreprocessCancel" type="button">取消</button>
          <button class="primary-button" id="videoPreprocessConfirm" type="button">使用這個片段</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  function waitForMetadata(video) {
    return new Promise((resolve, reject) => {
      if (video.readyState >= 1 && Number.isFinite(video.duration)) {
        resolve();
        return;
      }

      const onLoaded = () => {
        cleanup();
        resolve();
      };

      const onError = () => {
        cleanup();
        reject(new Error("無法讀取影片資訊"));
      };

      const cleanup = () => {
        video.removeEventListener("loadedmetadata", onLoaded);
        video.removeEventListener("error", onError);
      };

      video.addEventListener("loadedmetadata", onLoaded, { once: true });
      video.addEventListener("error", onError, { once: true });
    });
  }

  async function inspect(file) {
    console.log(
      "[VIDEO_PREPROCESS] selected:",
      file?.name,
      `${(file?.size / 1024 / 1024).toFixed(2)} MB`,
      file?.type || "(no mime)"
    );

    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.muted = true;
    video.playsInline = true;
    video.src = url;

    try {
      await waitForMetadata(video);
      const info = {
        duration: video.duration,
        width: video.videoWidth,
        height: video.videoHeight,
        type: file.type || "",
        size: file.size
      };

      console.log(
        "[VIDEO_PREPROCESS] metadata:",
        `${info.duration.toFixed(2)}s`,
        `${info.width}x${info.height}`,
        `${(info.size / 1024 / 1024).toFixed(2)} MB`
      );

      return info;
    } finally {
      URL.revokeObjectURL(url);
    }
  }

  function chooseRecorderMime() {
    if (!window.MediaRecorder) return null;

    const candidates = [
      "video/mp4;codecs=avc1.42E01E",
      "video/mp4",
      "video/webm;codecs=vp9",
      "video/webm;codecs=vp8",
      "video/webm"
    ];

    for (const type of candidates) {
      if (
        !MediaRecorder.isTypeSupported
        || MediaRecorder.isTypeSupported(type)
      ) {
        return type;
      }
    }

    return "";
  }

  function seekTo(video, time) {
    return new Promise((resolve, reject) => {
      const done = () => {
        cleanup();
        resolve();
      };

      const fail = () => {
        cleanup();
        reject(new Error("影片定位失敗"));
      };

      const cleanup = () => {
        video.removeEventListener("seeked", done);
        video.removeEventListener("error", fail);
      };

      video.addEventListener("seeked", done, { once: true });
      video.addEventListener("error", fail, { once: true });
      video.currentTime = time;
    });
  }

  async function renderTrimmedBlob(video, start, end, onStatus) {
    if (!HTMLCanvasElement.prototype.captureStream) {
      throw new Error("此瀏覽器不支援本機影片裁剪");
    }

    const mimeType = chooseRecorderMime();

    if (mimeType === null) {
      throw new Error("此瀏覽器不支援 MediaRecorder");
    }

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const context = canvas.getContext("2d", { alpha: false });

    video.pause();
    await seekTo(video, start);

    const stream = canvas.captureStream(30);
    const chunks = [];

    const recorder = new MediaRecorder(
      stream,
      mimeType
        ? { mimeType, videoBitsPerSecond: 4_000_000 }
        : { videoBitsPerSecond: 4_000_000 }
    );

    recorder.addEventListener("dataavailable", (event) => {
      if (event.data?.size) chunks.push(event.data);
    });

    const stopped = new Promise((resolve) => {
      recorder.addEventListener("stop", resolve, { once: true });
    });

    let finished = false;

    function finish() {
      if (finished) return;
      finished = true;

      try { video.pause(); } catch (_) {}
      try { recorder.stop(); } catch (_) {}

      stream.getTracks().forEach((track) => track.stop());
    }

    function drawFrame() {
      if (finished) return;

      try {
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
      } catch (_) {}

      if (video.currentTime >= end - 0.03 || video.ended) {
        finish();
        return;
      }

      if ("requestVideoFrameCallback" in HTMLVideoElement.prototype) {
        video.requestVideoFrameCallback(drawFrame);
      } else {
        requestAnimationFrame(drawFrame);
      }
    }

    onStatus?.(
      `本機裁剪中：${start.toFixed(1)}s → ${end.toFixed(1)}s\n`
      + "請保持頁面在前景。"
    );

    recorder.start(250);

    if ("requestVideoFrameCallback" in HTMLVideoElement.prototype) {
      video.requestVideoFrameCallback(drawFrame);
    } else {
      requestAnimationFrame(drawFrame);
    }

    await video.play();

    const watchdog = setTimeout(
      finish,
      Math.max(5000, (end - start + 5) * 1000)
    );

    await stopped;
    clearTimeout(watchdog);

    if (!chunks.length) {
      throw new Error("本機裁剪沒有產生影片資料");
    }

    const actualType =
      recorder.mimeType
      || mimeType
      || "video/mp4";

    const blob = new Blob(chunks, { type: actualType });

    if (blob.size < 1000) {
      throw new Error("本機裁剪輸出異常");
    }

    return blob;
  }

  function formatTime(seconds) {
    const safe = Math.max(0, Number(seconds) || 0);
    const minutes = Math.floor(safe / 60);
    const remainder = Math.floor(safe % 60);

    return `${String(minutes).padStart(2, "0")}:${String(
      remainder
    ).padStart(2, "0")}`;
  }

  async function openTrimDialog(file, info, maxSeconds) {
    ensureUi();

    const modal = document.getElementById("videoPreprocessModal");
    const preview = document.getElementById("videoPreprocessPreview");
    const meta = document.getElementById("videoPreprocessMeta");
    const startInput = document.getElementById("videoPreprocessStart");
    const endInput = document.getElementById("videoPreprocessEnd");
    const status = document.getElementById("videoPreprocessStatus");
    const confirm = document.getElementById("videoPreprocessConfirm");
    const cancel = document.getElementById("videoPreprocessCancel");
    const close = document.getElementById("videoPreprocessClose");
    const startRange = document.getElementById("videoSegmentStartRange");
    const endRange = document.getElementById("videoSegmentEndRange");
    const selection = document.getElementById("videoSegmentSelection");
    const durationLabel = document.getElementById("videoSegmentDuration");
    const validityLabel = document.getElementById("videoSegmentValidity");
    const timelineStart = document.getElementById("videoSegmentTimelineStart");
    const timelineEnd = document.getElementById("videoSegmentTimelineEnd");
    const previewButton = document.getElementById("videoSegmentPreviewButton");

    if (activeObjectUrl) URL.revokeObjectURL(activeObjectUrl);

    activeObjectUrl = URL.createObjectURL(file);
    preview.src = activeObjectUrl;
    preview.load();

    const initialEnd = Math.min(maxSeconds, info.duration);

    startInput.value = "0.0";
    endInput.value = initialEnd.toFixed(1);
    startInput.max = info.duration.toFixed(1);
    endInput.max = info.duration.toFixed(1);

    startRange.max = info.duration.toFixed(1);
    endRange.max = info.duration.toFixed(1);
    startRange.value = "0";
    endRange.value = initialEnd.toFixed(1);

    timelineStart.textContent = "00:00";
    timelineEnd.textContent = formatTime(info.duration);

    const clamp = (value, minimum, maximum) => (
      Math.min(maximum, Math.max(minimum, value))
    );

    const updatePicker = (source) => {
      let start = Number(
        source === "startInput"
          ? startInput.value
          : startRange.value
      );
      let end = Number(
        source === "endInput"
          ? endInput.value
          : endRange.value
      );

      if (!Number.isFinite(start)) start = 0;
      if (!Number.isFinite(end)) end = initialEnd;

      start = clamp(start, 0, info.duration);
      end = clamp(end, 0, info.duration);

      if (source === "startRange" || source === "startInput") {
        if (start >= end) start = Math.max(0, end - 0.1);
        if (end - start > maxSeconds) {
          end = Math.min(info.duration, start + maxSeconds);
        }
      } else {
        if (end <= start) end = Math.min(info.duration, start + 0.1);
        if (end - start > maxSeconds) {
          start = Math.max(0, end - maxSeconds);
        }
      }

      start = Math.round(start * 10) / 10;
      end = Math.round(end * 10) / 10;

      startInput.value = start.toFixed(1);
      endInput.value = end.toFixed(1);
      startRange.value = String(start);
      endRange.value = String(end);

      const startPercent = info.duration
        ? (start / info.duration) * 100
        : 0;
      const endPercent = info.duration
        ? (end / info.duration) * 100
        : 100;

      selection.style.left = `${startPercent}%`;
      selection.style.width =
        `${Math.max(0, endPercent - startPercent)}%`;

      const segmentDuration = end - start;
      durationLabel.textContent =
        `分析長度 ${segmentDuration.toFixed(1)} 秒`;

      const valid =
        segmentDuration > 0
        && segmentDuration <= maxSeconds + 0.05;

      validityLabel.textContent = valid
        ? "✓ 符合分析條件"
        : `片段不可超過 ${maxSeconds} 秒`;

      validityLabel.dataset.valid = valid ? "true" : "false";
    };

    updatePicker("startRange");

    meta.textContent =
      `${info.duration.toFixed(2)} 秒 · `
      + `${info.width}×${info.height} · `
      + `${(file.size / 1024 / 1024).toFixed(2)} MB`;

    status.textContent = "影片只在目前瀏覽器中讀取，尚未上傳.";
    modal.hidden = false;

    return new Promise((resolve) => {
      let settled = false;

      let previewStopHandler = null;

      const stopSegmentPreview = () => {
        if (previewStopHandler) {
          preview.removeEventListener(
            "timeupdate",
            previewStopHandler
          );
          previewStopHandler = null;
        }
      };

      const cleanup = () => {
        confirm.removeEventListener("click", onConfirm);
        cancel.removeEventListener("click", onCancel);
        close.removeEventListener("click", onCancel);
        startRange.removeEventListener("input", onStartRange);
        endRange.removeEventListener("input", onEndRange);
        startInput.removeEventListener("input", onStartInput);
        endInput.removeEventListener("input", onEndInput);
        previewButton.removeEventListener(
          "click",
          onPreviewSegment
        );
        stopSegmentPreview();
      };

      const finish = (value) => {
        if (settled) return;
        settled = true;
        cleanup();
        modal.hidden = true;
        preview.pause();
        resolve(value);
      };

      const onCancel = () => finish(null);

      const onStartRange = () => {
        stopSegmentPreview();
        updatePicker("startRange");
        preview.currentTime = Number(startRange.value);
      };

      const onEndRange = () => {
        stopSegmentPreview();
        updatePicker("endRange");
        preview.currentTime = Number(endRange.value);
      };

      const onStartInput = () => {
        stopSegmentPreview();
        startRange.value = startInput.value;
        updatePicker("startInput");
      };

      const onEndInput = () => {
        stopSegmentPreview();
        endRange.value = endInput.value;
        updatePicker("endInput");
      };

      const onPreviewSegment = async () => {
        const start = Number(startInput.value);
        const end = Number(endInput.value);

        if (!Number.isFinite(start) || !Number.isFinite(end)) {
          return;
        }

        stopSegmentPreview();
        preview.pause();

        try {
          await seekTo(preview, start);

          previewStopHandler = () => {
            if (preview.currentTime >= end - 0.03) {
              preview.pause();
              stopSegmentPreview();
            }
          };

          preview.addEventListener(
            "timeupdate",
            previewStopHandler
          );

          await preview.play();
        } catch (error) {
          console.error("[VIDEO_PREPROCESS]", error);
          status.textContent =
            error.message || "無法預覽分析片段";
        }
      };

      const onConfirm = async () => {
        const start = Number(startInput.value);
        const end = Number(endInput.value);

        if (
          !Number.isFinite(start)
          || !Number.isFinite(end)
          || start < 0
          || end <= start
          || end > info.duration + 0.05
        ) {
          status.textContent = "開始／結束時間不合法。";
          return;
        }

        if (end - start > maxSeconds + 0.05) {
          status.textContent = `分析片段不可超過 ${maxSeconds} 秒。`;
          return;
        }

        confirm.disabled = true;
        cancel.disabled = true;
        close.disabled = true;

        try {
          const blob = await renderTrimmedBlob(
            preview,
            start,
            end,
            (message) => {
              status.textContent = message;
            }
          );

          if (blob.type.includes("webm")) {
            throw new Error(
              "目前瀏覽器只產生 WebM；AI Motion 正式流程僅接受 MP4/MOV"
            );
          }

          const baseName = file.name.replace(/\.[^.]+$/, "");

          const trimmedFile = new File(
            [blob],
            `${baseName}_trim_${start.toFixed(1)}-${end.toFixed(1)}.mp4`,
            {
              type: blob.type || "video/mp4",
              lastModified: Date.now()
            }
          );

          status.textContent =
            `裁剪完成 · ${(trimmedFile.size / 1024 / 1024).toFixed(2)} MB`;

          finish(trimmedFile);
        } catch (error) {
          console.error("[VIDEO_PREPROCESS]", error);
          status.textContent = error.message || "本機裁剪失敗";
        } finally {
          confirm.disabled = false;
          cancel.disabled = false;
          close.disabled = false;
        }
      };

      confirm.addEventListener("click", onConfirm);
      cancel.addEventListener("click", onCancel);
      close.addEventListener("click", onCancel);
      startRange.addEventListener("input", onStartRange);
      endRange.addEventListener("input", onEndRange);
      startInput.addEventListener("input", onStartInput);
      endInput.addEventListener("input", onEndInput);
      previewButton.addEventListener(
        "click",
        onPreviewSegment
      );
    });
  }

  async function selectSegment(file, options = {}) {
    const maxSeconds = Number(
      options.maxDurationSeconds || DEFAULT_MAX_SECONDS
    );

    const info = options.info || await inspect(file);

    return openTrimDialog(
      file,
      info,
      maxSeconds
    );
  }

  async function prepare(file, options = {}) {
    const maxSeconds = Number(
      options.maxDurationSeconds || DEFAULT_MAX_SECONDS
    );

    const info = await inspect(file);

    if (
      !Number.isFinite(info.duration)
      || info.duration <= 0
      || !info.width
      || !info.height
    ) {
      throw new Error("無法在本機確認影片長度或解析度");
    }

    if (info.duration <= maxSeconds + 0.05) {
      console.log(
        "[VIDEO_PREPROCESS] PASS:",
        `${info.duration.toFixed(2)}s <= ${maxSeconds}s`,
        "trim not required"
      );
      return file;
    }

    console.log(
      "[VIDEO_PREPROCESS] TRIM REQUIRED:",
      `${info.duration.toFixed(2)}s > ${maxSeconds}s`
    );

    const trimmedFile =
      await selectSegment(
        file,
        {
          maxDurationSeconds: maxSeconds,
          info
        }
      );

    if (trimmedFile) {
      console.log(
        "[VIDEO_PREPROCESS] trim complete:",
        trimmedFile.name,
        `${(trimmedFile.size / 1024 / 1024).toFixed(2)} MB`,
        trimmedFile.type
      );
    } else {
      console.log(
        "[VIDEO_PREPROCESS] trim cancelled"
      );
    }

    return trimmedFile;
  }

  window.AI_MOTION_VIDEO_PREPROCESS = {
    inspect,
    prepare,
    selectSegment
  };
})();
