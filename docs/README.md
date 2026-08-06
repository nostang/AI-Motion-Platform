# AI Motion Platform Documentation

本目錄是 AI Motion Platform 的文件入口。文件依「架構、API、版本紀錄、正式規格、展示圖片」分類，避免系統規格與 AI Motion Catalog 混在同一層。

## 文件導覽

### Architecture

- [System Architecture](Architecture/architecture.md)
- [Architecture Diagram](Architecture/architecture.png)

### API

- [Local API Run Guide](API/API_RUN.md)
- [AI Motion API Contract](API/AI_Motion_API_Contract.md)

### Design and Changelog

- [Changelog Index](Design/CHANGELOG.md)
- `CHANGELOG_v0.x.x.md`：各歷史 Sprint 的版本紀錄

### Specification

- [Specification Index](Specification/README.md)
- `Core/`：Measurement、Footwork Event、Coach Engine、Report 等系統核心規格
- `Catalog/`：Motion Feature、Assessment Metric、Coach Rule 與契約版本
- `Archive/`：已被新版取代、但仍需保留追溯性的歷史規格

### Images

- `home.png`
- `swagger.png`
- `motion-summary.png`
- `radar-analysis.png`

## 文件原則

1. **Source of Truth**：程式與實際 JSON 輸出優先；文件不可虛構尚未實作的分數或能力。
2. **Feature 不等於 Score**：Motion Feature 只保存描述性資料，需經 Calibration 與 Assessment Rule 才能評分。
3. **NEEDS_REVIEW 不等於 FAIL**：方向辨識或校正不確定時，必須保留人工審查語意。
4. **NOT_EVALUATED 不得當作 0 分**：缺少 Feature、Calibration 或 Rule 時，應明確維持未評估。
5. **歷史文件不覆蓋**：已被新版取代的規格移至 `Archive/`，避免失去版本追溯。
