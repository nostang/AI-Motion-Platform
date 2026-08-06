# Assessment Metric Catalog

Assessment Metric 負責將可用資料轉換為客觀、可追溯的評估結果。Assessment 不負責模擬真人教練語氣。

## AR001 — Movement Completion

| 欄位 | 定義 |
|---|---|
| Metric ID | `AR001`（邏輯識別；目前 JSON 尚未輸出獨立 metric object） |
| 名稱 | Movement Completion |
| 輸入 | expected event count、detected event count、completed event count |
| 目前條件 | 預期 8 個 Event，且 8 個均完成 |
| Report 分數 | PASS = 25；FAIL = 0；其他 = Not Evaluated |
| Coach Rule | `CR001` |

### 限制

- 只評估測驗流程是否完成。
- 不代表每個方向或步法技術皆正確。

## AR002 — Recovery Speed

| 欄位 | 定義 |
|---|---|
| Metric ID | `AR002` |
| 名稱 | Recovery Speed |
| 輸入 | 每個 Event 的 `recovery_time_seconds` |
| 最少有效 Event | 6 |
| 快速參考值 | 0.60 秒 |
| 慢速參考值 | 1.50 秒 |
| 最大分數 | 25 |
| PASS 分數 | 18 |
| Config Version | `recovery-speed-v1` |
| Coach Rule | `CR005` |

### 輸出

```text
average_seconds
median_seconds
fastest_seconds
slowest_seconds
valid_event_count
score
max_score
status
result
thresholds
```

### 限制

- 門檻為暫定 Calibration，尚未經真人教練樣本驗證。
- 分數只描述目前影片中的回位時間。
- 不等同於完整 Footwork Technique。
- 拍攝角度、場地尺度與方向差異可能影響結果。

## AR003 — Direction Coverage

| 欄位 | 定義 |
|---|---|
| Metric ID | `AR003` |
| 名稱 | Direction Coverage |
| 輸入 | direction coverage map、missing directions、duplicate directions |
| 預期方向 | 8 |
| 分數算法 | `observed_direction_count / expected_direction_count × 25` |
| Config Version | `direction-coverage-v1` |
| Coach Rule | `CR003` |

### 預期方向

```text
RIGHT_FRONT
LEFT_FRONT
RIGHT_BACK
LEFT_BACK
RIGHT
LEFT
FRONT
BACK
```

### 結果規則

- 8/8：`PASS`
- 少於 8/8：`NEEDS_REVIEW`
- `NEEDS_REVIEW` 不等同於使用者做錯。

### 限制

- 缺方向可能來自動作、拍攝角度或方向分類誤差。
- 此分數是測驗覆蓋指標，不是完整步法技術分數。

## 尚未評估

目前下列項目沒有足夠且已校正的 Feature，因此維持 `NOT_EVALUATED`：

```text
Footwork Technique
Body Stability
Extra Steps
Split Step
Lead Foot
Dominant Hand Rule
Coach Similarity
```

不得以 `0` 代替 `NOT_EVALUATED`。
