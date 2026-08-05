# AI Motion v0.5.0

- 新增 Footwork Assessment JSON V1
- 規定米字步測驗必須剛好 8 個完整 Event
- 多做或少做會標記 EVENT_COUNT_NOT_EQUAL_TO_8
- UNKNOWN 方向仍正常輸出 JSON
- 新增方向分類工程信心值 system_confidence
- 明確分離 test_completed、direction coverage 與 technique_score
- technique_score 暫為 null，避免尚未定義教練規則時產生假分數
- 輸出至 output/footwork_assessment.json
