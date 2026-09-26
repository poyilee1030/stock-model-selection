# Data Center 資料依賴契約

v1 使用的每一個 Data Center 資料集：用途、要求的 derivation 版本、查詢方式，以及必須達到的 PIT 層級。
PIT 層級與兩種執行模式的定義見 [`time-and-cohort.md`](time-and-cohort.md) §5、§6。

- 狀態：step-2 定稿
- 規則：
  - 程式碼只能使用本文件列出的資料集。要新增資料集，先更新本文件。
  - 衍生資料集的 `derivation_version` 必須與本文件相同，不同就失敗（step-8-a）。
  - 回應的 `pit.defaulted` 若列出呼叫端有提供的截止點，就拒絕該回應（step-5-a）。

## 1. 符號

| 符號 | 意義 |
|---|---|
| T_C | cohort C 的資訊截止點（playbook date 04:00 台北時間） |
| K_mode | 依執行模式的 `knowledge_as_of`：production 為執行時點，reconstruction 為明確的重建時點 |
| P_C、X_C | cohort C 的進場日（playbook date）與出場日 |

## 2. 參考資料（不是 PIT）

| 端點 | 用途 | 查詢方式 | 風險與處理 |
|---|---|---|---|
| `/v1/stocks?date=P_C` | 股票池的掛牌狀態、市場、產業（只用於排除金融保險業） | `date` = P_C | 原地更新：快照記錄回應雜湊，重建時若不同就回報（step-7）。`industry` 是今日分類（D16） |
| `/v1/trading-days` | 營收截止日、playbook date、出場日、7 日均量的交易日 | `start` / `end` | 原地更正：日曆記錄回應雜湊。未涵蓋到截止點時，production 失敗（step-19） |

## 3. 股票池與入選篩選

| 資料集 | 欄位 | 用途 | 查詢方式 | 要求的 PIT 層級 |
|---|---|---|---|---|
| `monthly-revenues`（observed） | 列是否存在 | M-1 月營收可見才列入股票池（D8） | `information_as_of=T_C`、`knowledge_as_of=K_mode` | 列層級 |
| `daily-prices`（observed） | `volume` | P_C 前一個交易日有成交；7 日均量 ≥ 500 張（D10） | 同上 | 列層級 |
| `valuation-metrics`（derived，`valuation_metrics` v1） | `ttm_eps` | TTM EPS ≥ 2 才入選（D10） | `information_as_of=T_C`、`knowledge_as_of=latest` | 列層級（已知重編風險，D17） |

## 4. 特徵

特徵的所有權分界見 [`feature-ownership.md`](feature-ownership.md)。

| 資料集 | kind | dataset_code / 版本 | 查詢方式 | 要求的 PIT 層級 | 已知風險 |
|---|---|---|---|---|---|
| `technical-indicators-pit` | derived_on_demand | `technical_indicators_pit` v1 | `view=rolling`、每次一檔股票、`knowledge_as_of=K_mode`；只取 `trade_date` ≤ P_C 前一個交易日的列，並檢查每列的 `information_as_of` ≤ T_C | 值層級 | 價格是原始收盤價，未還原權息；除權息日附近的指標會跳動 |
| `monthly-revenues` | observed | — | `information_as_of=T_C`、`knowledge_as_of=K_mode` | production 值層級；reconstruction 列層級 | 營收可能事後更正 |
| `official-valuations` | observed | — | 同上 | 同上 | — |
| `institutional-flows` | observed | — | 同上 | 同上 | — |
| `foreign-holdings` | observed | — | 同上 | 同上 | — |
| `margin-trading` | observed | — | 同上 | 同上 | — |
| `securities-lending` | observed | — | 同上 | 同上 | — |
| `shareholding-distributions` | observed | — | 同上 | 同上 | 週頻；快照日後的週日 12:00 才可用 |
| `institutional-streaks` | derived | `institutional_streaks` v1 | `information_as_of=T_C`、`knowledge_as_of=latest` | 列層級 | 以最新輸入計算 |
| `institutional-cumulative-flows` | derived | `institutional_cumulative_flow` v1 | 同上 | 列層級 | 從序列第一天起累加，是代理值，不是持股 |
| `shareholding-concentrations` | derived | `shareholding_concentration` v1 | 同上 | 列層級 | — |
| `margin-metrics` | derived | `margin_metrics` v1 | 同上 | 列層級 | — |
| `short-interest-metrics` | derived | `short_interest_metrics` v1 | 同上 | 列層級 | — |
| `valuation-metrics` | derived | `valuation_metrics` v1 | 同上 | 列層級 | 用財報最新版本計算，重編時歷史值會改變（D17）；2025 Q3 以前的財報可見時點是保守日期 |

## 5. 標籤與回測

| 資料集 | kind | dataset_code / 版本 | 用途 | 查詢方式 | 要求的 PIT 層級 |
|---|---|---|---|---|---|
| `adjusted-prices-pit` | derived_on_demand | `adjusted_prices_pit` v1 | 標籤與回測的進出場價格（D12） | 每次一檔股票；`start`=P_C、`end`=X_C；`information_as_of=label_available_at(C)`、`knowledge_as_of=K_mode`；保留 `events` 區塊 | 值層級 |
| `indices` | observed | — | 基準報酬（D13） | `information_as_of=label_available_at(C)`、`knowledge_as_of=K_mode`；依 `source` 與 `index_name` 過濾 | production 值層級；reconstruction 列層級 |

## 6. v1 不直接使用的資料集

| 資料集 | 原因 |
|---|---|
| `technical-indicators` | 已儲存版本只有列層級 PIT；改用 `technical-indicators-pit` |
| `financial-reports` | 由它衍生的指標（EPS、ROE、利潤率）屬於 canonical；v1 經由 `valuation-metrics` 使用。直接使用財報欄位前，先處理 D21 |
| `corporate-actions` | 經由 `adjusted-prices-pit` 的 `events` 間接使用；不自行調整價格（D4） |
| `institutional-market-flows` | v1 沒有市場層級的特徵 |

## 7. 查詢限制（step-6 實作）

- 每個請求最多 200 個 `stock_id`；不帶 `stock_id` 時，`start`–`end` 最多 31 天。
- `technical-indicators-pit` 與 `adjusted-prices-pit` 每次只能一檔股票。實測 2330 完整歷史的 `view=rolling` 約 0.45 秒，全市場約 1800 檔。
- 所有回應的 `pit` 區塊都存入 provenance。
