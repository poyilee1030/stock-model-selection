# 決策紀錄

Phase 0 所有待決事項的決議。每一項寫明：決議、理由、影響的 step。
變更任何一項，都要在同一個 PR 更新本文件、相關契約與 ROADMAP。

- 最後更新：2026-09-26（step-2）
- 相關契約：
  - [`contracts/time-and-cohort.md`](contracts/time-and-cohort.md)：時間與 cohort 語意
  - [`contracts/data-dependencies.md`](contracts/data-dependencies.md)：使用的 Data Center 資料集
  - [`contracts/feature-ownership.md`](contracts/feature-ownership.md)：canonical 與模型專屬的分界
  - [`contracts/ranking.md`](contracts/ranking.md)：排名與入選
  - [`contracts/backtest.md`](contracts/backtest.md)：回測

## 總覽

| # | 事項 | 狀態 | 決定者 |
|---|---|---|---|
| D1 | Data Center API 介面 | 已決 | 使用者 |
| D2 | 歷史股票池來源 | 已決 | 使用者 |
| D3 | 交易日曆來源 | 已決 | 使用者 |
| D4 | 還原權息價格 | 已決 | 使用者 |
| D5 | cohort 與時間語意 | 已決（step-1） | 使用者 |
| D6 | 兩種執行模式與 `knowledge_as_of` | 已決（step-1） | 使用者 |
| D7 | 系統截止點 | 已決（step-1） | 使用者 |
| D8 | 營收未公布的股票 | 已決（step-1） | 使用者 |
| D9 | 金融保險業 | 已決 | 使用者 |
| D10 | 入選篩選：EPS 與成交量 | 已決 | 使用者 |
| D11 | 訓練母體與評估母體 | 已決 | 提議，使用者同意 |
| D12 | 價格慣例 | 已決 | 提議，使用者同意 |
| D13 | 基準指數 | 已決 | 提議，使用者同意 |
| D14 | 最早可用 cohort | 已決 | 提議，使用者同意 |
| D15 | 存活者偏差 | 已決 | 使用者 |
| D16 | 產業分類不是 PIT | 已決 | 提議，使用者同意 |
| D17 | 衍生資料集的重編風險 | 已決 | 提議，使用者同意 |
| D18 | 模型函式庫 | 已決 | 提議，使用者同意 |
| D19 | artifact 儲存位置與格式 | 已決 | 提議，使用者同意 |
| D20 | 雜湊用的序列化格式 | 已決 | 提議，使用者同意 |
| D21 | 報酬與波動度等 Data Center 尚未提供的 canonical 指標 | 延後到 step-9 | — |
| D22 | 投資組合檔數與權重 | 延後到 step-19 | — |
| D23 | 停牌 / 下市的標籤與回測政策 | 延後到 step-12 | — |
| D24 | 舊專案歷史輸出的取得方式 | 延後到 step-22 | — |

---

## D1–D4：資料介面

| # | 決議 |
|---|---|
| D1 | 只透過 HTTP API 存取 Data Center，唯讀；見 ROADMAP §2 |
| D2 | 歷史股票池來自 `/v1/stocks?date=`；見 step-7 |
| D3 | 交易日曆來自 `/v1/trading-days`；它是參考資料，不是 PIT |
| D4 | 還原權息價格使用 `adjusted-prices-pit`（向後調整、含息、PIT）；不在本專案從 `corporate-actions` 自行調整 |

## D5–D8：時間與 cohort（step-1）

完整定義見 [`contracts/time-and-cohort.md`](contracts/time-and-cohort.md)。

| # | 決議 |
|---|---|
| D5 | 每月一個 cohort。playbook date 是營收截止日（10 日，非交易日順延）之後的第一個交易日。資訊截止點 T_C 是 playbook date 當天 04:00 台北時間。出場日是下一個 cohort 進場日的前一個交易日 |
| D6 | 兩種模式的 `information_as_of` 都是 T_C。production 的 `knowledge_as_of` 是執行時點，reconstruction 的是記錄在 artifact 中的明確重建時點。已儲存的衍生資料集只能用 `latest` |
| D7 | 系統截止點只用於稽核與除錯 |
| D8 | M-1 月營收在 T_C 不可見的股票，cohort C 不列入股票池；不維護期限例外表 |

## D9：金融保險業

- **決議**：金融保險業不在 v1 的選股範圍內。`/v1/stocks` 的 `industry` 為「金融保險業」者一律排除。
- **理由**：`financial-reports` 不含金融業財報，這些股票沒有 EPS、ROE 等特徵。
- **已知缺口**：部分下市金融股的 `industry` 是 null（2867 三商壽、2888 新光金），無法由 industry 辨識。處理方式是 [`requests/industry-classifications.md`](requests/industry-classifications.md)；在那之前，由 step-7 的測試偵測。
- **影響**：step-7。

## D10：入選篩選（使用者決定）

以下兩條規則決定一檔股票**能不能進最後的名單**。它們不影響股票池本身（D11）。

| 規則 | 定義 |
|---|---|
| EPS | 過去四季 EPS 合計（TTM EPS）< 2 元者不入選。取 `valuation-metrics` 的 `ttm_eps`，在 P_C 前一個交易日、以 T_C 查詢。`ttm_eps` 為 null（四季財報未全部公布，例如新上市股票）者也不入選 |
| 成交量 | P_C 之前 7 個交易日的平均成交量 < 500 張（500,000 股）者不入選。7 個交易日依 `/v1/trading-days`；該股在某日沒有成交或沒有資料，當日以 0 計 |

- 「過去一年的 EPS」解讀為最近四季合計，不是上一個會計年度。
- `daily-prices` 的 `volume` 單位是股，上市與上櫃相同。已驗證：2330 在 2024-07-10 為 51,810,372 股；上櫃股票的 成交金額 ÷（成交量 × 收盤價）中位數為 1.000。
- 實測影響（股票池 → 通過篩選）：

| cohort | 股票池 | EPS ≥ 2 | 其中 TTM EPS 為 null | 均量 ≥ 500 張 | 兩者皆通過 |
|---|---|---|---|---|---|
| 2021-07 | 1538 | 702 | 38 | 808 | 404 |
| 2023-07 | 1598 | 756 | 39 | 789 | 397 |
| 2024-07 | 1639 | 735 | 42 | 920 | 416 |
| 2025-07 | 1675 | 772 | 57 | 594 | 333 |
| 2026-08 | 1768 | 790 | 70 | 713 | 395 |

- **影響**：step-19（入選規則）、step-16（評估母體）、step-20（回測只持有入選股票）。

## D11：訓練母體與評估母體

- **決議**：
  - **訓練**使用整個股票池（契約 time-and-cohort §8 的資格規則），不套用 D10 的篩選。
  - **評估**（Spearman IC、Top-K 報酬、命中率）只在通過 D10 篩選的股票上計算，因為那才是會被選的範圍。
  - 評估報告同時列出整個股票池上的 IC，作為參考。
- **理由**：使用者對訓練母體沒有意見。整個股票池的樣本約是篩選後的 4 倍，讓模型學到完整的橫斷面；最後的績效則只看實際會選的股票。
- **之後可以重新評估**：改成只用篩選後的股票訓練，屬於模型實驗，在 step-17 以設定切換並比較，不改契約。
- **影響**：step-14、step-16。

## D12：價格慣例

- **決議**：
  - 價格：`adjusted-prices-pit` 的還原價格（總報酬，股利再投入）。
  - 進場：P_C 的**開盤價**（`adjusted_open_price`）。
  - 出場：X_C 的**收盤價**（`adjusted_close_price`）。
  - 標籤：`adjusted_close(X_C) / adjusted_open(P_C) - 1`，兩個價格在同一次查詢中取得。
  - 讀取標籤的 PIT 情境：`information_as_of = label_available_at(C)`，`knowledge_as_of` 依執行模式（D6）。
- **理由**：
  - 原始價格在除權息日與面額變更日會產生假漲跌（2327 在 2025-08-25 一股拆四，原始價格報酬 −74%）。
  - 04:00 決策、09:00 開盤進場，比較貼近實際操作。
  - 出場之後的公司行動會等比例縮放進場與出場價格，比值不變；只有價格或事件事後被更正才會改變標籤。
- **代價**：X_C 收盤到 P_{C+1} 開盤之間的一個晚上，不算進任何 cohort 的報酬；回測在這段期間持有現金。
- **影響**：step-12、step-20。

## D13：基準指數

- **決議**：
  - 主要基準：`indices`，來源 `twse_mi_index`，名稱「報酬指數/臺灣證券交易所:發行量加權股價報酬指數」。
  - 次要基準（報告中並列）：來源 `tpex_index_summary`，名稱「報酬指數:櫃買指數」。
  - 基準報酬：`close(X_C) / close(P_C 前一個交易日) - 1`。
- **理由**：兩者都是含息指數，與 D12 的含息標籤一致，且都從 2020-01-02 起有資料。
- **已知差異**：這兩個報酬指數沒有開盤值（`open_value` 在這兩個來源屬於 unsourced），所以基準從前一日收盤起算，比投資組合多算 P_C 當天的開盤跳空。報告必須註明。
- **影響**：step-21。

## D14：最早可用 cohort

- **決議**：
  - 第一個訓練 cohort：2021-01。
  - 第一個評估 cohort：2023-01。它的訓練集是 2021-01 到 2022-12，共 24 個 cohort。
- **理由**：
  - Data Center 歷史從 2020-01-02 開始。
  - 240 日均線要累積 240 個交易日才有值：2330 的 MA240 從 2020-12-24 起有值，2021-01 cohort（P = 2021-01-12）可以用到。
  - 24 個月的訓練資料，是評估前的最低數量。
- **影響**：step-16。

## D15：存活者偏差

- **決議**：Data Center 會回補下市股票的資料集歷史（使用者確認）。
- **回補之前**：
  - 每份回測與評估報告都要註明「下市股票沒有歷史資料，結果有存活者偏差」。
  - 股票池本身仍依 `/v1/stocks` 正確包含下市股票。這些股票因為沒有營收資料，會被 D8 排除，所以結果不會出錯，只是有偏差。
- **回補之後**：重新執行所有 reconstruction，比較前後差異，並處理 D9 的已知缺口。
- **影響**：step-7、step-21、step-23。

## D16：產業分類不是 PIT

- **決議**：v1 不做產業相對標準化，也不用產業做任何特徵。
- **理由**：`/v1/stocks` 只有今天的產業分類。產業類別在 2023-07-03 改過一次，有 140 檔股票換了類別；下市股票的分類也是 null。
- **後續**：需求已寫在 [`requests/industry-classifications.md`](requests/industry-classifications.md)。拿到資料後，產業相對標準化以新的 step 加入。
- **影響**：step-10。

## D17：衍生資料集的重編風險

- **決議**：v1 接受已儲存衍生資料集只有列層級 PIT 的風險，逐資料集記錄在 [`contracts/data-dependencies.md`](contracts/data-dependencies.md)。
  - 技術指標改用 `technical-indicators-pit` 的 `view=rolling`，達到值層級 PIT，不用已儲存的 `technical-indicators`。
  - 主要風險是 `valuation-metrics`：它用財報的最新版本計算，公司重編財報時，歷史的 TTM EPS、ROE 會悄悄改變。D10 的 EPS 篩選也受影響。
  - 向 Data Center 申請 `valuation-metrics-pit`。拿到後改用，並在 step-22 比較差異。
- **理由**：財報重編不常見；其他衍生資料集的輸入是交易所每日資料，事後更正很少。
- **影響**：step-8-a、step-19。

## D18：模型函式庫

- **決議**：LightGBM。
- **理由**：表格資料的標準選擇，速度快，支援排名目標函數（LambdaRank）與迴歸目標。
- **影響**：step-17。

## D19：artifact 儲存位置與格式

- **決議**：
  - 位置：本機資料夾，由環境變數 `STOCKSEL_ARTIFACT_DIR` 指定，不在 git repo 內。
  - 命名：以內容的 SHA-256 定址，例如 `models/<sha256>/`、`rankings/<sha256>/`。
  - 寫入一次：已存在的路徑拒絕覆寫。
  - 每個 artifact 是一個資料夾，內含 `manifest.json` 與內容檔：
    - 模型：LightGBM 文字格式模型檔
    - 表格（資料集、排名、回測結果）：D20 的 Arrow IPC 檔
- **理由**：先求簡單。之後要搬到雲端儲存，只要換掉儲存層。
- **影響**：step-15、step-18、step-19。

## D20：雜湊用的序列化格式

- **決議**：資料集雜湊 = 對標準形式的 Arrow IPC stream 計算 SHA-256。標準形式：
  - 列依主鍵排序，例如 (`cohort_id`, `stock_id`)。
  - 欄位依 schema 的固定順序。
  - 移除 schema metadata，例如 pandas 附加的 metadata。
  - 不壓縮。
- **附帶規則**：manifest 記錄 `pyarrow` 版本。版本不同導致雜湊不同時，以「版本不同」回報，不當作資料不同。
- **影響**：step-8-b、step-15。

---

## 延後的事項

| # | 事項 | 延後到 | 需要什麼 |
|---|---|---|---|
| D21 | 報酬、動能、歷史波動度、ROA、利潤率 | step-9 | ROADMAP §3 把它們列為 Data Center 的 canonical 指標，但目前 Data Center 沒有提供。step-9 之前決定：向 Data Center 申請，或寫 ADR 後在本專案實作。v1 可以先不用這些特徵開始。見 [`contracts/feature-ownership.md`](contracts/feature-ownership.md) |
| D22 | 投資組合檔數 K 與權重 | step-19 | 使用者決定。契約先以參數表示，預設等權重 |
| D23 | 標籤期間內停牌或下市的處理 | step-12 | 提案見 [`contracts/backtest.md`](contracts/backtest.md) §5，step-12 定稿 |
| D24 | 舊專案歷史輸出的取得方式 | step-22 | 使用者提供舊專案位置與可匯出的輸出格式；若沒有舊輸出，Phase 11 改寫 |
