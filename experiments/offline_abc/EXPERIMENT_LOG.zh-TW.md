# A/B/C 實驗日誌

日期：2026-09-26

工作目錄：`/Users/ivesmi/Documents/AI_Motion_PoC`

限制：全程本機；不得建立/啟動 VM、不得部署 Cloud Run、不得接觸羽球＋1正式 API 或正式雲端資源。

## 0. 起始狀態與保護

### 想證明什麼

確保工作發生在獨立 PoC，並且不覆蓋使用者檔案。

### 實際步驟

- 核對分支、HEAD、Git 狀態與既有實驗目錄。
- 確認分支為 `codex/sync-ability-motion-20260926`。
- 確認 HEAD 為 `f1466b144c68153546a1f6b4bed5075934d8c1f3`。
- 發現唯一未追蹤使用者檔 `scripts/offline_demo_server.py`，全程不讀改、不 stage、不 commit。
- 檢查 `src/poc_isolation.py` 與 `tests/test_poc_resource_isolation.py`。

### 結果

起始狀態與交接相符，實驗可以在獨立 PoC 內繼續。

### 心得

選型實驗如果污染正式資源或把使用者檔案一起提交，後面的數字再漂亮也不可信。因此先建立可稽核邊界，比先跑模型更重要。

## 1. 釐清 A/B/C 定義

### 想證明什麼

避免把三個方案比較錯對象。

### 實際定義

- A：雲端 MediaPipe + 雲端 LLM。
- B：地端 MediaPipe + 地端 Gemma 4。
- C：自行訓練 YOLOv12（或更新版本）。

### 結果

確認 A/B 的共同核心是 MediaPipe + 規則分數；LLM 只解說。C 是新的物件感知研究，不自然等於既有動作分數。

### 心得

最大的認知風險是把「雲端/地端部署位置」與「MediaPipe/YOLO 視覺能力」混成一題。拆開後才知道 A 與 B 在比較部署，C 在比較是否值得自行養一套新感知能力。

## 2. MediaPipe 共同基準

### 想證明什麼

既有評分核心是否穩定，以及 A/B 能否直接沿用。

### 實際步驟

- 使用本機 PoC 影片 `ma_120f8334b8094f5f/source.mov`。
- 動作類型 `serve`，重跑 3 次。
- 紀錄影片規格、牆鐘時間、CPU 時間、峰值 RSS、分數與信心。

### 遇到的問題

第一次在受限沙箱執行時，MediaPipe 無法建立 macOS Metal 圖形服務而 abort。確認是本機圖形服務權限後，在允許本機硬體的環境以相同程式與資料重跑；沒有改程式結果，也沒有接觸外部資源。

### 結果

- 影片 16.217 秒、683 frames。
- 三次平均 5.3651 秒，127.303 FPS。
- 峰值 RSS 368.94 MB。
- 三次分數全部 87，信心全部 1.0。

### 畫面

![既有動作報告畫面](../../docs/assets/screenshots/motion-report.jpg)

### 心得

這組結果支持「不要重新發明分數」。LLM 與 YOLO 都應被放在既有核心之外：LLM 翻譯結果，YOLO 補足看不到的球拍/羽球。

### 證據

[`results/mediapipe_serve_baseline.json`](results/mediapipe_serve_baseline.json)

## 3. A 的雲端整合與成本情境

### 想證明什麼

在不建立雲端資源的限制下，建立可計算、可補驗的 A 架構與成本模型。

### 實際步驟

- 把本機 MediaPipe 實測作為雲端服務的工作量 proxy。
- 把 B 的實際平均 input/output tokens 作為雲端 LLM token proxy。
- 使用 2026-09-26 官方 Gemini 2.5 Flash-Lite 與 Cloud Run 公開單價。
- 以 10,000 次/月產生可重跑估算。

### 結果

- LLM 情境約 US$0.00012117/次。
- CPU/RAM 情境約 US$0.00010044/次。
- 合計約 US$0.00022160/次、10,000 次約 US$2.216。

### 畫面

![A 流程、實測與估算](assets/a_pipeline_evidence.png)

### 心得

US$2.216 不是正式預算。它的價值是把公式攤開，讓下一輪替換成真正 Cloud Run 時間、實際 tokens、Storage 和 DB 成本。誠實留下「雲端待測」比給一個看似精準的假帳單更重要。

### 證據

[`results/option_a_cost_estimate.json`](results/option_a_cost_estimate.json)

## 4. B：Gemma 4 模型完整性與三種輸入

### 想證明什麼

確認模型已下載，並測試本機 LLM 能否穩定把不同動作報告變成結構化繁中解說。

### 實際步驟

- 用 macOS 系統資訊確認測試機為 MacBook Pro（Apple M5 Pro、24 GB、macOS 26.5.2）。
- 檢查 Ollama manifest 與 blob，確認 `gemma4:e2b` model layer 為 7,162,394,016 bytes。
- 選 `SV_001`、`SV_003` 與一筆 footwork 報告。
- 冷啟動 GPU 模式，每筆各跑 2 次，共 6 筆。
- 檢查 JSON、必要欄位、priority grounding、caution。
- 從 Ollama `/api/ps` 讀取 resident size 與量化格式。

### 先發現的腳本問題

既有腳本用 `report_path.parent.parent.name` 當 case id，三筆都會被標成 `system_results`。已改為優先讀 `video_id`、其次 `assessment_id`，所以結果能分辨 `SV_001`、`SV_003` 與 footwork assessment。

### 結果

- 冷啟動首筆 5.3886 秒；暖機後平均 1.9091 秒。
- 平均 108.469 tokens/s。
- 6/6 成功、JSON/必要欄位/grounding/caution 全 100%。
- Q4_K_M，resident 7.004 GB，100% Apple GPU。

### 畫面

![B GPU/CPU/記憶體圖](assets/b_equipment_benchmark.png)

![B 實際 JSON 輸出](assets/b_output_screen.png)

### 心得

B 的功能不是假設，已經跑通。但 100% 只代表這 6 筆格式與基本 grounding 通過，不能擴大解讀為所有教練內容都正確，也不能說 Gemma 看過影片。

### 證據

[`results/gemma4_three_cases.json`](results/gemma4_three_cases.json)

## 5. B：CPU-only 對照

### 想證明什麼

回答「沒有 GPU 能不能做」與 GPU 的實際價值。

### 實際步驟

- 先卸載 GPU 模型。
- 以 Ollama `num_gpu=0` 跑相同三筆輸入。
- 保留成功率、延遲、tokens/s 與 resident size。

### 結果

- CPU-only 3/3 成功，所有格式檢查 100%。
- 冷啟動 7.2578 秒；暖機後平均 3.8094 秒。
- 平均 80.499 tokens/s；resident 6.733 GB。
- GPU 暖機後等待約為 CPU 的一半。

### 心得

GPU 不是可行性的必要條件，但對互動等待很有價值。由於兩種模式輸出 token 數不完全相同，不能把所有差異都歸因於硬體；因此同時報告端到端秒數與 tokens/s。

### 證據

[`results/gemma4_cpu_only.json`](results/gemma4_cpu_only.json)

## 6. B：1 個與 2 個同時請求

### 想證明什麼

單人速度好看，不代表多人能用；要觀察延遲與總吞吐。

### 實際步驟

- 先 warm up GPU 模型，排除載入時間。
- concurrency 1 跑 2 批；concurrency 2 跑 2 批。
- 每筆驗證 JSON 成功，紀錄 batch wall time、每筆 latency 與 requests/s。

### 結果

- 1 個同時請求：1.9347 秒/筆、0.5168 requests/s。
- 2 個同時請求：2.9006 秒/筆、0.5154 requests/s。
- 6/6 成功，但總吞吐沒有增加。

### 畫面

![B 並行與 VM 價格情境](assets/b_concurrency_vm.png)

### 心得

這台機器的單一 runner 主要讓請求排隊。B 要多人使用時，真正問題不是「模型能不能回答」，而是要不要增加 runner、GPU 記憶體與排隊系統。這會直接增加維運成本。

### 證據

[`results/gemma4_concurrency.json`](results/gemma4_concurrency.json)

## 7. B：設備與 VM 判斷

### 想證明什麼

把模型大小、實測延遲與並行結果轉成可使用的設備決策。

### 結果

- 8 GB：不建議，7 GB 模型幾乎吃滿空間。
- 16 GB：最低建議，單人一次一筆；尚未在 16 GB 實機測。
- 24 GB：本次已驗證，適合 PoC 與單人展示。
- 32 GB+：有更多開發餘裕，但 RAM 增加不會自動讓單 runner 並行。
- CPU VM 4 vCPU / 16 GiB 公開價情境約 US$141.79/月（730 小時）。
- L4 GPU VM 公開價情境約 US$515.99/月（730 小時）。

### 心得

單人 PoC 不需要租 VM。若為多人而租 VM，B 就從「地端模型」變成「團隊自己維運的雲端模型」，必須重新和 A 的託管 LLM 比成本、更新、可靠性與資料政策。

### 證據

[B 的設備、並行與 VM 專章](B_EQUIPMENT_AND_VM.zh-TW.md)

## 8. C：官方 YOLOv12 最小流程

### 想證明什麼

只驗證官方程式在本機能走完訓練與推論，不聲稱羽球準確度。

### 實際步驟

- 官方來源固定在 `2abab7153a065fb2925e8088e9ca2b19016ab7d6`。
- 建立隔離 Python 3.11 環境。
- 產生 12 train / 4 validation、單類別、160×160 合成方塊資料。
- YOLOv12n、batch 4、MPS、1 epoch。

### 遇到的問題

- 官方 `requirements.txt` 含 Linux/CUDA FlashAttention wheel，不適用 Apple Silicon；官方程式已有 PyTorch fallback。
- 官方 `pyproject.toml` 漏列啟動必需的 `huggingface-hub`，首次匯入失敗；補上官方 requirements 已列套件後重跑。
- 補依賴時 resolver 曾把 NumPy 升到 2.x，依官方 macOS 上限固定回 1.26.4。

### 結果

- 訓練 26.9749 秒、峰值 RSS 952.28 MB、模型 5.38 MB。
- 暖機後推論平均 5.915 ms。
- mAP、precision、recall 全為 0，五次都沒有預測框。

### 畫面

![C 合成資料與研究路線](assets/c_feasibility_research.png)

![C 訓練結果重建畫面](assets/c_training_result_screen.png)

第二張圖是依實際 console log、`results.csv` 與 JSON 重建的證據畫面，不是即時螢幕截圖。

### 心得

這個零分結果很有價值：它阻止我們把「產生 best.pt」誤寫成「模型已學會」。真正的持拍手、球路與落點仍需要人工確認的真實資料；在沒有可靠框/點標註前，不應硬做假羽球訓練。

### 證據

[`results/yolov12_tiny_feasibility.json`](results/yolov12_tiny_feasibility.json) 與 [C 研究計畫](C_RESEARCH_PLAN.zh-TW.md)

## 9. 視覺證據製作

### 想證明什麼

讓每個結論能用畫面說明，不必只讀終端輸出。

### 實際步驟

- 由版本化 JSON 自動繪製 A 流程、B 設備、B 並行/VM、C 流程與選型矩陣。
- B 輸出畫面直接取自實際 response JSON。
- C 訓練畫面明確標示為依原始 log/CSV/JSON 重建。

### 心得

圖表只負責縮短理解距離，原始 JSON 才是數字真相。因此每張圖都附來源檔，並讓 `render_evidence.py` 可重建。

## 10. 驗證與提交

### 實際步驟

- 重新執行 `render_evidence.py`，確認所有證據圖可由版本化 JSON 重建。
- 對五支實驗程式做 Python 語法檢查。
- 對所有結果 JSON 做格式驗證。
- 執行 PoC 測試目錄與兩支前端 Node 測試。
- 執行 `git diff --check`，確認沒有空白或 patch 格式錯誤。
- 再次確認未追蹤的使用者檔 `scripts/offline_demo_server.py` 沒有納入實驗提交。

### 遇到的問題

直接從 repository 根目錄執行未限定路徑的 `pytest` 時，pytest 也走進本機、Git 已忽略的官方 YOLOv12 clone，並因主 PoC 環境沒有安裝該隔離環境的 PyTorch 而在收集階段停止。這不是 PoC 測試失敗；YOLOv12 本來就刻意使用獨立 `.venv-yolo`。因此完整 PoC 驗證明確指定 `tests/`，避免把外部研究 clone 的上游測試混入產品測試。

### 結果

- PoC Python：238 passed、2 skipped。
- 前端 Node：5 passed、0 failed。
- 本實驗與隔離保護的重點測試：10 passed。
- 五支實驗程式語法檢查通過。
- 七份正式 JSON（含保留但忽略的早期中間檔）皆為有效 JSON；提交只保留六份正式結果，不納入 `*_initial.json`。
- `git diff --check` 通過。

### 心得

把 YOLOv12 放在隔離環境是正確的：C 的研究相依套件不應污染 A/B 的 PoC 環境。B 的證據也因此能獨立重跑；它只需要既有 PoC Python、Ollama 與本機 Gemma 模型。最後結論不依賴一次性的終端畫面，而是由 JSON、測試、圖片生成程式與逐步日誌共同支撐。
