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

## 11. A/B 共用素材盤點與去重

### 想證明什麼

回答現有素材能否誠實形成 20～30 份報告，並避免把同一影片的多份複製或多個版本 JSON 當成不同受測者。

### 實際步驟

- 盤點 calibration JSON、API assessment 影片與 dataset 影片。
- 對所有影片計算 SHA-256，以內容而非檔名去重。
- 將 dataset 資料夾名稱與 `human_annotation.json` 的動作類型合併。
- 以「影片 hash × 動作類型」作為真實案例單位。

### 結果

- 表面影片檔 74 個，去重後 24 段。
- 有可信動作類型的 18 段影片，可形成 19 個影片 × 動作案例。
- 真實案例分布：高遠球 10、步法 3、發球 6。
- 既有 94 個 calibration JSON 多是版本與中間產物，不能當成 94 位受測者。

### 心得

檔案數不等於樣本數。這一步讓後續報告可以誠實說「19 個真實影片流程案例」，而不是誤導成 19 位不同受測者。

## 12. 產生 19 真實 + 9 模擬案例

### 實際步驟

- `build_ab_benchmark_corpus.py` 依去重結果逐一執行現有 MediaPipe/規則流程。
- 有人工視窗時使用標註的 start/end，沒有時分析完整影片。
- 建立 9 個明確標示 `not_from_video=true` 的壓力 JSON。
- 每完成一個案例就更新 manifest，失敗也保留原因。

### 遇到的問題

第一輪高遠球 10/10 都顯示 `TypeError`。檢查後發現不是素材或輸入驗證失敗，而是新批次工具誤把 `racket_side` 傳給不接受該參數的高遠球函式。修正工具並加回歸測試後只重跑高遠球，10/10 完成；步法 3/3、發球 6/6 也完成。

### 結果

- 19/19 真實案例產生分析報告。
- 9/9 模擬壓力案例產生，且每份都標明不可算成真實影片或受測者。
- 共 28 份可供 A、B 使用的固定輸入。

### 心得

第一次看到 10 個失敗時不能立刻歸因於模型。manifest 留下了 exception，才得以確認是適配器 bug。修正工具後的結果與第一次錯誤紀錄應分開解釋，不能把工程 bug 當成高遠球能力失敗。

### 證據

[`results/ab_corpus_manifest.json`](results/ab_corpus_manifest.json) 與 [`corpus/`](corpus/)

## 13. B：28 案例輸出與品質檢查

### 實際步驟

- 先卸載 Gemma，保留第一筆冷啟動。
- 依 manifest 對 28 份輸入各跑一次。
- 分開統計真實與模擬案例的 p50/p95、JSON 與必要欄位。
- 建立九項自動檢查與待人工填寫的盲評表。

### 結果

- 28/28 有效 JSON；27/28 五個必要欄位完整。
- 全部 p50 1.9705 秒、p95 2.8806 秒。
- 真實 19 份：p50 2.0218 秒、p95 3.1906 秒、欄位完整 94.7%。
- 模擬 9 份：p50 1.3857 秒、p95 1.6554 秒、欄位完整 100%。
- 自動九項全部通過 26/28；人工內容盲評尚未完成。

### 發現的問題

- `R-CLR-02` 缺少 `strength` key；相同 v1 設定重跑三次，三次都用錯誤 key。
- v2 加入嚴格 JSON 範本後三次欄位都正確，但三次都把待改善項目寫成優點。
- `R-SV-02` 使用簡體字「无」。

### 心得

這輪把「能解析」「schema 正確」「內容有根據」「人覺得有用」拆成四個不同層級。v2 的結果特別重要：格式 guardrail 可以修結構，卻可能留下語意錯誤，因此上線前必須有 deterministic validation、fallback 與人工品質比較。

### 畫面

![B 的 28 案例擴充證據](assets/b_28_case_evidence.png)

### 證據

[`results/gemma4_28_case_corpus.json`](results/gemma4_28_case_corpus.json)、[`results/gemma4_28_case_quality.json`](results/gemma4_28_case_quality.json)、[`results/gemma4_28_case_human_review.csv`](results/gemma4_28_case_human_review.csv)

## 14. B：1、2、4 請求壓力測試

### 實際步驟

- 使用同一份真實高遠球報告，先暖機。
- concurrency 1、2、4，各跑五批。
- 共 35 個請求，記錄 p50、p95、總吞吐與成功率。

### 結果

- 1 個：p95 2.0710 秒，0.4834 requests/s。
- 2 個：p95 4.1401 秒，0.4838 requests/s。
- 4 個：p95 8.3004 秒，0.4822 requests/s。
- 35/35 成功，但吞吐幾乎固定。

### 心得

這不是四筆一起算完，而是約每 2.07 秒完成一筆。第四筆最差接近等四輪。B 若要服務多人，必須增加 runner/硬體或接受排隊；只把 RAM 加大，不會自動提高單 runner 吞吐。

### 證據

[`results/gemma4_concurrency_1_2_4.json`](results/gemma4_concurrency_1_2_4.json)

## 15. 28 案例階段驗證

### 實際步驟

- 重跑完整 PoC Python 測試與前端 Node 測試。
- 對五支本輪新增/修改的實驗程式做語法檢查。
- 驗證 results 與 corpus 的 JSON 格式。
- 驗證 corpus 恰有 28 份 report、人工評分 CSV 恰有 28 列。
- 重新產生並目視檢查 `b_28_case_evidence.png`。
- 執行 `git diff --check`。

### 結果

- PoC Python：242 passed、2 skipped。
- 前端 Node：5 passed、0 failed。
- 實驗程式語法檢查通過。
- 28 份 corpus JSON、結果 JSON 與 CSV 列數檢查通過。
- 圖中文字、數值與「人工評分待完成」標示確認可讀。
- 沒有建立 VM、沒有呼叫雲端 LLM、沒有接觸正式資源。
- 使用者未追蹤檔 `scripts/offline_demo_server.py` 仍未讀改、未 stage。

### 心得

這輪最有價值的不是把成功率做成 100%，而是留下可重現的反例：v1 的結構錯誤與 v2 的語意錯誤。它們會讓後續 A 使用完全相同案例與檢查規則，不會因為換成雲端模型就降低標準。

## 16. A：確認隔離邊界與可用憑證

### 實際步驟

- 只檢查環境變數名稱是否存在，不顯示任何值。
- 搜尋 PoC 是否已有雲端 LLM 串接；沒有讀取或使用羽球+1正式資源。
- 確認 `GEMINI_API_KEY`、`GOOGLE_API_KEY`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`GOOGLE_CLOUD_PROJECT`、`GOOGLE_APPLICATION_CREDENTIALS` 均未設定。
- `.env` 只有 `DATABASE_URL`；它不是 LLM 金鑰，因此沒有嘗試使用。

### 結果

- 沒有可用的獨立雲端 LLM 測試金鑰。
- 沒有呼叫雲端、沒有登入、沒有建立專案，也沒有接觸資料庫內容。

### 心得

「電腦裡有某種憑證」不等於可以拿來做另一個實驗。要證明 A 又不影響羽球+1，最重要的是把測試金鑰、預算與資料來源分開；缺少這個條件時應先完成零網路準備，而不是借用正式設定。

## 17. A：建立零網路乾跑與費用閘門

### 實際步驟

- 新增 `benchmark_gemini_corpus.py`，預設只做 dry-run。
- 固定只讀 A/B 共用的 28 案例精簡 JSON，不送影片或檔案路徑。
- 使用 provider-native JSON schema 限制五個輸出欄位。
- 加入 US$0.05 預估費用 cap、獨立金鑰要求、固定 API host、無自動重試與 400/401/403 立即停止。
- 加入 request schema、資料邊界、費用估算與 thinking token 計費測試。

### 結果

- 28 案例全部進入乾跑計畫。
- API 請求 0 次，實際費用 US$0。
- 保守 input 上限 18,630 tokens、output 上限 8,960 tokens。
- 依 2026-09-26 Gemini 3.5 Flash-Lite 公開單價，整批最高估計 US$0.027989，低於預設 cap。
- 將舊的 Gemini 2.5 Flash-Lite 成本情境更新為目前模型與單價；10,000 次/月的透明估算由 US$2.216 更新為約 US$7.2307。
- 新增的離線實驗測試 10/10 通過。
- 依原始 JSON 產生零網路乾跑證據畫面，明確標示不是雲端效能實測。

### 心得

乾跑不是 A 的效能證據，但它先回答三個風險：到底會送什麼、最多花多少、沒有金鑰時會不會誤送。下一個有效證據必須是先跑一筆純模擬 smoke test，再決定是否讓 19 份真實影片衍生的結構資料進入 paid 隔離測試專案。

### 證據

[`A_CLOUD_LLM_BENCHMARK.zh-TW.md`](A_CLOUD_LLM_BENCHMARK.zh-TW.md) 與 [`results/gemini_35_flash_lite_28_case_preflight.json`](results/gemini_35_flash_lite_28_case_preflight.json)

### 畫面

![A 的 28 案例零網路乾跑畫面](assets/a_cloud_preflight_screen.png)

## 18. A 乾跑階段驗證

### 實際步驟

- 先從專案根目錄直接執行 pytest，確認測試收集範圍。
- 發現它會把隔離下載的 YOLOv12 上游 repository 測試一起收進主環境；該環境未安裝 PyTorch，因此在第三方測試收集階段停止。
- 改用主 PoC 自己的 `tests/` 目錄重跑，並另外執行前端 Node 測試。
- 重跑 A 成本估算、所有證據圖、JSON 格式與 Python 語法檢查。
- 目視檢查 `a_cloud_preflight_screen.png` 的數值、標題與「不是雲端效能實測」標示。

### 結果

- 主 PoC Python：244 passed、2 skipped。
- 前端 Node：5 passed、0 failed。
- A 離線實驗單元測試包含在上述結果內，10/10 通過。
- 根目錄 pytest 的停止原因是第三方 YOLOv12 測試需要其隔離環境的 PyTorch，不是主 PoC 回歸失敗。
- `scripts/offline_demo_server.py` 仍未讀改、未 stage。
- 沒有雲端請求、沒有費用、沒有改動羽球+1正式專案。

### 心得

研究用 repository 與主系統共用工作目錄時，測試範圍必須明確。這次保留了「寬範圍收集為何停止」的紀錄，再用主 PoC 的正式測試範圍驗證功能，避免把缺少研究依賴誤報成產品壞掉，也避免反過來隱藏真正的回歸。
