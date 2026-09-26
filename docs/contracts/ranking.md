# 排名契約

一個 cohort 的排名如何產生、哪些股票能入選，以及排名 artifact 必須包含什麼。

- 狀態：step-2 定稿；投資組合檔數 K 與權重於 step-19 前決定（D22）
- 實作：step-19

## 1. 輸入

| 輸入 | 來源 |
|---|---|
| 模型 artifact | step-18；載入時驗證特徵 schema 與 derivation 版本 |
| cohort C 的推論矩陣 | step-14；只有特徵，沒有標籤 |
| cohort C 的股票池快照 | step-7 |
| 入選篩選所需的資料 | `valuation-metrics.ttm_eps`、`daily-prices.volume`（[`data-dependencies.md`](data-dependencies.md) §3） |

所有輸入都在同一個 `PitContext`（T_C、K_mode）下取得。

## 2. 流程

```text
股票池（time-and-cohort §8）
  → 模型評分：股票池內每一檔都有分數
  → 入選篩選（D10）：
        TTM EPS ≥ 2（null 不通過）
        P_C 前 7 個交易日平均成交量 ≥ 500 張（缺資料的日子以 0 計）
  → 排名：通過篩選的股票依分數由高到低排序；同分依股票代號由小到大
  → 入選：排名前 K 名（K 於 step-19 前決定）
```

- 不通過篩選的股票仍然保留分數，寫入 artifact，但沒有名次，也不能入選。這樣可以事後檢查篩選擋掉了什麼。
- 整個流程是確定性的：相同的模型與資料，一定產生相同的排名。

## 3. 排名 artifact

每一檔股票池內的股票一列：

| 欄位 | 說明 |
|---|---|
| `cohort_id` | 例如 `2024-07` |
| `stock_id` | 股票代號 |
| `score` | 模型分數 |
| `eligible` | 是否通過入選篩選 |
| `exclusion_reasons` | 未通過的原因，可複選：`ttm_eps_below_2`、`ttm_eps_null`、`volume_below_500_lots` |
| `ttm_eps`、`avg_volume_7d` | 篩選所用的值 |
| `rank` | 名次；只有 `eligible` 的股票才有 |
| `selected` | 是否入選 |
| `weight` | 入選股票的權重；預設等權重 |

artifact 層級的 metadata：

| 欄位 | 說明 |
|---|---|
| `ranking_id` | 內容雜湊 |
| `kind` | `production` 或 `reconstruction`（D6） |
| `model_id` | 模型 artifact 的雜湊 |
| PIT 情境 | T_C、`knowledge_as_of`，以及 Data Center 回傳的 `pit` 區塊 |
| 特徵 schema 版本 | — |
| canonical derivation 版本 | 每個衍生資料集的 `dataset_code` 與 `derivation_version` |
| Data Center provenance | 每次查詢的回應雜湊 |
| 篩選參數 | EPS 門檻 2、均量門檻 500 張、均量天數 7、K |
| 股票池大小、通過篩選的檔數 | 讓股票池特別小的月份（time-and-cohort §8）看得出來 |
| git commit | — |

## 4. 不可變

- artifact 只能寫入一次。以相同 `ranking_id` 寫入時，拒絕覆寫。
- 歷史重跑一律產生新的 `reconstruction` artifact，不覆寫原本的 `production` 排名。
- production 執行前檢查資料新鮮度（step-19）：P_C 前一個交易日沒有日價格，或交易日曆沒有涵蓋到 T_C，就失敗，不產生排名。
