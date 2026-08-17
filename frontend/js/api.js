(function () {
  "use strict";

  const config = window.AI_MOTION_CONFIG;
  if (!config) throw new Error("AI_MOTION_CONFIG 尚未載入");

  async function request(path, options) {
    const response = await fetch(`${config.API_BASE_URL}${path}`, options);
    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json")
      ? await response.json()
      : await response.text();

    if (!response.ok) {
      const detail =
        body && typeof body === "object"
          ? (
              body.error?.message
              || body.detail
              || body.message
            )
          : body;

      throw new Error(
        detail
        || `API request failed (${response.status})`
      );
    }
    return body;
  }

  async function createAssessment(
    videoFile,
    assessmentType,
    options = {}
  ) {
    const formData = new FormData();
    formData.append("video", videoFile, videoFile.name);
    formData.append("user_id", "1");
    formData.append("assessment_type", assessmentType);
    formData.append(
      "defer_analysis",
      options.deferAnalysis ? "true" : "false"
    );
    return request(
      "/motion-assessments",
      {
        method: "POST",
        body: formData
      }
    );
  }


  async function createUploadTicket(videoFile) {
    const rawType = videoFile.type || "";

    const contentType =
      rawType.startsWith("video/mp4")
        ? "video/mp4"
        : rawType.startsWith("video/quicktime")
          ? "video/quicktime"
          : (
              videoFile.name.toLowerCase().endsWith(".mov")
                ? "video/quicktime"
                : "video/mp4"
            );

    console.log(
      "[UPLOAD_MIME]",
      {
        filename: videoFile.name,
        rawType,
        normalizedType: contentType
      }
    );

    return request(
      "/video-upload-urls",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          filename: videoFile.name,
          content_type: contentType
        })
      }
    );
  }

  function uploadToSignedUrl(
    videoFile,
    uploadUrl,
    contentType,
    onProgress
  ) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      xhr.open("PUT", uploadUrl);
      xhr.setRequestHeader(
        "Content-Type",
        contentType
      );

      xhr.upload.addEventListener(
        "progress",
        (event) => {
          if (!event.lengthComputable) return;
          const percent = Math.round(
            (event.loaded / event.total) * 100
          );
          onProgress?.(percent);
        }
      );

      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          onProgress?.(100);
          resolve();
          return;
        }

        reject(
          new Error(
            `Cloud Storage 上傳失敗 (${xhr.status})`
          )
        );
      });

      xhr.addEventListener("error", () => {
        reject(
          new Error("Cloud Storage 上傳連線失敗")
        );
      });

      xhr.send(videoFile);
    });
  }

  async function createAssessmentFromStorage(
    videoFile,
    assessmentType,
    onUploadProgress
  ) {
    const ticket = await createUploadTicket(videoFile);

    if (!ticket?.upload_url || !ticket?.object_name) {
      throw new Error("API 未回傳 Storage upload ticket");
    }

    await uploadToSignedUrl(
      videoFile,
      ticket.upload_url,
      ticket.content_type,
      onUploadProgress
    );

    return request(
      "/motion-assessments/from-storage",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          object_name: ticket.object_name,
          assessment_type: assessmentType,
          user_id: 1
        })
      }
    );
  }

  function analyzeAnnotation(assessmentId) {
    return request(
      `/motion-assessments/${
        encodeURIComponent(assessmentId)
      }/analyze-annotation`,
      { method: "POST" }
    );
  }

  function getAssessment(assessmentId) {
    return request(`/motion-assessments/${encodeURIComponent(assessmentId)}`);
  }

  function extractAssessmentId(payload) {
    return payload?.assessment_id ?? payload?.id ?? payload?.data?.assessment_id ?? null;
  }

  function normalizeStatus(payload) {
    return String(payload?.status ?? payload?.assessment_status ?? payload?.data?.status ?? "").toUpperCase();
  }

  function isComplete(payload) {
    return ["COMPLETED", "COMPLETE", "SUCCEEDED", "SUCCESS", "DONE"].includes(normalizeStatus(payload));
  }

  function isFailed(payload) {
    return ["FAILED", "ERROR", "REJECTED", "CANCELLED"].includes(normalizeStatus(payload));
  }

  async function pollAssessment(assessmentId, onUpdate) {
    const startedAt = Date.now();
    while (Date.now() - startedAt < config.POLL_TIMEOUT_MS) {
      const assessment = await getAssessment(assessmentId);
      onUpdate?.(assessment);
      if (isComplete(assessment)) return assessment;
      if (isFailed(assessment)) {
        throw new Error(assessment?.error_message || assessment?.message || "動作分析失敗");
      }
      await new Promise((resolve) => setTimeout(resolve, config.POLL_INTERVAL_MS));
    }
    throw new Error("分析等待逾時，請稍後以 Assessment ID 查詢結果");
  }


  async function getReport(assessmentId) {
    return request(
      `/motion-assessments/${encodeURIComponent(assessmentId)}/report`
    );
  }

  async function getEngineerDebug(assessmentId) {
    return request(
      `/internal/motion-assessments/${
        encodeURIComponent(assessmentId)
      }/engineer-debug`
    );
  }

  window.AIMotionAPI = Object.freeze({
    createAssessment,
    createAssessmentFromStorage,
    analyzeAnnotation,
    getAssessment,
    pollAssessment,
    extractAssessmentId,
    normalizeStatus
  });
  window.motionAPI = Object.freeze({
    getReport,
    getEngineerDebug
  });
})();
