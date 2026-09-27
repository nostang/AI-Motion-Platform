# B 的下一輪地端模型候選（排除中國模型）

日期：2026-09-27

## 結論先講

`gemma4:e2b` 已定案為 **B 方案目前有完整實測證據的 baseline**，但尚未定案為「最佳地端模型」。目前只有 Gemma 4 跑完固定 28 案例、完整 JSON Schema、grounding 檢查、fallback、CPU/GPU 與並行測試；其他模型沒有跑同一份考卷，不能直接宣布輸贏。

下一輪建議測三個非中國來源模型：

1. **Ministral 3 8B**（Mistral AI，法國）：主挑戰者。
2. **Granite 4.1 8B**（IBM，美國）：結構化 JSON 挑戰者。
3. **Phi-4-mini 3.8B**（Microsoft，美國）：低規格／速度控制組。

明確排除 Qwen、DeepSeek、Kimi、GLM 等中國公司模型。

## 為什麼選這三個

| 模型 | 開發者／來源 | Ollama Q4 大小 | 官方或模型頁能力 | 本專案角色 |
|---|---|---:|---|---|
| Gemma 4 `e2b` | Google／美國 | 已安裝 7.2 GB | 本專案已完成 28 案例 Schema 與 guardrail 實測 | 現有 baseline |
| Ministral 3 8B | Mistral AI／法國 | 約 6.0 GB | Edge、中文等多語、system prompt、function calling、JSON output | **第一優先主挑戰者** |
| Granite 4.1 8B | IBM／美國 | 約 5.3 GB | 多語、中文、tool use、原生 structured JSON、Apache 2.0 | **第二優先結構化挑戰者** |
| Phi-4-mini 3.8B | Microsoft／美國 | 約 2.5 GB | 多語、推理、function calling；硬體負擔小 | **低規格控制組** |
| Llama 3.1 8B | Meta／美國 | 約 4.9 GB | 成熟 8B、128K context、工具能力 | 可選；繁中不是本輪首要優勢 |

來源：

- [Mistral 官方模型總覽](https://docs.mistral.ai/models/)
- [Ollama Ministral 3 模型頁](https://ollama.com/library/ministral-3)
- [Ollama Granite 4.1 模型頁](https://ollama.com/library/granite4.1)
- [Ollama Phi-4-mini 模型頁](https://ollama.com/library/phi4-mini)
- [Meta Llama 3.2 官方介紹](https://ai.meta.com/blog/llama-3-2-connect-2024-vision-edge-mobile-devices/)

Ollama 頁面的檔案大小是下載／量化版本資訊，不是本機實測常駐記憶體。本機目前 Ollama 版本為 0.32.15；已安裝 `gemma4:e2b`、`gemma3:4b`、`llama3.2:1b`、`gemma3:270m`，三個新候選尚未下載或實測。

## 為什麼不直接改用已安裝的 Llama 3.2 1B

它只有約 1.3 GB，適合確認極低規格能不能跑，但與 7.2 GB Gemma 4 的容量差太大。若它輸出品質較差，我們無法分辨是模型家族差異，還是單純參數量太小。因此它可以當「最低硬體下限」控制組，不應成為主要替代候選。

## 公平實驗方式

每個候選都必須使用和 Gemma 4 完全相同的：

- 19 份真實流程報告＋9 份模擬壓力案例，共 28 案例。
- 五欄 JSON Schema。
- v3 prompt 與 minimal 結構化輸入。
- temperature、輸出上限、grounding 十項檢查。
- deterministic normalization 與固定模板 fallback。
- GPU 暖機、CPU-only、1/2/4 concurrency 測試。

比較表應至少包含：

| 指標 | 為什麼需要 |
|---|---|
| 原始十項全過率 | 真正比較模型輸出，不把 fallback 算成模型能力 |
| priority / strength grounding | 是否引用輸入中的真實 evidence ID |
| fallback rate | 產品需要規則模板接手多少次 |
| 繁體中文一致性 | 是否混入簡體字或無法理解的翻譯 |
| p50 / p95 | 使用者要等多久 |
| tokens/s | 排除輸出長短造成的假速度差 |
| 模型檔與 resident memory | 能否在 16 GB／24 GB 裝置實際使用 |
| 1/2/4 concurrency | 多人使用是否只是排隊 |

## 建議順序

1. 先測 **Ministral 3 8B**：大小和 Gemma 4 接近，且明確主打 edge、多語與 JSON，最適合做公平主對手。
2. 再測 **Granite 4.1 8B**：原生 structured JSON 與企業 instruction-following 很符合五欄報告任務。
3. 最後測 **Phi-4-mini**：若品質可接受，它可能把硬體門檻從約 7 GB 模型降到約 2.5 GB。

在這三個模型跑完同一批 28 案例以前，正確說法是：

> Gemma 4 已完成可行性定案，可以作為 B 的離線 baseline；「B 最佳地端模型」尚未定案。
