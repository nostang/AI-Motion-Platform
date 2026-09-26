# A/B/C 選型實驗

本目錄用可重跑的本機實驗回答：為什麼 PoC 現階段選擇 **A：雲端 MediaPipe + 雲端 LLM**，而不是 B 或 C。

三個方案的固定定義：

- **A**：在雲端執行 MediaPipe 與既有規則評分，再由雲端 LLM 產生文字解說。
- **B**：在地端執行 MediaPipe、規則評分與 Ollama `gemma4:e2b`。
- **C**：自行蒐集、標註資料並訓練 YOLOv12（或更新版本）處理羽球專用視覺任務。

## 先看這些

- [完整實驗報告](EXPERIMENT_REPORT.zh-TW.md)
- [A 的雲端 LLM 隔離實驗](A_CLOUD_LLM_BENCHMARK.zh-TW.md)
- [B 的設備、並行與 VM 專章](B_EQUIPMENT_AND_VM.zh-TW.md)
- [A vs B 共用 28 案例測試集](AB_BENCHMARK_CORPUS.zh-TW.md)
- [C 的羽球訓練研究計畫](C_RESEARCH_PLAN.zh-TW.md)
- [從零開始的口頭報告稿](PRESENTATION_SCRIPT.zh-TW.md)
- [實驗日誌](EXPERIMENT_LOG.zh-TW.md)
- [原始結果](results/)
- [證據圖片](assets/)

## 證據規則

- **實測**：真的在這台 PoC 電腦執行並留下 JSON。
- **估算**：用實測輸入與官方單價計算，不冒充雲端實測。
- **尚未測得**：本輪受限於「不得建立或呼叫雲端資源」而沒有執行。

Gemma 只負責文字解說，不替換或修改版本化評分。YOLOv12 是離線研究，不參與目前正式評分。所有大型資料集、模型、虛擬環境與訓練產物都留在 Git 忽略目錄；小型 JSON 摘要與證據圖保留版本。

## 重跑順序

以下命令只操作本機 PoC。`scripts/offline_demo_server.py` 是使用者未追蹤檔，不在本實驗範圍。

```bash
# 1. MediaPipe 基準（換成自己的本機影片也可以）
.venv/bin/python experiments/offline_abc/benchmark_mediapipe.py \
  --motion serve \
  --case-id ma_120f8334b8094f5f \
  --video api_data/motion_assessments/ma_120f8334b8094f5f/source.mov \
  --repeats 3 \
  --output experiments/offline_abc/results/mediapipe_serve_baseline.json

# 2. B：本機 Gemma 4，三種輸入各兩次
.venv/bin/python experiments/offline_abc/benchmark_gemma4.py \
  --report docs/calibration/system_results/SV_001_window_v0_4/serve_analysis_report.json \
  --report docs/calibration/system_results/SV_003_window_v0_4/serve_analysis_report.json \
  --report docs/calibration/system_results/FW_002_boundary_fix/footwork_analysis_report.json \
  --repeats 2 \
  --output experiments/offline_abc/results/gemma4_three_cases.json

# 3. B：CPU-only 對照
.venv/bin/python experiments/offline_abc/benchmark_gemma4.py \
  --report docs/calibration/system_results/SV_001_window_v0_4/serve_analysis_report.json \
  --report docs/calibration/system_results/SV_003_window_v0_4/serve_analysis_report.json \
  --report docs/calibration/system_results/FW_002_boundary_fix/footwork_analysis_report.json \
  --num-gpu 0 --repeats 1 \
  --output experiments/offline_abc/results/gemma4_cpu_only.json

# 4. B：模型暖機後，測 1 個與 2 個同時請求
.venv/bin/python experiments/offline_abc/benchmark_gemma_concurrency.py \
  --report docs/calibration/system_results/SV_001_window_v0_4/serve_analysis_report.json \
  --concurrency 1 --concurrency 2 --batches 2 \
  --output experiments/offline_abc/results/gemma4_concurrency.json

# 5. 建立 A/B 共用測試集：19 份真實影片流程輸出 + 9 份模擬壓力 JSON
MPLCONFIGDIR=/tmp/ai-motion-mpl .venv/bin/python \
  experiments/offline_abc/build_ab_benchmark_corpus.py

# 6. B：對共用 28 案例各跑一次
.venv/bin/python experiments/offline_abc/benchmark_gemma4.py \
  --manifest experiments/offline_abc/results/ab_corpus_manifest.json \
  --repeats 1 \
  --output experiments/offline_abc/results/gemma4_28_case_corpus.json

# 7. 建立自動檢查與待人工填寫的評分表
.venv/bin/python experiments/offline_abc/evaluate_llm_corpus.py \
  --input experiments/offline_abc/results/gemma4_28_case_corpus.json \
  --output experiments/offline_abc/results/gemma4_28_case_quality.json \
  --review-csv experiments/offline_abc/results/gemma4_28_case_human_review.csv

# 8. B：暖機後測 1、2、4 個同時請求，各五批
.venv/bin/python experiments/offline_abc/benchmark_gemma_concurrency.py \
  --report experiments/offline_abc/corpus/real/R-CLR-01/analysis_report.json \
  --concurrency 1 --concurrency 2 --concurrency 4 --batches 5 \
  --output experiments/offline_abc/results/gemma4_concurrency_1_2_4.json

# 9. C：官方 YOLOv12 的最小流程驗證（先依日誌建立隔離環境）
experiments/offline_abc/.venv-yolo/bin/python \
  experiments/offline_abc/benchmark_yolov12.py \
  --repo experiments/offline_abc/yolov12 \
  --workspace experiments/offline_abc/results/yolo_workspace \
  --epochs 1 --device mps --inference-repeats 5 \
  --output experiments/offline_abc/results/yolov12_tiny_feasibility.json

# 10. A：只做成本情境估算，不呼叫雲端
.venv/bin/python experiments/offline_abc/estimate_option_a.py \
  --mediapipe experiments/offline_abc/results/mediapipe_serve_baseline.json \
  --gemma experiments/offline_abc/results/gemma4_three_cases.json \
  --monthly-analyses 10000 \
  --output experiments/offline_abc/results/option_a_cost_estimate.json

# 11. A：零網路乾跑；預設不會呼叫 API
.venv/bin/python experiments/offline_abc/benchmark_gemini_corpus.py \
  --manifest experiments/offline_abc/results/ab_corpus_manifest.json \
  --output experiments/offline_abc/results/gemini_35_flash_lite_28_case_preflight.json

# 12. 重新產生所有證據圖
MPLCONFIGDIR=/tmp/ai-motion-mpl .venv/bin/python \
  experiments/offline_abc/render_evidence.py
```

## 安全邊界

本實驗沒有建立 VM、沒有部署 Cloud Run、沒有呼叫正式 API，也沒有使用正式 Cloud SQL、bucket、queue、secret、service account、流量或 IAM。A 的新工具預設為零網路 dry-run，只有 `--execute` 加上獨立 `GEMINI_API_KEY` 才會呼叫 Gemini。PoC 的隔離保護仍由 `src/poc_isolation.py` 與 `tests/test_poc_resource_isolation.py` 驗證。
