# 特徵所有權契約

哪些數值由 Data Center 計算（canonical），哪些由本專案計算（模型專屬）。

- 狀態：step-2 定稿
- 原則（ROADMAP §1、§3）：Data Center 擁有可重用的 canonical 指標；本專案擁有排名專用的轉換、標籤、訓練、排名與回測。

## 1. 分界規則

| 類型 | 誰擁有 | 判斷方式 | 例子 |
|---|---|---|---|
| 單一股票的時間序列衍生值 | Data Center（canonical） | 只用一檔股票自己的歷史資料就算得出來，而且別的系統也可能要用 | 均線、RSI、營收年增率、TTM EPS、ROE、報酬率、波動度 |
| 同一 cohort 內的橫斷面轉換 | 本專案 | 需要同一個 cohort 裡其他股票的值 | 排名、百分位、z-score、winsorize |
| 排名導向的組合與交互作用 | 本專案 | 為了排名而組合多個特徵 | 動能 × 品質、複合分數 |
| 標籤 | 本專案 | 未來報酬 | `adjusted_close(X_C) / adjusted_open(P_C) - 1` |
| 入選篩選 | 本專案（排名） | 使用者的業務規則 | EPS ≥ 2、7 日均量 ≥ 500 張（D10） |

- 本專案要計算一個 canonical 類型的數值，必須先寫 ADR（範本 [`../adr/0000-template.md`](../adr/0000-template.md)），並在 step-9 的 registry 中附上 ADR 編號。沒有 ADR 的，registry 拒絕。
- 例外：D10 的 7 日均量是業務篩選規則，只用來決定能否入選，不當作特徵。Data Center 沒有 7 日的量均線（`technical-indicators-pit` 只有 5、10、20、60、120、240 日），所以不算重複實作。

## 2. v1 的 canonical 輸入

以原值直接帶入（passthrough），再由本專案做橫斷面轉換。

| 特徵族 | 資料集 | 欄位 |
|---|---|---|
| 技術指標 | `technical-indicators-pit`（`view=rolling`） | `ma5`…`ma240`、`vma5`…`vma240`、`k`、`d`、`rsi6`、`rsi12`、`macd_dif`、`macd_dea`、`macd_hist`、`bb_upper`、`bb_middle`、`bb_lower` |
| 月營收 | `monthly-revenues` | `revenue`、`mom_pct`、`yoy_pct`、`cumulative_yoy_pct` |
| 官方評價 | `official-valuations` | `pe_ratio`、`pb_ratio`、`dividend_yield` |
| 計算評價 | `valuation-metrics` | `ttm_eps`、`pe_ratio`、`pe_percentile`、`roe` |
| 法人買賣 | `institutional-flows` | `foreign_net`、`trust_net`、`dealer_net`、`total_net` |
| 法人連續買賣 | `institutional-streaks` | `foreign_streak_days`、`trust_streak_days`、`dealer_streak_days` |
| 法人累計 | `institutional-cumulative-flows` | `trust_cumulative_net_ratio`、`dealer_cumulative_net_ratio` |
| 外資持股 | `foreign-holdings` | `held_ratio`、`investable_ratio` |
| 融資融券 | `margin-metrics` | `margin_usage_ratio`、`margin_balance_change_pct`、`short_usage_ratio`、`short_balance_change_pct`、`short_cover_pressure` |
| 借券 | `short-interest-metrics` | `sbl_balance_change_pct`、`sbl_sell_repay_ratio` |
| 股權集中度 | `shareholding-concentrations` | `large_holder_ratio`、`small_holder_ratio`、`concentration_spread` 與各自的 `_wow` |

- 實際使用哪些欄位，由 step-9 的 `FeatureSchema` 決定；這張表是允許的範圍，不是必須全用。
- 以股數或金額表示的原值（例如 `foreign_net`），在橫斷面轉換前要先除以規模。除法屬於本專案的轉換，分母必須也是 canonical 輸入，例如 `foreign-holdings.issued_shares`。

## 3. 本專案的轉換（step-10、step-11）

- 橫斷面：排名、百分位、z-score、winsorize、缺值處理。只在單一 cohort 的股票池內計算。
- 同分處理：依股票代號。
- 規模標準化：原值 ÷ canonical 分母（見上）。
- 交互作用與複合特徵：step-11 定義。
- **v1 不做**產業相對標準化（D16）。

## 4. Data Center 尚未提供的 canonical 指標（D21）

ROADMAP §3 把以下指標列為 canonical，但目前 Data Center 沒有提供：

| 指標 | 可能的來源 | 備註 |
|---|---|---|
| 報酬率、動能（例如 20、60、120 日報酬） | `adjusted-prices-pit` | 必須用還原價格算；用原始價格會在除權息日出現假跌 |
| 歷史波動度 | `adjusted-prices-pit` | 同上 |
| ROA、毛利率、營業利益率 | `financial-reports` | 財報欄位的比率 |

step-9 之前對每一項決定：向 Data Center 申請（優先），或寫 ADR 後在本專案實作。v1 可以先不用這些特徵開始。

## 5. 禁止的做法

- 從 `daily-prices` 自己算均線、RSI 等 Data Center 已提供的指標。
- 從 `corporate-actions` 自己還原價格（D4）。
- 使用預測 EPS（v1 不依賴 `stock-eps-model`）。
- 使用未來資料：任何標籤、未來報酬或 `label_available_at` 晚於 T_C 的值都不能當特徵（step-9 的 registry 拒絕）。
- 使用 `/v1/stocks` 的 `industry` 當特徵（D16）。
