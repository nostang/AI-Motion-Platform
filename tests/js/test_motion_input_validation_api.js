"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

test("polling exposes the friendly retryable input-validation failure", async () => {
  global.window = {
    AI_MOTION_CONFIG: {
      API_BASE_URL: "http://localhost/api/v1",
      POLL_TIMEOUT_MS: 1000,
      POLL_INTERVAL_MS: 1
    }
  };
  global.fetch = async () => ({
    ok: true,
    headers: { get: () => "application/json" },
    json: async () => ({
      success: true,
      data: {
        status: "failed",
        failure: {
          code: "INPUT_VALIDATION_FAILED",
          message: "目前沒有偵測到足夠明顯的可分析動作，請確認影片內容。",
          retryable: true
        }
      }
    })
  });

  require("../../frontend/js/api.js");

  await assert.rejects(
    window.AIMotionAPI.pollAssessment("ma_validation"),
    (error) => {
      assert.equal(error.code, "INPUT_VALIDATION_FAILED");
      assert.equal(error.retryable, true);
      assert.match(error.message, /足夠明顯的可分析動作/);
      return true;
    }
  );
});
