# A vs B 共用測試集說明

## 目的

建立一份 A 與 B 都能使用的固定輸入，避免兩個方案各挑對自己有利的案例。A 尚未執行雲端測試；本輪先完成資料集與 B 的基準結果。

## 盤點結果

- 專案中表面可找到 74 個影片檔。
- 用 SHA-256 去除完全相同的內容後，剩下 24 段不同影片。
- 有可信動作類型、可送進現有流程的，是 18 段不同影片。
- 同一段影片可有不同動作標籤，因此形成 19 個「影片 × 動作類型」案例。
- 既有 94 個 calibration JSON 多數是同一案例的不同版本與中間產物，不能當成 94 位受測者。

## 最終 28 案例

| 類型 | 高遠球 | 步法 | 發球 | 合計 |
|---|---:|---:|---:|---:|
| 真實影片經 MediaPipe/規則流程產生 | 10 | 3 | 6 | 19 |
| 人工設計的結構化壓力 JSON | 3 | 3 | 3 | 9 |
| 合計 | 13 | 6 | 9 | 28 |

19 個真實案例全部完成報告生成；其中一份步法報告的狀態是 `NOT_EVALUATED`，仍保留在資料集，用來測試 LLM 面對證據不足時是否誠實。這 19 份不能宣稱是 19 位不同受測者，因為實際上來自 18 段不同影片。

9 個模擬案例只用來測試 LLM 的邊界，包括：高分但仍有小問題、低分且多項改善、沒有分數、低信心、沒有改善項目等。每份檔案都含：

```json
{
  "evidence_kind": "synthetic_structured_stress_case",
  "not_from_video": true,
  "must_not_be_counted_as_real_subject": true
}
```

## B 的第一次完整結果

| 指標 | 全部 28 份 | 19 份真實 | 9 份模擬 |
|---|---:|---:|---:|
| 有效 JSON | 100% | 100% | 100% |
| 五個必要欄位完整 | 96.4% | 94.7% | 100% |
| 平均延遲 | 2.0295 秒 | 2.3305 秒 | 1.3941 秒 |
| p50 | 1.9705 秒 | 2.0218 秒 | 1.3857 秒 |
| p95 | 2.8806 秒 | 3.1906 秒 | 1.6554 秒 |

自動九項檢查有 26/28 全部通過。九項包含：固定 schema、必要值非空、改善項目有根據、優點有正向證據、分數引用未被修改、說明 2D 限制、沒有聲稱直接看見畫面、證據不足時有保留、基本繁中一致性。

這仍然不是教練人工品質評分。`gemma4_28_case_human_review.csv` 已留下 grounding、實用性、清楚度與幻覺欄位，等 A 產生相同案例輸出後再做盲評。

## 發現的兩個問題

1. `R-CLR-02`：輸入沒有 `strengths`，Gemma v1 雖回傳有效 JSON，卻把 `strength` key 寫成一整句文字。相同設定重跑三次，三次都失敗，顯示是穩定的提示詞/schema 問題。
2. `R-SV-02`：內容與欄位通過，但 priority 使用簡體字「无」，未完全遵守繁體中文要求。

對 `R-CLR-02` 加入嚴格 JSON 範本後，v2 三次都補回正確欄位；但三次都把四個待改善項目同時當成優點。這證明 schema 成功與語意正確是兩件事，不能只靠提示詞或 JSON mode 宣稱內容可靠。

## 1、2、4 個同時請求

每級執行五批，模型先暖機：

| 同時請求 | 請求數 | p50 | p95 | 總吞吐 |
|---:|---:|---:|---:|---:|
| 1 | 5 | 2.0686 秒 | 2.0710 秒 | 0.4834 requests/s |
| 2 | 10 | 3.0947 秒 | 4.1401 秒 | 0.4838 requests/s |
| 4 | 20 | 5.1727 秒 | 8.3004 秒 | 0.4822 requests/s |

35/35 請求成功，但吞吐幾乎固定。這台機器上的單一 Ollama runner 是依序處理；第四筆最差約等四輪，增加請求只會增加等待。

## 證據檔

- [`results/ab_corpus_manifest.json`](results/ab_corpus_manifest.json)：來源、SHA-256、動作與真實/模擬標記。
- [`corpus/`](corpus/)：28 份實際輸入報告。
- [`results/gemma4_28_case_corpus.json`](results/gemma4_28_case_corpus.json)：28 份 Gemma 原始輸出與延遲。
- [`results/gemma4_28_case_quality.json`](results/gemma4_28_case_quality.json)：自動檢查。
- [`results/gemma4_28_case_human_review.csv`](results/gemma4_28_case_human_review.csv)：待人工填寫的評分表。
- [`results/gemma4_concurrency_1_2_4.json`](results/gemma4_concurrency_1_2_4.json)：並行原始結果。

![28 案例 B 實驗證據](assets/b_28_case_evidence.png)
