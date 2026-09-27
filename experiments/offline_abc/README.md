# A/B/C 選型實驗

本目錄用可重跑的實驗回答兩組問題：為什麼解說層現階段選擇 **A：雲端 MediaPipe + 雲端 LLM**；以及視覺層加入 YOLO 是否比 MediaPipe 單獨使用更有證據。

三個方案的固定定義：

- **A**：在雲端執行 MediaPipe 與既有規則評分，再由雲端 LLM 產生文字解說。
- **B**：在地端執行 MediaPipe、規則評分與 Ollama `gemma4:e2b`。
- **C**：保留 MediaPipe，再加 YOLO 處理球拍、羽球與落點等物件任務；不是取代 A/B 或既有分數。

## 先看這些

- [完整實驗報告](EXPERIMENT_REPORT.zh-TW.md)
- [A 的雲端 LLM 隔離實驗](A_CLOUD_LLM_BENCHMARK.zh-TW.md)
- [A vs B 同條件 28 案例結論](AB_CLOUD_LOCAL_COMPARISON.zh-TW.md)
- [B 的設備、並行與 VM 專章](B_EQUIPMENT_AND_VM.zh-TW.md)
- [B 的非中國地端模型候選](B_LOCAL_MODEL_CANDIDATES.zh-TW.md)
- [A vs B 共用 28 案例測試集](AB_BENCHMARK_CORPUS.zh-TW.md)
- [C 的羽球訓練研究計畫](C_RESEARCH_PLAN.zh-TW.md)
- [MediaPipe vs MediaPipe＋YOLO11n／YOLO12n／YOLO26n](C_MP_YOLO_COMPARISON.zh-TW.md)
- [YOLO26 n／s／m 地端成本與效果比較](C_YOLO26_SCALE_COMPARISON.zh-TW.md)
- [YOLO26n 小型羽球拍微調實驗](C_YOLO26N_FINETUNE_PILOT.zh-TW.md)
- [從零開始的口頭報告稿](PRESENTATION_SCRIPT.zh-TW.md)
- [實驗日誌](EXPERIMENT_LOG.zh-TW.md)
- [原始結果](results/)
- [證據圖片](assets/)

## 證據規則

- **實測**：真的在這台 PoC 電腦執行並留下 JSON。
- **估算**：用實測輸入與官方單價計算，不冒充雲端實測。
- **尚未測得**：尚未執行或沒有可信紀錄；目前主要是完整影片上傳、Cloud Run、正式帳單與人工盲評。

Gemma 只負責文字解說，不替換或修改版本化評分。YOLO 是離線視覺增強研究，不參與目前正式評分。所有大型資料集、模型、虛擬環境、來源影片影格與訓練產物都留在 Git 忽略目錄；小型 JSON 摘要、可重跑程式與不含原始人物的證據圖保留版本。

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

# 9. 歷史：YOLOv12 作者實作的最小流程驗證（先依日誌建立隔離環境）
experiments/offline_abc/.venv-yolo/bin/python \
  experiments/offline_abc/benchmark_yolov12.py \
  --repo experiments/offline_abc/yolov12 \
  --workspace experiments/offline_abc/results/yolo_workspace \
  --epochs 1 --device mps --inference-repeats 5 \
  --output experiments/offline_abc/results/yolov12_tiny_feasibility.json

# 10. 第二組：建立 6 段真實影片、72 張影格的 MediaPipe corpus
MPLCONFIGDIR=/tmp/ai-motion-mp-yolo-mpl .venv/bin/python \
  experiments/offline_abc/build_mp_yolo_hand_corpus.py \
  --corpus-manifest experiments/offline_abc/results/ab_corpus_manifest.json \
  --assessments-root api_data/motion_assessments \
  --frame-root experiments/offline_abc/results/yolo_compare_workspace/frames \
  --output experiments/offline_abc/results/mp_yolo_hand_corpus.json

# 11. 第二組：同條件比較 YOLO11n、YOLO12n 與 YOLO26n
# 需先在隔離環境安裝 Ultralytics 8.4.163，並放入官方 yolo11n.pt / yolo26n.pt。
PYTHONPATH=experiments/offline_abc/results/yolo_compare_runtime \
  experiments/offline_abc/.venv-yolo/bin/python \
  experiments/offline_abc/benchmark_mp_yolo_hand.py \
  --corpus experiments/offline_abc/results/mp_yolo_hand_corpus.json \
  --model YOLO11n experiments/offline_abc/results/yolo_compare_workspace/weights/yolo11n.pt \
  --model YOLO12n experiments/offline_abc/results/yolo_compare_workspace/weights/yolo12n.pt \
  --model YOLO26n experiments/offline_abc/results/yolo_compare_workspace/weights/yolo26n.pt \
  --device mps --image-size 1280 --confidence 0.15 \
  --evidence-dir experiments/offline_abc/results/yolo_compare_workspace/evidence \
  --output experiments/offline_abc/results/mp_yolo11_yolo12_yolo26_hand_comparison.json

# 11b. 第二組深入：YOLO26 n / s / m 各用獨立程序跑三輪
# 九次 benchmark 的參數與 11 相同，每次只帶一個 --model；逐輪 JSON 留在
# results/yolo_scale_workspace/runs/。最後彙整成可供儀表板讀取的固定格式：
.venv/bin/python experiments/offline_abc/summarize_yolo26_scale_runs.py \
  --run experiments/offline_abc/results/yolo_scale_workspace/runs/YOLO26n_run1.json \
  --run experiments/offline_abc/results/yolo_scale_workspace/runs/YOLO26n_run2.json \
  --run experiments/offline_abc/results/yolo_scale_workspace/runs/YOLO26n_run3.json \
  --run experiments/offline_abc/results/yolo_scale_workspace/runs/YOLO26s_run1.json \
  --run experiments/offline_abc/results/yolo_scale_workspace/runs/YOLO26s_run2.json \
  --run experiments/offline_abc/results/yolo_scale_workspace/runs/YOLO26s_run3.json \
  --run experiments/offline_abc/results/yolo_scale_workspace/runs/YOLO26m_run1.json \
  --run experiments/offline_abc/results/yolo_scale_workspace/runs/YOLO26m_run2.json \
  --run experiments/offline_abc/results/yolo_scale_workspace/runs/YOLO26m_run3.json \
  --output experiments/offline_abc/results/yolo26_n_s_m_comparison.json

# 11c. 建立嚴格的 AI 輔助球拍預標註資料（不是人工 ground truth）
experiments/offline_abc/.venv-yolo/bin/python \
  experiments/offline_abc/build_yolo_racket_pilot_dataset.py \
  --corpus experiments/offline_abc/results/mp_yolo_hand_corpus.json \
  --teacher-s experiments/offline_abc/results/yolo_scale_workspace/runs/YOLO26s_run1.json \
  --teacher-m experiments/offline_abc/results/yolo_scale_workspace/runs/YOLO26m_run1.json \
  --workspace experiments/offline_abc/results/yolo_racket_pilot_workspace \
  --minimum-iou 0.65 --minimum-confidence 0.4

# 11d. YOLO26n：5 epochs 短測＋40 epochs 正式微調＋保留影片測試
PYTHONPATH=experiments/offline_abc/results/yolo_compare_runtime \
  experiments/offline_abc/.venv-yolo/bin/python \
  experiments/offline_abc/train_yolo26n_racket_pilot.py \
  --dataset-yaml experiments/offline_abc/results/yolo_racket_pilot_workspace/dataset.yaml \
  --manifest experiments/offline_abc/results/yolo_racket_pilot_workspace/manifest.json \
  --base-weights experiments/offline_abc/results/yolo_compare_workspace/weights/yolo26n.pt \
  --workspace experiments/offline_abc/results/yolo_racket_pilot_workspace \
  --output experiments/offline_abc/results/yolo26n_racket_finetune_pilot.json \
  --device mps --image-size 640 --batch 8 --smoke-epochs 5 --epochs 40

# 12. A：只做成本情境估算，不呼叫雲端
.venv/bin/python experiments/offline_abc/estimate_option_a.py \
  --mediapipe experiments/offline_abc/results/mediapipe_serve_baseline.json \
  --gemma experiments/offline_abc/results/gemma4_three_cases.json \
  --monthly-analyses 10000 \
  --output experiments/offline_abc/results/option_a_cost_estimate.json

# 13. A：零網路乾跑；預設不會呼叫 API
.venv/bin/python experiments/offline_abc/benchmark_gemini_corpus.py \
  --manifest experiments/offline_abc/results/ab_corpus_manifest.json \
  --output experiments/offline_abc/results/gemini_35_flash_lite_28_case_preflight.json

# 14. A：隔離專案的正式 28 案例（需要獨立測試金鑰；4.5 秒間隔遵守 15 RPM）
.venv/bin/python experiments/offline_abc/benchmark_gemini_corpus.py \
  --manifest experiments/offline_abc/results/ab_corpus_manifest.json \
  --compact-profile minimal --prompt-version v3 \
  --minimum-request-interval-seconds 4.5 --execute \
  --output experiments/offline_abc/results/gemini_35_flash_lite_28_case_minimal_v3.json

# 15. B：用與 A 完全相同的最小輸入與 v3 提示詞
.venv/bin/python experiments/offline_abc/benchmark_gemma4.py \
  --manifest experiments/offline_abc/results/ab_corpus_manifest.json \
  --compact-profile minimal --prompt-version v3 \
  --structured-output schema --repeats 1 \
  --output experiments/offline_abc/results/gemma4_28_case_schema_v3.json

# 16. 分別跑十項自動檢查（A、B 各跑一次）
.venv/bin/python experiments/offline_abc/evaluate_llm_corpus.py \
  --input experiments/offline_abc/results/gemini_35_flash_lite_28_case_minimal_v3.json \
  --output experiments/offline_abc/results/gemini_35_flash_lite_28_case_minimal_v3_quality.json \
  --review-csv experiments/offline_abc/results/gemini_35_flash_lite_28_case_minimal_v3_review.csv

# 17. B：套用確定性正規化、同一套十項檢查與固定模板 fallback
.venv/bin/python experiments/offline_abc/apply_local_llm_guardrails.py \
  --input experiments/offline_abc/results/gemma4_28_case_schema_v3.json \
  --output experiments/offline_abc/results/gemma4_28_case_schema_guarded_v3.json

# 18. 建立隱藏提供者的 56 列人工盲評表（A vs B1 原始模型輸出）
.venv/bin/python experiments/offline_abc/build_blind_ab_review.py \
  --a-run experiments/offline_abc/results/gemini_35_flash_lite_28_case_minimal_v3.json \
  --b-run experiments/offline_abc/results/gemma4_28_case_schema_v3.json \
  --review-csv experiments/offline_abc/results/ab_schema_28_case_blind_human_review.csv \
  --mapping-json experiments/offline_abc/results/ab_schema_28_case_blind_mapping.json

# 19. 重新產生所有證據圖
MPLCONFIGDIR=/tmp/ai-motion-mpl .venv/bin/python \
  experiments/offline_abc/render_evidence.py

# 20. 產生小型微調公開統計圖（不含原始人物畫面）
MPLCONFIGDIR=/tmp/ai-motion-mpl experiments/offline_abc/.venv-yolo/bin/python \
  experiments/offline_abc/render_yolo_racket_pilot_evidence.py \
  --summary experiments/offline_abc/results/yolo26n_racket_finetune_pilot.json \
  --summary-output experiments/offline_abc/assets/yolo26n_racket_finetune_pilot.png
```

## 安全邊界

本實驗沒有建立 VM、沒有部署 Cloud Run，也沒有使用正式 Cloud SQL、bucket、queue、secret、流量或自訂 IAM。唯一雲端動作是使用獨立 Free tier 測試專案呼叫 Gemini API；Google AI Studio 為 key 自動綁定同名服務帳戶。實驗完成後 API key 已刪除並確認清單為空，服務帳戶仍留待另行確認是否移除。全程沒有使用或接觸羽球＋1正式資源。工具預設為零網路 dry-run，只有 `--execute` 加上獨立 `GEMINI_API_KEY` 才會呼叫 Gemini。PoC 的隔離保護仍由 `src/poc_isolation.py` 與 `tests/test_poc_resource_isolation.py` 驗證。
