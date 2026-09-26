# 回測契約

回測如何從凍結的排名 artifact 算出績效。

- 狀態：step-2 定稿；停牌與下市的處理於 step-12 定稿（D23）
- 實作：step-20、step-21

## 1. 輸入與禁止事項

- 輸入：一串排名 artifact（每個 cohort 一個），載入時驗證雜湊。
- 可以向 Data Center 取得：進出場價格（`adjusted-prices-pit`）、基準指數（`indices`）。
- 不可以：重建特徵、重跑模型、修補 PIT 問題、套用針對特定月份的補丁。
- `backtest/` 不得 import `features/`、`training/` 或資料集建構器（step-20 的守衛）。

## 2. 持有期與價格（D12）

```text
進場  P_C 開盤，adjusted_open_price
出場  X_C 收盤，adjusted_close_price
      X_C = P_{C+1} 的前一個交易日
X_C 收盤到 P_{C+1} 開盤之間持有現金
```

- 每檔股票的報酬：`adjusted_close(X_C) / adjusted_open(P_C) - 1`，與標籤相同。
- 價格以 `information_as_of = label_available_at(C)` 取得，所以回測只能用到 `label_available_at` 已過的 cohort。

## 3. 投資組合

- 持有排名 artifact 中 `selected = true` 的股票，權重取 artifact 的 `weight`。
- K 與權重由排名 artifact 決定（D22），回測不改動。
- 每個 cohort 期初重新建立投資組合，期末全部賣出。

## 4. 交易成本

預設值，以設定調整；報告必須列出使用的值。

| 成本 | 預設 |
|---|---|
| 手續費 | 買、賣各 0.1425%，不打折 |
| 證券交易稅 | 賣出 0.3% |
| 滑價 | 0（v1 不模擬） |

- 每個 cohort 的淨報酬 = 毛報酬 − 買進成本 − 賣出成本。
- 因為每期全部換股，周轉率固定為 100%；step-21 另外計算「與上期重複持股的比例」。

## 5. 停牌與下市（D23，提案，step-12 定稿）

| 情況 | 提案 |
|---|---|
| X_C 當天停牌，沒有收盤價 | 以 X_C 之前最後一個有成交日的還原收盤價出場，並標記 |
| 持有期間下市 | 以最後一個交易日的還原收盤價出場，並標記；下市後的現金不再投入 |
| P_C 當天停牌，沒有開盤價 | 股票池只要求 P_C 前一日有成交，P_C 當天仍可能停牌。該股不進場，權重保留為現金，並標記 |
| `adjustment_factor` 為 null | 無法計算報酬；該股不進場，權重保留為現金，並標記 |

標籤（step-12）與回測使用同一套規則，不能各自定義。

## 6. 基準（D13）

- 主要：發行量加權股價報酬指數（`twse_mi_index`）。
- 次要：櫃買報酬指數（`tpex_index_summary`）。
- 基準報酬：`close(X_C) / close(P_C 前一個交易日) - 1`。這兩個指數沒有開盤值，所以比投資組合多算 P_C 的開盤跳空，報告必須註明。

## 7. 報告（step-21）

- 每個 cohort：股票池大小、通過篩選的檔數、入選檔數、毛報酬、淨報酬、兩個基準的報酬、超額報酬、命中率。
- 全期：累積報酬、最大回撤、年化報酬與波動度、與上期重複持股的比例。
- 必要註明：
  - 存活者偏差（D15），直到 Data Center 回補下市股票
  - 2025 Q3 以前的財報可見時點是保守日期（time-and-cohort §5）
  - 基準的開盤跳空差異（§6）
  - 股票池特別小的月份（time-and-cohort §8）
- 報告 artifact 帶有使用的排名 ID 與 provenance。
