# B 專章：地端 MediaPipe + 地端 Gemma 4

## B 到底在做什麼

B 分成兩位工作者：

1. **MediaPipe + 規則引擎像裁判**：看人體骨架、量測動作，給出固定分數與證據。
2. **Gemma 4 像翻譯員**：把 JSON 說成人話，產生摘要、優點、優先改善項目、練習與限制。

翻譯員不能改裁判分數。即使 Gemma 當機，原本的分數與規則報告仍然存在。

## 實驗步驟

1. 確認 `gemma4:e2b` 已完整下載：manifest 指向 7,162,394,016-byte model layer。
2. 選三筆既有結構化報告：`SV_001`、`SV_003`、`FW_002_boundary_fix`。
3. 固定 temperature 0、seed 7、JSON format、最多 320 output tokens。
4. GPU 模式先卸載模型再冷啟動，三筆各跑兩次。
5. CPU-only 模式設定 `num_gpu=0`，三筆各跑一次。
6. 每筆檢查 JSON、必要欄位、priority 是否來自輸入、caution 是否存在。
7. 模型暖機後，比較 1 個與 2 個同時請求，各跑兩批。
8. 讀取 Ollama `/api/ps` 的常駐模型大小，保留完整 JSON 結果。

## 畫面與結果

![GPU、CPU 與記憶體](assets/b_equipment_benchmark.png)

![實際 Gemma JSON 輸出](assets/b_output_screen.png)

![並行與 VM 價格情境](assets/b_concurrency_vm.png)

### GPU 模式

| 指標 | 結果 |
|---|---:|
| 測試筆數 | 6 |
| 冷啟動首筆 | 5.3886 秒 |
| 暖機後平均 | 1.9091 秒 |
| 平均 tokens/s | 108.469 |
| 成功 / JSON / 必要欄位 / grounding | 全部 100% |
| 模型常駐 | 7.004 GB，100% Apple GPU |

### CPU-only 模式

| 指標 | 結果 |
|---|---:|
| 測試筆數 | 3 |
| 冷啟動首筆 | 7.2578 秒 |
| 暖機後平均 | 3.8094 秒 |
| 平均 tokens/s | 80.499 |
| 成功 / JSON / 必要欄位 / grounding | 全部 100% |
| 模型常駐 | 6.733 GB，0 GPU |

### 並行模式

| 同時請求 | 平均每筆延遲 | p95 | 總吞吐 | 成功率 |
|---:|---:|---:|---:|---:|
| 1 | 2.0682 秒 | 2.0710 秒 | 0.4834 requests/s | 100% |
| 2 | 3.0977 秒 | 4.1401 秒 | 0.4838 requests/s | 100% |
| 4 | 5.1825 秒 | 8.3004 秒 | 0.4822 requests/s | 100% |

每級各五批，共 35 個請求。請求增加到四筆時，吞吐仍沒有增加，代表此環境實際上以排隊為主。若要多人服務，不能只看單筆 tokens/s。

## 設備建議

### 8 GB

不建議。模型常駐就接近 7 GB，還沒算作業系統、Ollama、MediaPipe、影片 buffer 與前端。即使靠 memory mapping 或 swap 勉強啟動，也不代表能穩定操作。

### 16 GB

最低建議。適合單人、一次一筆、4K context、短文字解說。應避免同時開多個大模型或重型剪輯工具。這一級是容量推估，並未在 16 GB 實機驗證。

### 24 GB

本次已驗證的等級。Apple M5 Pro / 24 GB 在 GPU 模式可將暖機後解說控制在約 1.91 秒；MediaPipe 峰值約 369 MB。適合 PoC 開發與單人展示。

### 32 GB 以上

適合需要更大 context、同時開發工具、或嘗試多模型/多 worker。但本次兩個同時請求已顯示單一 Ollama runner 的吞吐不會自動翻倍；增加 RAM 不等於增加推論副本。

## GPU 是否必要

不是必要，但有價值。在同一台 M5 Pro 上：

- CPU-only 仍然 100% 成功。
- GPU 的生成速度約為 CPU 的 1.35 倍（108.469 / 80.499）。
- GPU 暖機後端到端等待約為 CPU 的一半（1.9091 vs 3.8094 秒）。

端到端差異比 tokens/s 差異大，可能同時受到輸出 token 數、執行路徑與排隊影響；不能只用一個比例推論其他電腦。

## 要不要租 VM

### 不需要租的情況

- 單人 PoC、偶爾展示。
- 已有 24 GB Apple Silicon 或同等可用設備。
- 沒有 24/7 服務需求。
- 可以接受一次只處理一筆。

### 值得評估的情況

- 多人要從不同地點使用。
- 要排程大量報告。
- 本機沒有至少 16 GB RAM。
- 需要監控、重啟、API 化與固定服務時間。
- 資料政策允許把結構化報告送到租用機器。

### CPU VM 情境

Google Cloud Taiwan `n2-standard-4` 為 4 vCPU / 16 GiB，公開隨用隨付價 US$0.194236/小時，連續 730 小時約 US$141.79/月。容量可能放得下 Q4 模型，但本次沒有建立或測速；雲端 x86 CPU 很可能與 M5 Pro 表現不同，必須實測 p50/p95 latency。

### GPU VM 情境

`g2-standard-4` 參考公開價 US$0.706832276/小時，連續 730 小時約 US$515.99/月。L4 VRAM 足以容納此 7 GB 模型的單份權重，但 context、KV cache、並行 worker 與框架 overhead 仍會占空間。這個價格尚未包含磁碟、網路、監控與維運。

### 最重要的判斷

一旦 B 租 VM，它就不再是「完全地端」；它變成「自己維運的雲端開源模型」。此時應直接與 A 的託管雲端 LLM 比較：A 按 token 付費並由供應商維護模型；B-VM 以機器時間付費並由團隊負責容量、更新與可靠性。

## B 能做到什麼程度

- 已證明：19 個真實影片案例全部產生規則報告，再加 9 個明確標示的模擬壓力案例，共 28 份固定輸入。
- 早期 v1：28/28 是有效 JSON；一次輸出 27/28 欄位完整，當時九項檢查 26/28 全部通過。
- B0 Prompt-only：28/28 有 JSON，p50 1.8344 秒、p95 2.4474 秒；欄位型別 0%。這是整合基準，不是 Gemma 最終能力。
- B1 完整 Schema：欄位型別升至 100%，p50 1.4489 秒、p95 2.1314 秒；priority grounding 67.9%、strength grounding 53.6%，十項全過 13/28。
- B2 Schema + Python guardrail：15/28 使用固定模板 fallback 後，最終輸出 28/28 通過。這代表產品可安全降級，不代表原始模型品質 100%。
- 已發現：沒有任何優點的 `R-CLR-02` 會穩定造成 v1 欄位錯誤；v2 雖修正 schema，卻把待改善項目誤寫成優點。
- 已證明：CPU 能跑，Apple GPU 明顯縮短等待。
- 已證明：單 runner 從 1、2 到 4 個請求，總吞吐都約 0.48 requests/s；p95 從 2.07 增至 8.30 秒。
- 尚未證明：人工語意品質、更長期幻覺率、不同硬體、Windows/Linux、大規模或長時間多人壓測與 24/7 穩定性。
- 不應宣稱：Gemma 看過影片、辨識球拍或羽球、比規則引擎更會評分。

## 本段心得

B 不是做不到。完整 Schema 已解決格式問題，且不需要 LangChain；直接 Ollama + Python 驗證即可實作。它的代價是把雲端成本換成每台終端的硬體、模型、驗證與 fallback 維護。對離線、隱私、教練工作站或固定場館設備很有價值；對一般使用者與多人服務，7 GB 模型、16 GB 最低記憶體、53.6% fallback 與排隊行為仍是部署門檻。

![B 的 28 案例擴充實驗](assets/b_28_case_evidence.png)

![B 的 Schema 與 Guardrail 實驗](assets/b_schema_guardrail_comparison.png)

28 案例的資料來源、限制與人工評分表見 [A vs B 共用測試集說明](AB_BENCHMARK_CORPUS.zh-TW.md)。

## 原始證據

- [`results/gemma4_three_cases.json`](results/gemma4_three_cases.json)
- [`results/gemma4_cpu_only.json`](results/gemma4_cpu_only.json)
- [`results/gemma4_concurrency.json`](results/gemma4_concurrency.json)
- [`results/gemma4_28_case_corpus.json`](results/gemma4_28_case_corpus.json)
- [`results/gemma4_28_case_quality.json`](results/gemma4_28_case_quality.json)
- [`results/gemma4_28_case_minimal_v3.json`](results/gemma4_28_case_minimal_v3.json)
- [`results/gemma4_28_case_minimal_v3_quality.json`](results/gemma4_28_case_minimal_v3_quality.json)
- [`results/gemma4_28_case_schema_v3.json`](results/gemma4_28_case_schema_v3.json)
- [`results/gemma4_28_case_schema_v3_quality.json`](results/gemma4_28_case_schema_v3_quality.json)
- [`results/gemma4_28_case_schema_guarded_v3.json`](results/gemma4_28_case_schema_guarded_v3.json)
- [`results/gemma4_concurrency_1_2_4.json`](results/gemma4_concurrency_1_2_4.json)
- [`benchmark_gemma4.py`](benchmark_gemma4.py)
- [`benchmark_gemma_concurrency.py`](benchmark_gemma_concurrency.py)
- [Google Cloud general-purpose VM pricing](https://cloud.google.com/products/compute/pricing/general-purpose)
- [Google Cloud accelerator-optimized VM pricing](https://cloud.google.com/products/compute/pricing/accelerator-optimized)
