# A/B/C 羽球動作分析選型實驗報告

日期：2026-09-26～2026-09-27

執行環境：Apple M5 Pro、24 GB 統一記憶體、macOS 26.5.2

結論：**目前選擇 A。雲端 LLM 已用隔離專案完成與 B 同條件的 28 案例比較；完整影片上傳、Cloud Run 與正式帳單仍是後續部署驗證。**

## 1. 先用一句話理解三個方案

- **A 像中央廚房**：影片送到雲端，由同一套 MediaPipe、評分規則與雲端 LLM 統一處理；使用者裝置不用放大模型。
- **B 像每個人家裡各放一套廚房**：MediaPipe 與 Gemma 4 都在本機，資料不必送給 LLM 供應商，但每台機器都要有足夠硬體、模型與更新流程。
- **C 像替骨架分析加一位物件球探**：MediaPipe 繼續看人體，YOLO 補看球拍、羽球與未來球路；兩者合作，不是二選一。

因此要拆成兩組問題：第一組 A vs B 比較 LLM 放雲端或地端；第二組 MediaPipe vs MediaPipe＋YOLO 比較是否值得增加物件證據。C 可以加在 A 或 B 前面，不是第三種 LLM 部署方案。

## 2. 這次怎麼判斷

選型的必要條件如下：

1. 必須保留目前可解釋、可版本化的 MediaPipe 與規則分數。
2. LLM 只能把結構化結果說成人話，不能改分數。
3. 一般使用者不能被要求下載 7 GB 模型或準備高階電腦。
4. 模型、提示詞與規則要能集中更新及回滾。
5. 「程式跑得動」與「模型準確」必須分開。
6. 所有數字必須標示為實測、估算或尚未測得。

![A/B/C 選型證據表](assets/abc_decision_evidence.png)

## 3. 共同基準：MediaPipe 實際能跑多快

使用 PoC 本機既有 `serve` 影片 `ma_120f8334b8094f5f`：

| 項目 | 實測結果 |
|---|---:|
| 影片 | 1750 × 954、683 frames、16.217 秒 |
| 重跑次數 | 3 |
| 三次牆鐘時間 | 5.6885 / 5.4291 / 4.9778 秒 |
| 平均處理時間 | 5.3651 秒 |
| 即時倍率 | 0.3308（處理比影片播放快） |
| 平均處理速度 | 127.303 FPS |
| 峰值 RSS | 368.94 MB |
| 三次整體分數 | 87 / 87 / 87 |
| 三次系統信心 | 1.0 / 1.0 / 1.0 |

這代表：目前既有核心已能穩定把人體動作轉成固定分數。A 與 B 可以共用它，不需要讓 LLM「看影片猜分數」。原始證據是 [`results/mediapipe_serve_baseline.json`](results/mediapipe_serve_baseline.json)。

以下是 PoC 既有動作報告的實際畫面，可看到分數、能力拆解與教練建議如何呈現在使用者端：

![PoC 動作報告實際畫面](../../docs/assets/screenshots/motion-report.jpg)

MediaPipe 的邊界也很清楚：單鏡頭 2D 骨架適合身體關節、動作完整性與穩定度；它不直接知道羽球落在哪裡，也不可靠地辨識球拍面、擊球瞬間或高速羽球。

## 4. A：雲端 MediaPipe + 雲端 LLM

![A 的流程與證據](assets/a_pipeline_evidence.png)

### A 的工作步驟

1. 使用者上傳影片。
2. 雲端服務執行 MediaPipe，取得人體骨架。
3. 既有規則引擎產生固定分數與證據。
4. 雲端 LLM 只讀結構化報告，產生摘要、優點、優先改善項目與練習。
5. 系統驗證 LLM JSON；失敗時仍可回傳固定規則報告。

### A 目前有哪些證據

- **實測**：相同 MediaPipe 核心處理 16.217 秒影片平均 5.3651 秒，三次分數一致。
- **實測**：隔離的 Free tier Gemini 對固定 28 案例完成 28/28，0 errors；p50 1.6191 秒、p95 2.4000 秒。
- **實測**：相同十項自動合約/grounding 檢查，A 全部通過率 100%；人工教練盲評尚未完成。
- **付費單價等值**：依實際 token usage 套公開 paid-tier 單價，28 筆合計 US$0.0121284（不是實際帳單）。
- **估算**：用 B 實際平均 414.333 input tokens、199.333 output tokens，套入 2026-09-26 Gemini 3.5 Flash-Lite 公開 standard paid tier 單價（input US$0.30/1M、output 含 thinking US$2.50/1M）。
- **估算**：Cloud Run 以 1 vCPU、依本機峰值 RSS 換算 0.3603 GiB、執行 5.3651 秒，套入公開 CPU/RAM 單價。
- **情境結果**：LLM 約 US$0.00062263/次，運算約 US$0.00010044/次，合計約 US$0.00072307/次；10,000 次/月約 US$7.2307。

這個 US$7.2307 **不是雲端帳單預測**。它沒有包含 Storage、網路、資料庫、logging、重試、稅金，也假設雲端執行時間等於這台 Mac 的本機時間。它的用途只是讓各成本成分可計算。原始估算在 [`results/option_a_cost_estimate.json`](results/option_a_cost_estimate.json)，公式在 [`estimate_option_a.py`](estimate_option_a.py)。

### A 尚未測得

- 真正的上傳時間與網路延遲。
- Cloud Run 冷啟動、不同 CPU 的 MediaPipe 執行時間。
- 真正的儲存、資料庫、監控與網路帳單。
- 多人壓測與人工教練對 56 份 A/B 輸出的盲評。

因此本報告能證明 A 的雲端解說層在固定 corpus 上較符合輸出合約與資料依據；仍不能擴大解讀為所有羽球內容都比 B 準確。

### A 與 B 的同條件 28 案例比較

兩邊都使用相同 19 份真實影片流程輸出、9 份模擬壓力案例、`minimal` 輸入、v3 提示規則與完整五欄 Schema。雲端端只送去識別結構化 JSON，不送影片或路徑。

| 指標 | A：Gemini 3.5 Flash-Lite | B1：Gemma 4 e2b + Schema |
|---|---:|---:|
| 完成 | 28/28 | 28/28 |
| p50 / p95 | 1.6191 / 2.4000 秒 | 1.4489 / 2.1314 秒 |
| 欄位型別正確 | 100% | 100% |
| 改善項目有依據且無新增 | 100% | 67.9% |
| 優點有依據或明確無資料 | 100% | 53.6% |
| 十項自動檢查全部通過 | 100% | 46.4%（13/28） |

B0 Prompt-only 的型別率是 0%；將完整 Schema 傳入 Ollama 後，B1 立即變成 100%，證明先前格式問題主要是整合層。Schema 不會修正自行新增或翻譯掉證據 ID，因此 B1 只有 13/28 十項全過。B2 加入驗證與 deterministic fallback 後最終 28/28，但 15/28 使用固定模板，不能冒充 Gemma 原始品質。新的 A/B1 56 份匿名盲評表已建立，待補人工評分。

![A 的 28 案例正式執行畫面](assets/a_cloud_final_screen.png)

![A 與 B 的同條件 28 案例比較](assets/ab_cloud_local_28_case_comparison.png)

![Gemma Prompt、Schema 與 Guardrail 比較](assets/b_schema_guardrail_comparison.png)

完整執行順序、費用口徑與資料邊界見 [A 的雲端 LLM 隔離實驗](A_CLOUD_LLM_BENCHMARK.zh-TW.md)。

## 5. B：地端 MediaPipe + 地端 Gemma 4

![B 的設備實測](assets/b_equipment_benchmark.png)

### B 做了什麼

Gemma 4 不看原始影片，只讀 MediaPipe 與規則引擎已產生的 JSON。提示詞禁止它改分數、聲稱看見球拍/羽球或做醫療診斷。

測試資料包含兩筆發球報告與一筆步法報告。GPU 模式每筆跑兩次，共 6 筆；CPU-only 模式共 3 筆。

| 項目 | Apple GPU 實測 | CPU-only 實測 |
|---|---:|---:|
| 模型 | `gemma4:e2b`, Q4_K_M | 同左 |
| 磁碟模型檔 | 7.162 GB | 同左 |
| Ollama 常駐大小 | 7.004 GB | 6.733 GB |
| 冷啟動首筆 | 5.3886 秒 | 7.2578 秒 |
| 暖機後平均 | 1.9091 秒 | 3.8094 秒 |
| 平均生成速度 | 108.469 tokens/s | 80.499 tokens/s |
| JSON 可解析率 | 100%（6/6） | 100%（3/3） |
| 必要欄位率 | 100% | 100% |
| 優先項目有根據 | 100% | 100% |

實際輸出畫面如下；完整內容在 [`results/gemma4_three_cases.json`](results/gemma4_three_cases.json) 與 [`results/gemma4_cpu_only.json`](results/gemma4_cpu_only.json)。

![Gemma 本機輸出畫面](assets/b_output_screen.png)

### B 的 28 案例擴充測試（早期 v1 探索）

為了讓 A、B 未來能使用完全相同的輸入，我對現有素材做 SHA-256 去重，建立 19 個真實「影片 × 動作」案例，再加入 9 個明確標示為非影片、不可算成真實受測者的模擬壓力案例。

- 真實：高遠球 10、步法 3、發球 6，19/19 產生報告。
- 模擬：三類動作各 3，測高低分、低信心、無分數、無改善項目等邊界。
- Gemma 一次輸出 28/28 有效 JSON，27/28 五個必要欄位完整。
- 真實案例 p50 2.0218 秒、p95 3.1906 秒；模擬案例 p50 1.3857 秒、p95 1.6554 秒。
- 當時的九項自動檢查為 26/28 全部通過；後續公平比較已加入欄位型別，改用相同 `minimal`/v3 條件，正式數字以前一節 A/B 表格為準。

`R-CLR-02` 沒有任何規則引擎標記的優點。Gemma v1 把 `strength` 欄位名稱寫錯，相同設定重跑三次仍失敗。加入嚴格 JSON 範本後，v2 三次都補回欄位，卻三次都把待改善項目誤寫成優點。這是本輪最重要的品質發現：**格式正確不代表內容正確。**另一個案例 `R-SV-02` 出現簡體字「无」，顯示仍需要輸出驗證與後處理。

![B 的 28 案例擴充證據](assets/b_28_case_evidence.png)

測試集規則與完整結果見 [A vs B 共用測試集說明](AB_BENCHMARK_CORPUS.zh-TW.md)。

初步把同一份報告以 1 個與 2 個同時請求送入暖機後的本機 Gemma，已看出總吞吐沒有增加。擴充為每級五批後，1、2、4 個同時請求的 p95 分別是 2.0710、4.1401、8.3004 秒，總吞吐分別是 0.4834、0.4838、0.4822 requests/s；35/35 成功，但幾乎是依序排隊。這顯示目前單 runner 不會因請求增加而提高產能。

![B 的並行與 VM 情境](assets/b_concurrency_vm.png)

完整設備判讀與 VM 條件見 [B 的設備、並行與 VM 專章](B_EQUIPMENT_AND_VM.zh-TW.md)。

### B 要什麼設備

這是根據「7 GB 常駐模型 + 作業系統 + MediaPipe 約 369 MB + 應用程式」做的工程建議，不是跨機型實測：

| 設備 | 判斷 | 能做到的程度 |
|---|---|---|
| 8 GB RAM | 不建議 | 模型本身已接近可用記憶體上限，容易交換記憶體、卡頓或與 MediaPipe 搶資源。 |
| 16 GB RAM | 最低建議 | 單使用者、一次一筆、短報告可行；不要同時跑多模型或重型工具。 |
| 24 GB RAM | 本次已驗證 | Apple M5 Pro 可同時完成 MediaPipe 與 Gemma 實驗，GPU 暖機後約 1.91 秒/筆。 |
| 32 GB 以上 | 開發/並行建議 | 適合保留更多餘裕、跑較大 context 或做低度並行；仍須實際壓測。 |

GPU 不是「能不能跑」的必要條件：CPU-only 也有 100% JSON 成功率。但在這台機器上，GPU 把暖機後平均等待從 3.81 秒降到 1.91 秒，約快 2 倍。

### B 是否需要租 VM

**單人 PoC 不需要。**目前 24 GB Mac 已跑通，租 VM 只會增加帳號、網路、映像、監控與費用。

只有下列情況值得評估 B-VM：沒有 16–24 GB 的可用本機、多人要遠端共用、需要排程批次處理，或要量測多請求並行。此時它其實已不再是純地端 B，而是「自己維運的雲端 Gemma」。

2026-09-26 官方公開價格情境：

| VM 情境 | 公開隨用隨付價格 | 連續 730 小時/月 |
|---|---:|---:|
| Taiwan `n2-standard-4`，4 vCPU / 16 GiB、CPU-only | US$0.194236/小時 | 約 US$141.79/月 |
| `g2-standard-4`，1×L4 / 4 vCPU / 16 GiB | US$0.706832276/小時 | 約 US$515.99/月 |

以上沒有建立 VM，也沒有量測這些 VM 的 tokens/s；只是官方標價乘以時間。CPU VM 雖然記憶體放得下，速度不能直接用 M5 Pro 數字推論。GPU VM 理論上放得下 7 GB 模型，但並行量仍要測 KV cache、context 與排隊。

### B 為何不是目前首選

B 的功能已被證明可行，而且完整 Schema 已解決欄位型別問題。本輪甚至不需要 LangChain，直接 Ollama Schema + Python 驗證即可。但原始輸出只有 13/28 十項全過，15/28 要用固定模板接手；每個執行端仍要下載 7.2 GB、保留至少約 7 GB 模型常駐空間、管理 Ollama/模型版本、guardrail 與硬體差異。若改租 VM，成本與維運又回到雲端。

### Gemma 4 是否已定案

Gemma 4 已定案為 **B 方案的已驗證 baseline**，不是「所有地端模型中的最終冠軍」。要對地端模型本身做選型，下一輪應以完全相同的 28 案例、Schema、grounding、fallback 與並行設定，再測非中國來源的 Ministral 3 8B（Mistral AI／法國）、Granite 4.1 8B（IBM／美國）與 Phi-4-mini（Microsoft／美國）。完整候選理由與公平實驗表見 [B 的非中國地端模型候選](B_LOCAL_MODEL_CANDIDATES.zh-TW.md)。

## 6. 第二組：MediaPipe vs MediaPipe＋YOLO

![MediaPipe 與 YOLO11n、YOLO12n、YOLO26n 比較](assets/mp_yolo11_yolo12_yolo26_hand_comparison.png)

### 為什麼測 YOLO11n、YOLO12n 與 YOLO26n

先前 YOLOv12 的 16 張合成圖、1 epoch 實驗只證明訓練管線可執行。Ultralytics 的 YOLO12 文件將它列為社群模型，並建議穩定工作負載使用 YOLO11 或 YOLO26；但為了完整回答世代差異，這一輪仍把三個 nano 模型都放進真正相關的「球拍＋手腕」流程。

### 方法

- 6 段去重後的真實發球影片，全部有人工右手持拍答案。
- 每段在人工作用時間窗內均勻取 12 張，共 72 張。
- MediaPipe 提供肩膀與左右手腕；YOLO 使用 COCO 預訓練 `tennis racket` 當羽球拍 proxy。
- 三個模型都用 1280 px、confidence 0.15、相同手腕 visibility 與距離規則。
- 至少 2 張成功配對且同側票數達 60% 才判定，否則回傳 `unknown`。

| 指標 | MediaPipe | MP＋YOLO11n | MP＋YOLO12n | MP＋YOLO26n |
|---|---:|---:|---:|---:|
| 可判定案例 | 5/6（83.3%） | 4/6（66.7%） | 5/6（83.3%） | 6/6（100%） |
| 全部案例的右手一致 | 2/6（33.3%） | 3/6（50.0%） | 3/6（50.0%） | 5/6（83.3%） |
| 球拍候選影格 | 不適用 | 40/72（55.6%） | 45/72（62.5%） | 49/72（68.1%） |
| 可配對手腕影格 | 不適用 | 35/72（48.6%） | 37/72（51.4%） | 38/72（52.8%） |
| YOLO p50 / p95 | 不適用 | 11.6 / 18.8 ms | 15.9 / 18.9 ms | 11.2 / 14.4 ms |

這批資料全部是右手，所以「一致率」不是左右手平衡準確率。又因為沒有人工球拍框，候選影格率也不是 precision、recall 或 mAP。

### 失敗案例與真正瓶頸

R-SV-02 中，YOLO11n、YOLO12n 與 YOLO26n 都找到球拍，卻都配到 MediaPipe 的左手腕，而人工答案是右手。這顯示問題可能是影片鏡像或左右語意沒有正規化；只微調 YOLO 不一定能修好，還要記錄前/後鏡頭與鏡像狀態。

### 決策

- MediaPipe 保留，繼續負責人體骨架、規則與固定分數。
- YOLO26n 在這個小型基準的覆蓋、一致率與 p95 延遲都較好，作為下一輪人工標註與微調主模型。
- YOLO11n 與 YOLO12n 留作控制組；YOLO12n 的候選框覆蓋較高，但案例一致率沒有超過 YOLO11n。
- 微調前先補左手影片、鏡像 metadata 與人工球拍框；否則不能誠實報完整準確率。

完整逐案結果與模型雜湊見 [MediaPipe vs MediaPipe＋YOLO 比較報告](C_MP_YOLO_COMPARISON.zh-TW.md)。

### 歷史 YOLOv12 流程驗證（不能當模型選型結果）

![C 的流程證據與研究方向](assets/c_feasibility_research.png)

先前做過以下最小流程：

- 來源：YOLOv12 作者官方 `https://github.com/sunsmarterjie/yolov12.git`。
- 固定提交：`2abab7153a065fb2925e8088e9ca2b19016ab7d6`。
- 隔離 Python 3.11.16 環境；Apple MPS；官方程式內建的非 CUDA attention fallback。
- 產生 12 張訓練、4 張驗證的 160×160 合成方塊圖，單一類別。
- 從頭訓練 YOLOv12n 1 epoch，再驗證並做 5 次暖機後推論。

| 項目 | 實測結果 |
|---|---:|
| 訓練時間 | 26.9749 秒 |
| 峰值程序 RSS | 952.28 MB |
| `best.pt` | 5,381,802 bytes（約 5.38 MB） |
| 暖機後單張推論 | 平均 0.005915 秒 |
| mAP50 / mAP50-95 | 0 / 0 |
| precision / recall | 0 / 0 |
| 五次預測數量 | 0 / 0 / 0 / 0 / 0 |

原始證據在 [`results/yolov12_tiny_feasibility.json`](results/yolov12_tiny_feasibility.json)。這只能證明 YOLOv12 作者程式在此 Mac 可完成「資料 → 訓練 → 驗證 → 推論」；零指標來自刻意極小的合成資料與 1 epoch，不能用來說 YOLO 不適合，也不能拿來否定後續 YOLO11/12/26 的預訓練實測。

![YOLOv12 訓練結果畫面](assets/c_training_result_screen.png)

### 後續仍適合研究什麼

1. **持拍手判定**：YOLO 找球拍，再把球拍位置與 MediaPipe 左/右手腕配對。
2. **羽球路徑**：YOLO 找每一幀的羽球，再用 tracker/Kalman/時間規則連成軌跡。
3. **落點分析**：球路徑之外還要做球場座標校正、辨識落地時間，再把影像座標轉成球場公分或區域。

詳細資料量、標註欄位、切分方式與驗證指標見 [C 的羽球訓練研究計畫](C_RESEARCH_PLAN.zh-TW.md)。

### 為何不把 C 拿來取代 A

C 解決的是「看見球拍/羽球/落點」，A/B 解決的是「在哪裡用 LLM 解說」。即使 YOLO26n 下一輪微調成功，它也不會自然產生既有骨架角度、動作規則或教學分數，因此不能拿 C 的結果改寫 A/B 的部署結論。

## 7. 最後為什麼選 A

證據鏈不是「A 比所有模型都準」，而是：

1. 已有 MediaPipe + 規則核心重跑穩定，A 可以直接沿用。
2. LLM 被限制為解說層，所以換雲端 LLM 不會破壞分數真實來源。
3. 同條件 28 例中，B1 p50/p95 甚至略低；選 A 不是因為速度，也不是因為 Gemma 不能輸出格式，而是 A 原始輸出十項全過 28/28，B1 為 13/28，B2 需要 15/28 fallback。
4. B 已證明能做，但每台機器需要約 7 GB 常駐模型與至少 16 GB RAM；這不適合一般終端部署。
5. B 若租 24/7 VM，CPU 參考情境約 US$141.79/月，L4 參考情境約 US$515.99/月，且還要自己維運模型。
6. 第二組實驗顯示，MediaPipe＋YOLO26n 在 6 個右手案例達到 5/6 一致、6/6 可判定，優於 MediaPipe 單獨、YOLO11n 與 YOLO12n；但仍缺左手案例與人工球拍框。
7. A 把重運算、版本、提示詞與回滾集中在服務端，一般終端只需上傳和看報告；依目前產品條件最合理。

所以正式說法應是：

> 本輪選擇 A 作為 LLM 解說層預設，因為它能沿用已驗證的 MediaPipe 固定評分，原始輸出 grounding 較穩定，又不把 7 GB 模型、至少 16 GB RAM 與 guardrail 維護轉嫁給使用者。Gemma 4 加 Schema 與 fallback 已證明可用，保留作離線方案；視覺層則保留 MediaPipe，並以 YOLO26n 作為下一輪球拍標註與微調候選。

## 8. 證據可信度與限制

- 只實測一台 Apple M5 Pro / 24 GB，不能代表所有 Mac、Windows、Linux 或 VM。
- B 的 GPU 與 CPU 輸出 token 數不同，因此延遲與 tokens/s應一起看。
- A/B 的 28 案例已完成同條件自動 contract/grounding 檢查；56 份人工教練品質盲評仍待填寫。
- A 的 LLM API 已在隔離 Free tier 專案實測；完整雲端 MediaPipe、儲存與服務帳單尚未實測。US$0.0121284 是 paid-tier 單價等值，不是帳單。
- 舊 YOLOv12 實驗只有 16 張合成圖片與 1 epoch，只驗流程；新比較有 6 段真實右手影片，但左手與人工球拍框仍為 0，因此不可宣稱平衡準確率或 mAP。
- 沒有建立雲端 VM、Cloud Run、Cloud SQL、bucket、queue、secret 或自訂 IAM，也沒有接觸羽球＋1正式資源；只有隔離專案的 Gemini API 呼叫。AI Studio 自動綁定同名服務帳戶；API key 已於收尾刪除，服務帳戶留待另行確認是否移除。

## 9. 公開來源

- [YOLOv12 作者官方實作](https://github.com/sunsmarterjie/yolov12)
- [YOLOv12 論文與官方程式連結（NeurIPS 2025）](https://proceedings.neurips.cc/paper_files/paper/2025/hash/7103444259031cc58051f8c9a4868533-Abstract-Conference.html)
- [Ultralytics YOLO12 文件：社群模型與穩定工作負載建議](https://docs.ultralytics.com/models/yolo12/)
- [Ultralytics 模型總覽：YOLO11 與 YOLO26](https://docs.ultralytics.com/models/)
- [MediaPipe Pose Landmarker 官方文件](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker)
- [Mistral 官方模型總覽](https://docs.mistral.ai/models/)
- [Ollama Ministral 3](https://ollama.com/library/ministral-3)
- [Ollama IBM Granite 4.1](https://ollama.com/library/granite4.1)
- [Ollama Microsoft Phi-4-mini](https://ollama.com/library/phi4-mini)
- [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Google Cloud Run pricing](https://cloud.google.com/run/pricing)
- [Google Cloud general-purpose VM pricing](https://cloud.google.com/products/compute/pricing/general-purpose)
- [Google Cloud accelerator-optimized VM pricing](https://cloud.google.com/products/compute/pricing/accelerator-optimized)
