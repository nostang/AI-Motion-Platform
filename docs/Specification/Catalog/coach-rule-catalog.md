# Coach Rule Catalog

- **Status:** Current index
- **Owner:** AI Motion coach
- **Last verified:** 2026-09-02

教練輸出是規則式結果，不由自由生成 LLM 決定分數或 assessment truth。

- 規則資料：`../../../src/config_data/ai_coach_rules.json`
- Coach engine：`../../../src/coach/ai_coach_engine.py`
- V2 組裝：`../../../src/coach/ai_coach_v2.py`
- 動作專屬回饋：`../../../src/coach/serve_coach.py`、`clear_coach.py`
- 對外責任：[AI Coach Contract](../../AI_COACH_CONTRACT_V1.md)

規則新增時要有可觸發條件、fallback、繁體中文使用者文案與對應測試；不得讓
前端依文字內容反推分數或狀態。
