# Motion Feature Catalog

Motion Feature 是由 Pose Landmark 抽出的描述性資料。Feature 本身不代表技術好壞，也不得直接當作教練結論。

## 共通規則

- Feature Version：`motion-feature-v1`
- 來源：MediaPipe Pose 2D image-normalized landmarks
- 最低 Landmark Visibility：`0.5`
- 收集階段：`MOVE` 與 `RECOVER`
- 輸出層級：每個 Footwork Event
- Scoring：停用

每個 Feature 目前保存：

```text
sample_count
mean_degrees
mean_absolute_degrees
max_absolute_degrees
standard_deviation_degrees
```

## MF001 — Shoulder Tilt

| 欄位 | 定義 |
|---|---|
| Feature ID | `MF001_shoulder_tilt` |
| 名稱 | Shoulder Tilt |
| 輸入 Landmark | Left Shoulder 11、Right Shoulder 12 |
| 計算 | 肩線相對影像水平軸的有號角度 |
| 單位 | degree |
| 可用階段 | MOVE、RECOVER |
| 目前用途 | 描述肩線變化；提供後續 Calibration 與 Expert Review |
| Scoring | 尚未啟用 |

### 限制

- 目前角度受人物朝向、左右 Landmark 次序與角度環繞影響。
- 原始值可能接近 `±180°`；尚未完成穩定角度正規化。
- 在正規化完成前，不得直接用於 Body Stability 分數。

## MF002 — Hip Tilt

| 欄位 | 定義 |
|---|---|
| Feature ID | `MF002_hip_tilt` |
| 名稱 | Hip Tilt |
| 輸入 Landmark | Left Hip 23、Right Hip 24 |
| 計算 | 髖線相對影像水平軸的有號角度 |
| 單位 | degree |
| 可用階段 | MOVE、RECOVER |
| 目前用途 | 描述骨盆線變化；提供後續 Calibration 與 Expert Review |
| Scoring | 尚未啟用 |

### 限制

- 與 MF001 相同，原始角度可能受到 `±180°` 環繞影響。
- 拍攝角度、遮擋與人體轉身會影響數值。
- 在正規化與樣本驗證前，不得直接產生穩定度分數。

## MF003 — Torso Lean

| 欄位 | 定義 |
|---|---|
| Feature ID | `MF003_torso_lean` |
| 名稱 | Torso Lean |
| 輸入 Landmark | Shoulder midpoint、Hip midpoint |
| 計算 | 肩中心相對髖中心，與影像垂直軸的有號角度 |
| 單位 | degree |
| 可用階段 | MOVE、RECOVER |
| 目前用途 | 描述軀幹左右傾斜幅度；提供 Body Stability 的候選 Feature |
| Scoring | 尚未啟用 |

### 限制

- 只描述 2D 影像平面的軀幹傾斜。
- 不代表真實三維重心或生物力學穩定度。
- 不同攝影機高度、旋轉與透視會改變結果。

## Pose Quality Metadata

每個 Event 同時保存：

```text
minimum_visibility
average_visibility
minimum_required_visibility
valid_sample_ratio
phase_samples.move
phase_samples.recovery
```

Feature 使用端必須先檢查：

1. `status == EXTRACTED`
2. `valid_sample_count > 0`
3. `valid_sample_ratio` 達到該 Assessment Rule 要求
4. Feature 已完成必要的角度正規化與 Calibration
