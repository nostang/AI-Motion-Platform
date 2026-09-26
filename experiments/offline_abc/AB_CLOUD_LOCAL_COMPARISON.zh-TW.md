# A vs B：同條件 28 案例結論

日期：2026-09-27

## 先講結論

這輪資料支持選 A，但理由不是「雲端快很多」。A、B 的單筆回應速度接近；A 的差異在於它較穩定遵守產品要求的欄位型別，且輸出的改善與優點較能對回輸入證據。B 還多了 7.2 GB 模型、至少 16 GB RAM、Ollama 與版本維護負擔。

![A 與 B 的同條件 28 案例比較](assets/ab_cloud_local_28_case_comparison.png)

## 怎麼做到公平

A 與 B 都使用：

- 相同 28 案例：19 個真實影片流程輸出、9 個明確標示的模擬壓力案例。
- 相同 `minimal` 輸入：動作類型、狀態、總分、信心、優點、改善項目與前兩項限制。
- 相同 v3 提示規則與五欄 JSON 合約。
- 相同十項自動 contract/grounding 檢查。

A 透過隔離 Free tier 測試專案呼叫 Gemini 3.5 Flash-Lite；B 在本機 Apple M5 Pro / 24 GB 上呼叫 Ollama Gemma 4 e2b。A 的刻意 4.5 秒 rate-limit 等待不算在單筆 API 回應時間；因此表格比較的是請求送出到回應完成的時間，不是整批牆鐘時間。

## 數字

| 指標 | A：雲端 Gemini | B：地端 Gemma 4 | 解讀 |
|---|---:|---:|---|
| 完成 | 28/28 | 28/28 | 兩者都能產生輸出 |
| p50 | 1.6191 秒 | 1.8344 秒 | A 稍低，但不是數量級差距 |
| p95 | 2.4000 秒 | 2.4474 秒 | 尾端延遲非常接近 |
| 精確五個 key | 100% | 100% | 兩者都能列出 key |
| 欄位型別正確 | 100% | 0% | B 常把字串回成陣列 |
| priority 有輸入依據 | 100% | 64.3% | A 較穩定引用原始改善 ID |
| strength 有依據或明確無資料 | 100% | 42.9% | B 較常產生未對應的優點 |
| 十項全部通過 | 100% | 0% | B 每案至少有一項合約失敗 |
| 本輪成本口徑 | US$0.0121284 paid-tier 單價等值 | 使用既有本機設備 | A 專案為 Free tier；兩者都不是完整 TCO |

## 為什麼 B 的 0% 不能說成「B 完全沒用」

B 仍有 28/28 可解析 JSON，而且內容可以閱讀。0% 指的是：在這個嚴格的五欄合約下，每一案至少有一個欄位型別不符合，最常見是 `summary` 或 `caution` 應是單一字串卻回成陣列。這會增加後端驗證、修正與 fallback 成本，但不等同於人類認為每篇內容都是 0 分。

同樣地，A 的 100% 只代表這 28 例通過預先定義的自動規則，不代表所有影片、所有語意或教練品質永遠正確。

## 還差哪一塊證據

已建立 56 列的 [`results/ab_28_case_blind_human_review.csv`](results/ab_28_case_blind_human_review.csv)。評分者看不到 A/B 提供者，需對 grounding、helpfulness、clarity、hallucination 評分。這一輪先留下可直接填寫的表，不模擬人類分數，也不把自動檢查冒充人工判斷。

另外尚未測完整影片上傳、Cloud Run 冷啟動、雲端 MediaPipe 硬體差異、正式帳單與多人壓測。這些是「正式部署」的補驗，不會抹掉本輪解說層與設備門檻的比較結果。

## 我可以怎麼說

> 我沒有只拿 A 的理論優點去比 B，而是讓兩個模型讀同一組 28 份最小化報告。兩邊速度接近，但 A 在欄位型別、改善依據與優點依據都達到 100%；B 分別是 0%、64.3%、42.9%。再加上 B 每個執行端需要約 7.2 GB 模型與至少 16 GB RAM，因此本輪選 A 作預設方案，B 保留給離線或特殊隱私需求。

## 原始證據

- A 執行：[`results/gemini_35_flash_lite_28_case_minimal_v3.json`](results/gemini_35_flash_lite_28_case_minimal_v3.json)
- A 品質：[`results/gemini_35_flash_lite_28_case_minimal_v3_quality.json`](results/gemini_35_flash_lite_28_case_minimal_v3_quality.json)
- B 執行：[`results/gemma4_28_case_minimal_v3.json`](results/gemma4_28_case_minimal_v3.json)
- B 品質：[`results/gemma4_28_case_minimal_v3_quality.json`](results/gemma4_28_case_minimal_v3_quality.json)
- 人工盲評表：[`results/ab_28_case_blind_human_review.csv`](results/ab_28_case_blind_human_review.csv)
