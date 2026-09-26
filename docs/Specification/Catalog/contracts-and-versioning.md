# Contracts and Versioning

- **Status:** Current
- **Owner:** AI Motion / Integration
- **Last verified:** 2026-09-02

## 版本原則

- Route、required field、enum 或錯誤語意的破壞性變更必須升版。
- 新增 optional field 應保持舊 Web consumer 可讀；`null` 不得被改寫成 `0`。
- Calibration／rubric／coach rule 必須保留可識別版本，並與結果紀錄相容。
- API、Web mapping、fixtures、tests 與文件在同一變更更新。
- 正式 image、revision 與 rollback 只記錄於 repository 根目錄的
  `HANDOFF_CURRENT.md`，不寫死在本 Catalog。

對外 schema 見 [API Contract V2](../../API_CONTRACT_V2.md)，Web 消費範圍見
[Web API Contract](../../WEB_API_CONTRACT_V1.md)。
