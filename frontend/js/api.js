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
      const detail = body && typeof body === "object" ? body.detail || body.message : body;
      throw new Error(detail || `API request failed (${response.status})`);
    }
    return body;
  }

  async function createAssessment(videoFile, assessmentType) {
    const formData = new FormData();
    formData.append("video", videoFile, videoFile.name);
    formData.append("user_id", "1");
    formData.append("assessment_type", assessmentType);
    return request("/motion-assessments", { method: "POST", body: formData });
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

  window.AIMotionAPI = Object.freeze({
    createAssessment,
    getAssessment,
    pollAssessment,
    extractAssessmentId,
    normalizeStatus
  });
  window.motionAPI = Object.freeze({ getReport });
})();
