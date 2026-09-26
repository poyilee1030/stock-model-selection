# stock-model-selection ROADMAP

## 1. 專案目標

`stock-model-selection` 使用 `stock-data-center` 提供、符合 PIT（point-in-time，時點正確）的觀測資料與 canonical 衍生資料，訓練選股模型、對候選股票排名，並評估這些排名。

第一版（v1）刻意**不**使用 `stock-eps-model`。

核心原則：

> Data Center 擁有可重用的 canonical 指標。
> Model Selection 擁有排名專用的轉換、未來報酬標籤、訓練、排名與回測。

---

## 2. v1 資料來源

允許使用的 Data Center 輸入：

```text
歷史股票池（historical universe）
每日行情
月營收
財報 / XBRL 資料
歷史實際 EPS
集保（TDCC）
法人 / 籌碼原始資料
融資融券 / 借券（SBL）
市場指數
公司行動（corporate actions）
還原權息價格（adjusted-prices-pit）
官方評價指標（本益比等）
canonical 衍生資料集
```

v1 不使用預測 EPS。

### Data Center API

只透過 HTTP 存取，唯讀。

```text
base URL   環境變數 STOCKDC_BASE_URL   （區網位址；放在 .env，不進 repo）
API key    環境變數 STOCKDC_API_KEY    （放在 .env，絕不 commit）
驗證       每個請求都帶 header  X-API-Key: <key>

GET /v1/datasets
    目錄：name、kind（observed | derived | derived_on_demand）、keys、period、
    columns、sources、各來源未提供的欄位（unsourced），衍生資料集另有
    derivation 區塊（dataset_code、derivation_version、formula、inputs、
    日曆慣例、價格調整慣例）

GET /v1/datasets/{name}?start=YYYY-MM-DD&end=YYYY-MM-DD[&stock_id=2330&stock_id=2317]
    [&information_as_of=<含時區位移的 ISO-8601>&knowledge_as_of=<含時區位移的 ISO-8601>]
    [&system_as_of=<含時區位移的 ISO-8601>]
    start/end 必填；以資料集的 period 欄位過濾
    不帶 stock_id 時：每個請求最多 31 天
    每個請求最多 200 個 stock_id
    省略的 *_as_of 參數預設為現在（列在 pit.defaulted）
    information_as_of / knowledge_as_of：市場 PIT（該時點前已公開、且已被記錄）
    system_as_of：系統 PIT，Data Center 在該時點前已記錄的資料，不論是否已公開；
        不可與 information_as_of 或 knowledge_as_of 並用
    已儲存的衍生資料集只接受 knowledge_as_of = latest
    其他參數：source（可重複）、statement / account_code（financial-reports）、
        view = as_of | rolling（technical-indicators-pit）
    adjusted-prices-pit 與 technical-indicators-pit：每個請求只能一個 stock_id

GET /v1/stocks[?stock_id=2330][&market=sii|otc][&date=YYYY-MM-DD]
    上市（sii）與上櫃（otc）普通股：今日清單上的所有股票，加上 2020-01-02 以來
    下市的所有股票；不含 ETF、特別股、TDR、權證、創新板股票
    每列：stock_id、name、industry、market、listed_on、provenance、
         listings [{market, listed_on, delisted_on, provenance}]
    一段掛牌期間（span）從 listed_on 到 delisted_on 前一天；上櫃轉上市會有兩段
    listed_on 為 null：掛牌早於交易所掛牌資料表的起點
        （上市 2001-01-03 以前、上櫃 2005 年以前）
    date：回傳掛牌期間涵蓋該日的股票；最早 2020-01-02
    不是 PIT：原地更新，沒有 available_at / recorded_at，也沒有 *_as_of 參數
    industry 是今日的產業分類；下市股票為 null

GET /v1/trading-days?start=YYYY-MM-DD&end=YYYY-MM-DD
    證交所交易日，附 provenance；不是 PIT（交易所修改行事曆時原地更正）

GET /openapi.json
    機器可讀的 API 描述
```

回應結構（2026-09-25 驗證）：

```text
dataset, pit {mode, information_as_of, knowledge_as_of, defaulted, aliases}, query, rows
observed 列：   recorded_at、available_at、provenance {fetch_id, raw_sha256}
derived：       最上層 derivation {dataset_code, derivation_version, ...}、inputs（"latest"），
                列帶 computed_at、available_at
derived_on_demand（technical-indicators-pit）：
                最上層 view（"as_of" | "rolling"），列帶 information_as_of、
                input_count、input_fingerprint
adjusted-prices-pit：
                最上層 events [{ex_date, event_type, close_before, reference_price,
                factor, available_at, recorded_at, provenance, ...}]，列出所有調整到
                回傳列的事件；列帶原始 open/high/low/close_price、adjustment_factor、
                adjusted_open/high/low/close_price，沒有 available_at / recorded_at
financial-reports 列：巢狀 facts [{statement, account_code, concept, period_start,
                period_end, unit, value}]
錯誤：          HTTP 400，內容 {"detail": "..."}
```

已驗證的 PIT 語意（2026-09-25 驗證）：

```text
information_as_of 以 available_at 過濾列
    例：2330 在 2024-07-02 的日價格 available_at 為 2024-07-02T19:00Z（台北時間 D+1 03:00）
各資料集的 available_at 規則（2026-09-26 實測，完整表見 docs/contracts/time-and-cohort.md）：
    日頻資料（日價格、法人、融資券、借券、官方評價、外資持股、指數）：D+1 03:00
    集保股權分散：快照日後的週日 12:00
    月營收：公布日 23:59:59
    公司行動：除權息日 00:00
    財報：2025 Q3（含）以前每季所有股票共用同一個保守日期（法定期限當天或之後
        第一個工作日 23:59:59）；2025 Q4 起為各股實際公布時間
knowledge_as_of 以 recorded_at 過濾列
    歷史資料是 2026 年回補的，所以歷史時點的 knowledge_as_of 回傳 0 列
實體化（materialized）衍生資料集回報 inputs = "latest"：數值由最新版的輸入計算，
    只有「列是否可見」依 available_at 過濾
technical-indicators-pit 在完整 PIT 下即時計算指標
adjusted-prices-pit 在完整 PIT 下即時計算調整因子（市場 PIT 或系統 PIT 皆可）
```

還原權息價格（adjusted-prices-pit，2026-09-26 驗證）：

```text
向後調整、含息（total return）：事件因子 = reference_price / close_before；某交易日的
    adjustment_factor 是它之後、到 PIT 情境看得到的最後一筆價格為止，所有可見事件
    因子的乘積；最後一筆價格不調整
交易所參考價已扣除現金股利，所以用調整後序列算出的報酬是總報酬（股利再投入）；
    不提供只調價、不含息的序列
成交量不調整
事件可見時點：corporate_action_ex_date@1（除權息日當天 00:00 台北時間）；
    價格可見時點：exchange_daily_settled@1（D+1 03:00 台北時間）
    例：2330 在 2024-06-15 時點下，2024-06-13 除息（因子 0.99615）調整 2024-06-12
    及更早的價格；2024-09-12 的除息尚不可見
涵蓋除權 / 除息、現金減資、減資彌補虧損、變更面額
    （例：2327 在 2025-08-25 變更面額，因子 0.25）
每個來源一條序列：上櫃轉上市會有兩條序列，需指定 source
缺 reference_price 或 close_before 的事件，會讓它之前所有的 adjustment_factor 變成 null
沒有成交的日子仍會回傳，價格為 null（例：8291 的 2025-08-12）
現金增資除權日，調整後收盤價單日變動可能超過 10%：
    這是參考價所反映的認購權價值
參考價取整到升降單位，所以除權息日的調整後報酬與 (收盤價 + 股利) / 前一日收盤價 - 1
    略有差異（2330 在 2024-06-13：1.4909% 對 1.4851%）
單一股票完整歷史（2330，2020-01-02 起，1627 列）約 0.2 秒回傳
```

2026-09-26 的資料集目錄：

```text
observed：  daily-prices, indices, official-valuations, institutional-flows,
            institutional-market-flows, foreign-holdings, margin-trading, securities-lending,
            shareholding-distributions, monthly-revenues, corporate-actions, financial-reports
derived（derivation_version 全為 v1）：
            technical-indicators, institutional-streaks, institutional-cumulative-flows,
            shareholding-concentrations, margin-metrics, short-interest-metrics, valuation-metrics
derived_on_demand：
            technical-indicators-pit, adjusted-prices-pit
```

涵蓋範圍與存活者偏差（2026-09-26 驗證）：

```text
歷史資料從 2020-01-02 開始（例：2330 日價格從 2020-01-02 起）
/v1/stocks 會列出下市股票，但各資料集仍只收集今日仍掛牌的股票：
    2448（2021-01-06 下市）沒有 2020 年的日價格
股票池本身正確，但下市股票沒有特徵也沒有標籤，所以在 Data Center 回補之前
    存活者偏差仍然存在
financial-reports 不含金融業公司的財報：/v1/stocks 的 industry 為金融保險業者
    共 42 檔（上市 31、上櫃 9，另 2 檔已下市：2809 京城銀、2823 凱基人壽）都沒有財報，例如 2881、2891 回傳 0 列；它們的 valuation-metrics（TTM EPS、PE、ROE）
    與任何財報衍生特徵都是 null
```

資料新鮮度（2026-09-26 檢查）：

```text
各資料集的最後日期落後今天約兩週：
    daily-prices、institutional-flows、margin-trading、securities-lending、
        official-valuations、foreign-holdings 與日頻衍生資料集：2026-09-11
    trading-days：2026-09-15（2026-09-14、09-15 已是交易日，但全市場沒有日價格）
    indices：2026-09-16；shareholding-distributions：2026-09-18
    monthly-revenues 到 2026-08 月營收；financial-reports 到 2026 Q2
歷史研究不受影響；production 模式要求資訊截止點前最後一個交易日的資料已存在
```

基準指數（indices，2026-09-26 驗證）：

```text
含息報酬指數皆從 2020-01-02 起：
    上市：twse_mi_index「報酬指數/臺灣證券交易所:發行量加權股價報酬指數」
    上櫃：tpex_index_summary「報酬指數:櫃買指數」
另有未含息的發行量加權股價指數、櫃買指數，以及上市櫃各產業報酬指數
```

---

## 3. Canonical 特徵與模型專屬特徵

### Data Center canonical 範例

```text
MA5/MA20/MA60
報酬率
歷史波動度
RSI/MACD（若已標準化）
營收月增率 / 年增率
TTM EPS
ROE/ROA/各項利潤率
股權集中度
融資融券使用率
放空 / 借券比率
canonical 評價指標
```

### Model Selection 擁有的範例

```text
橫斷面 z-score
百分位 / 排名轉換
相對於股票池的特徵
動能 × 品質交互作用
以排名為導向的複合特徵
模型專屬交互作用
```

不要重複實作 Data Center 的 canonical 公式。

---

## 4. 硬性不變條件

```text
不直接存取 DB/Redis
v1 不依賴 stock-eps-model
entry_date 絕不是資訊截止點（information cutoff）
歷史股票池必須符合 PIT
未來報酬只能是標籤，絕不能是特徵
目標 cohort 不能訓練自己
canonical Data Center 依賴必須記錄 derivation_version
回測器只吃凍結的排名 artifact
```

### 測試先行規則

每個 phase、每一項變更，都先寫測試再寫實作：

```text
1. 寫出會失敗的測試，把驗收條件 / 不變條件編碼進去
2. 執行並確認它們因預期的原因而失敗
3. 寫出讓測試通過的最小實作
4. 在測試全綠的狀態下重構
```

- 修 bug 從一個能重現該 bug 的回歸測試開始。
- 資料洩漏與 PIT 不變條件，在被保護的程式碼存在之前，先以失敗的測試形式存在。
- 只加實作、沒有先寫測試的 PR 視為未完成。

### Step 規則

- 每個 phase 以一個或多個 step 交付。一個 step = 一個 branch（`step-N`）= 一個 PR，標題為 `step-N: <一行目標>`。
- PR 標題與描述使用繁體中文撰寫。`step-N:` 前綴、程式識別字、檔案路徑、指令輸出保持原樣。
- 目標大小：每個 step 最多 800 行實作程式碼，不含測試、測試 fixture 與文件。
- 預估超過 800 行的 step，拆成 `step-N-a`、`step-N-b`、`step-N-c`……每一部分都能獨立合併，並帶有自己的測試。
- 未拆分且超過 800 行的 step，只有在其條目中寫明 `Size exception: <理由>` 且理由充分時才允許。
- 本 roadmap 中的預估是規劃數字。每個 step 開始時重新評估；若實作途中超過 800 行，停下來拆分，不要合併過大的 PR。
- 超出某 step 範圍的工作，加到後面的 step，不要順手修。

---

## 5. Repository 結構

```text
stock-model-selection/
├── README.md
├── ROADMAP.md
├── pyproject.toml
├── .github/
│   └── workflows/
├── src/
│   └── stock_model_selection/
│       ├── config/
│       ├── domain/
│       ├── data/
│       │   ├── client.py
│       │   ├── schemas.py
│       │   ├── universe.py
│       │   ├── dataset_builder.py
│       │   └── provenance.py
│       ├── features/
│       │   ├── transforms.py
│       │   ├── cross_sectional.py
│       │   ├── interactions.py
│       │   └── builder.py
│       ├── labels/
│       │   └── forward_return.py
│       ├── training/
│       ├── ranking/
│       ├── backtest/
│       └── artifacts/
├── tests/
└── docs/
    ├── contracts/
    ├── adr/
    └── analysis/
```

---

## 6. Step 總覽

行數是實作程式碼的規劃預估，不含測試。
每個 step 開始時重新評估（見 §4 的 Step 規則）。

| Step | Phase | 目標 | 預估行數 | 依賴 |
|---|---|---|---|---|
| step-1 | 0 | 時間與 cohort 語意契約 | 0（文件） | — |
| step-2 | 0 | 資料依賴、所有權、artifact 契約；待決事項 | 0（文件） | step-1 |
| step-3 | 1 | Repo 骨架、基礎 CI、靜態邊界守衛 | ~250 | step-2 |
| step-4 | 1 | PIT 與 cohort 領域模型 | ~450 | step-3 |
| step-5-a | 1 | Data Center client 介面與回應 schema | ~600 | step-4 |
| step-5-b | 1 | 強制 PIT 的假 Data Center client | ~400 | step-5-a |
| step-6 | 1 | 真實 Data Center SDK adapter | ~300 | step-5-a（平行線） |
| step-7 | 2 | 符合 PIT 的歷史股票池 | ~350 | step-5-b |
| step-8-a | 3 | 資料集請求規格與符合 PIT 的抓取 | ~450 | step-7 |
| step-8-b | 3 | Cohort panel 組裝與資料集 provenance | ~450 | step-8-a |
| step-9 | 4 | 特徵 schema 與 registry | ~350 | step-8-b |
| step-10 | 4 | 橫斷面轉換 | ~400 | step-9 |
| step-11 | 4 | 交互作用項、複合特徵、特徵建構器 | ~450 | step-10 |
| step-12 | 5 | 未來報酬標籤計算 | ~450 | step-5-b |
| step-13 | 5 | 標籤資格閘門 | ~250 | step-12 |
| step-14 | 6 | 訓練資料集組裝器 | ~450 | step-11, step-13 |
| step-15 | 6 | 訓練 manifest 與資料集雜湊 | ~350 | step-14 |
| step-16 | 7 | Walk-forward 排程與評估指標 | ~550 | step-15 |
| step-17 | 7 | 模型訓練器與 walk-forward 執行器 | ~500 | step-16 |
| step-18 | 8 | 模型 artifact | ~450 | step-17 |
| step-19 | 9 | 排名產生與不可變的排名 artifact | ~500 | step-18 |
| step-20 | 10 | 基於凍結排名的回測引擎 | ~550 | step-19 |
| step-21 | 10 | 基準比較與績效報告 | ~400 | step-20 |
| step-22 | 11 | 舊輸出匯入與比較工具 | ~400 | step-21, step-6 |
| step-23 | 11 | 歷史資料洩漏案例研究 | ~300 + 文件 | step-22 |
| step-24 | 12 | CLI | ~500 | step-21 |
| step-25 | 13 | 永久守衛整併 | ~250 | step-24 |

平行線：

```text
step-6            可與 step 7–21 平行進行（它們都對假 client 開發）；
                  必須在 step-22 之前合併。
step-12..13       只依賴 step-5-b，可與 step 7–11 平行進行。
```

---

# 7. Phase 0 — 契約凍結

定義：

```text
cohort 識別
playbook date
資訊 / 知識 / 系統截止點（information / knowledge / system cutoffs）
進場 / 出場日
標籤期間（horizon）
標籤可用時點
股票池語意
canonical Data Center 依賴
模型專屬特徵的所有權
排名契約
回測契約
```

本 phase 必須解決（或明確延後到某個指定 step）的待決事項：

已解決：

```text
Data Center API 介面：HTTP API，見 §2「Data Center API」
歷史股票池來源：/v1/stocks?date=，見 step-7
交易日曆來源：/v1/trading-days（參考資料，不是 PIT）
還原權息價格：Data Center adjusted-prices-pit（向後調整、含息、PIT）；不要在本專案
    從 corporate-actions 自行調整
cohort 與時間語意（step-1）：月度 cohort；playbook date = 營收截止日（每月 10 日，
    非交易日順延）後的第一個交易日；資訊截止點 = playbook date 04:00 台北時間；
    出場日 = 下一個 cohort 進場日的前一個交易日；見 docs/contracts/time-and-cohort.md
歷史 cohort 的 knowledge_as_of（step-1）：兩種模式的 information_as_of 都是 cohort 的
    資訊截止點；production 的 knowledge_as_of 為執行時點，reconstruction 為記錄在
    artifact 中的明確重建時點；已儲存的衍生資料集只能用 latest
系統截止點（step-1）：只用於稽核與除錯，特徵、標籤、訓練、排名、回測都不得使用
營收未公布的股票（step-1）：M-1 月營收在 cohort 資訊截止點不可見的股票，當月不列入
    股票池；不維護主管機關延長期限的例外表
金融保險業（2026-09-26 使用者決定）：不在 v1 選股宇宙內；以 /v1/stocks 的
    industry = 金融保險業 排除，下市股票若保留 industry 同樣適用（2809、2823）
    已知缺口：部分下市金融股 industry 為 null（2867 三商壽、2888 新光金），無法由
    industry 辨識；目前下市股票沒有資料集歷史，不影響結果；Data Center 回補下市
    股票時，須同時補上 industry，或在 step-7 加入明列代號的排除清單
```

待決：

```text
實體化衍生資料集的重編風險（inputs = "latest"，例如 valuation-metrics 使用
    財報最新版本的數值）：改用 *-pit 版本、向 Data Center 申請一個，
    或逐資料集接受並記錄此風險
資料集的存活者偏差：資料集沒有下市股票的歷史；向 Data Center 申請回補，
    或在回補前記錄此偏差以及結果如何呈報
產業分類不是 PIT：/v1/stocks 給的是今日產業（下市股票為 null）；決定 step-10
    在 v1 是否使用產業相對標準化，若要，則向 Data Center 申請歷史產業分類
最早可用 cohort：歷史資料從 2020-01-02 開始；確定 walk-forward（step-16）的
    第一個訓練 cohort 與第一個評估 cohort
標籤與回測的價格慣例：adjusted-prices-pit 總報酬或原始價格、開盤或收盤，
    以及讀取標籤時使用的 PIT 情境（label_available_at 或 latest；出場之後的事件
    會等比例縮放進場與出場價格，所以只有價格或事件事後被更正才會改變比值）
基準指數：資料已具備（見 §2「基準指數」）；在上市報酬指數、櫃買報酬指數或兩者
    依股票池市值加權之間擇一，且與標籤的含息慣例一致
v1 使用的模型函式庫
artifact 儲存位置與格式
用於雜湊的資料集序列化格式
舊專案歷史輸出的取得方式（Phase 11 需要）
```

驗收條件：

- [ ] v1 排除預測 EPS
- [ ] 進場日絕不是資訊截止點
- [ ] 目標 cohort 不能訓練自己
- [ ] canonical 與模型專屬的所有權明確
- [ ] 每個 canonical 依賴都記錄 derivation version

## step-1: 時間與 cohort 語意契約

- 預估程式碼：0 行（僅文件）
- 交付物：`docs/contracts/time-and-cohort.md`
  - cohort 識別與 playbook date
  - 截止點一律是帶時區的時間戳，絕不是單純日期。Data Center 的可用時點精確到日內（D 日的日價格在 D+1 03:00 台北時間才可用），所以只有日期的截止點有歧義。
  - 對應到 Data Center 參數：資訊截止點 → `information_as_of`（過濾 `available_at`）；知識截止點 → `knowledge_as_of`（過濾 `recorded_at`）
  - 系統截止點 → `system_as_of`：Data Center 已記錄的資料，不論是否已公開。它不能與 `information_as_of` / `knowledge_as_of` 並用，所以要定義系統截止點在本專案的意義（例如只用於稽核與除錯，絕不用於特徵），或把它移除。
  - 兩種執行模式。Data Center 的歷史資料是 2026 年回補的，所以歷史時點的 `knowledge_as_of` 不會回傳任何列。

    | 模式 | `information_as_of` | `knowledge_as_of` | 意義 |
    |---|---|---|---|
    | production（正式） | 該 cohort 的資訊截止點 | 執行時間 | 真正的 PIT |
    | reconstruction（重建） | 該 cohort 的資訊截止點 | 重建時間 | 當時已公開的資料，以現在的紀錄為準 |

    重建模式會看到 cohort 截止點之後才記錄的更正；把這點列為已知限制，並將兩種模式對應到排名 artifact 的種類（`production` / `reconstruction`，step-19）。
  - 兩個 PIT 層級，在此定義，並於 step-2 逐資料集選定：
    - 列層級 PIT：某列是否可見，依 `available_at` 判斷
    - 值層級 PIT：某個數值是由哪些輸入版本算出來的。實體化衍生資料集回報 `inputs = "latest"`，所以只達到列層級 PIT。
  - 進場 / 出場日與標籤期間
  - `label_available_at` = 出場價格的 `available_at`（例：在 D 日收盤出場 → D+1 03:00 台北時間）
  - 股票池語意（僅資格規則；資料來源於 step-2 決定）
  - 以真實 Data Center `available_at` 值走過一個月度 cohort 的時間軸，包含：
    - D 日的日價格：D+1 03:00 台北時間可用
    - 月營收約在次月 10 日公布（2330 的 2024 年 6 月營收：2024-07-10 23:59 台北時間）
    - 季報（2330 的 2024 Q1：2024-05-15 23:59 台北時間），以及 2–3 月公布的 Q4 年報
- 不在範圍內、於 step-2 決定：各資料集必須達到的 PIT 層級、股票池資料來源、價格慣例（還原或原始、開盤或收盤）。
- 測試先行：不適用（僅文件）。這裡寫下的不變條件會成為 step-4 最先失敗的測試。
- 決議：production 模式的 `information_as_of` 改為 cohort 的資訊截止點（原為執行時間），讓兩種模式只差在 `knowledge_as_of`；詳見契約 §5。
- 驗收：
  - [x] 明確指出進場日不是資訊截止點
  - [x] 每個截止點都是帶時區的時間戳
  - [x] 每個截止點都對應到一個 Data Center 參數，或說明沒有對應參數時的意義
  - [x] 定義正式與重建兩種模式，並寫明重建模式的限制
  - [x] 定義列層級與值層級 PIT
  - [x] 寫明目標 cohort 的排除規則（自己的列、之後的 cohort、標籤尚未完整的較早 cohort）
  - [x] 以出場價格的 `available_at` 定義 `label_available_at`

## step-2: 資料依賴、所有權與 artifact 契約

- 預估程式碼：0 行（僅文件）
- 交付物：
  - `docs/contracts/data-dependencies.md`：每個使用到的 Data Center 資料集，附 `dataset_code`、要求的 `derivation_version`、PIT 查詢語意，以及它必須達到的 PIT 層級（列層級或值層級，於 step-1 定義）
  - `docs/contracts/feature-ownership.md`：canonical 與模型專屬的對照表
  - `docs/contracts/ranking.md`、`docs/contracts/backtest.md`
  - `docs/adr/0000-template.md`：任何重新實作 canonical 指標都必須使用的 ADR 範本
  - `docs/decisions.md`：上列每個待決事項的決議
- 驗收：
  - [ ] v1 排除預測 EPS
  - [ ] canonical 與模型專屬的所有權明確
  - [ ] 每個 canonical 依賴都列出其 derivation version
  - [ ] 每個待決事項都已解決或延後到指定的 step

---

# 8. Phase 1 — Repository 骨架與 Data Center 邊界

建立：

```text
PIT / cohort 領域模型
Data Center client
回應 schema
derivation metadata
假 client
直接存取 DB 的守衛
不依賴 EPS 的守衛
基礎 CI
```

驗收條件：

- [ ] 不存取 DB/Redis
- [ ] 不依賴 stock-eps-model
- [ ] Data Center client 可被 mock
- [ ] 尚未開始訓練

## step-3: Repository 骨架、基礎 CI、靜態邊界守衛

- 預估程式碼：~250 行
- 內容：
  - `pyproject.toml`（套件 metadata、pytest、ruff、mypy）、依 §5 的 `src/` 結構、附誠實現況說明的 README
  - 每個 PR 都執行 lint、型別檢查與 pytest 的 CI workflow。基礎 CI 放在這裡而不是 Phase 13，讓之後每個 step 都在 CI 下執行。
  - 掃描 `src/` 與 `pyproject.toml` 的靜態守衛：
    - 禁止的 import：PostgreSQL driver、SQLAlchemy、Redis client、`stock-eps-model` 套件 / client
    - 原始 SQL 語句樣式與 Data Center 資料表名稱
- 測試先行：每個守衛都拿刻意違規的 fixture 檔案測試，必須在這些檔案上失敗。
- 驗收：
  - [ ] 不存取 DB/Redis
  - [ ] 不依賴 stock-eps-model
  - [ ] 骨架上 CI 全綠

## step-4: PIT 與 cohort 領域模型

- 預估程式碼：~450 行
- 內容：
  - `PitContext`（資訊 / 知識 / 系統截止點，含先後順序驗證）
  - `Cohort`（id、playbook date、進場 / 出場、期間、`label_available_at`）
  - `DerivationRef`（`dataset_code`、`derivation_version`）與 provenance 紀錄型別
  - 抓取特徵的 API 只接受 `PitContext`，絕不接受單純日期
- 測試先行：
  - 缺 PIT 情境時拋出例外
  - 從 `entry_date` 建立 `PitContext` 時拋出例外
  - 截止點順序違規時拋出例外
  - 沒有版本的 `DerivationRef` 拋出例外
  - `docs/contracts/time-and-cohort.md` §12 列出的不變條件，包括 playbook date、出場日與 `label_available_at` 的日曆計算

## step-5-a: Data Center client 介面與回應 schema

- 預估程式碼：~600 行
- 拆分理由：完整的 client 邊界（介面、schema、假 client）預估約 1000 行。
- 內容：
  - `DataCenterClient` protocol：每個 v1 資料來源（§2）一個方法，加上 `/v1/stocks` 與 `/v1/trading-days`。特徵資料方法接受 `PitContext`，對應到 `information_as_of` / `knowledge_as_of`。給標籤 / 回測用的成交價、公司行動與指數方法接受明確日期；還原權息價格方法（`adjusted-prices-pit`，每次呼叫一檔股票）另外接受明確的 `information_as_of`，並保留 `events` 區塊。
  - 依 §2「Data Center API」的回應 schema：`pit` 區塊、帶 `recorded_at`、`available_at`、`provenance` 的 observed 列；帶 `derivation` 區塊的衍生回應；financial-reports 的巢狀 `facts`
  - Data Center 回傳的 `pit` 區塊保存在 provenance 中；若回應的 `pit.defaulted` 列出呼叫端有提供的截止點，則拒絕該回應
  - 錯誤型別：缺 derivation version、PIT 違規、缺 provenance
- 測試先行：
  - 沒有 `derivation_version` 或 provenance 的回應被拒絕
  - 回應回報截止點被預設的特徵請求被拒絕
  - 沒有任何特徵資料方法接受 `entry_date`

## step-5-b: 強制 PIT 的假 Data Center client

- 預估程式碼：~400 行
- 內容：
  - 記憶體內的 fixture 儲存。每一列都有可用時間戳，假 client 只回傳在知識截止點可見的列。少了這個，資料洩漏測試什麼都偵測不到。
  - fixture 建構器：掛牌 / 下市、有公布延遲的月營收、延後公布的季報 / 年報、價格、公司行動、調整因子會隨事件變為可見而改變的還原權息價格
  - 故障注入：錯誤的 derivation version、缺 provenance
- 測試先行：
  - 截止點之後才公布的列被隱藏
  - 能重現 step-1 的營收延遲與 Q4 時間軸
- 驗收：
  - [ ] Data Center client 可被 mock
  - [ ] 尚未開始訓練

## step-6: 真實 Data Center SDK adapter

- 預估程式碼：~300 行
- 依賴：step-5-a
- 內容：
  - 透過 §2 的 HTTP API 實作 `DataCenterClient` 的 adapter
  - 設定來自 `STOCKDC_BASE_URL` 與 `STOCKDC_API_KEY`；每個請求都帶 `X-API-Key`；repo 裡不放任何機密
  - 在 API 限制內切分請求：每個請求最多 200 個 stock_id，不帶 stock_id 時每個請求最多 31 天；結果以確定性方式合併
  - HTTP 400 的 `detail` 以型別化錯誤拋出；不做會改變查詢內容的靜默重試
  - 把回應對應到 schema；逐一驗證每個回應的 `derivation_version`
- 測試先行：以錄製的回應做契約測試（CI 中不連網）；另有一個可選的線上 smoke test，加上標記並在 CI 中跳過。
- 平行線：step 7–21 對假 client 開發。本 step 必須在 step-22 之前合併。

---

# 9. Phase 2 — 符合 PIT 的歷史股票池

從 Data Center 建構歷史候選股票池。

不要使用今日的上市櫃清單。

驗收條件：

- [ ] 排除未來才掛牌的股票
- [ ] 之後才下市的股票，在適當時仍保有歷史資格
- [ ] 記錄股票池的 provenance

## step-7: 符合 PIT 的歷史股票池

- 預估程式碼：~350 行
- 內容：
  - `data/universe.py`：以 `GET /v1/stocks?date=<cohort 日期>` 產生某個 cohort 的股票池快照
  - `/v1/stocks` 不是 PIT（原地更新）。掛牌與下市日期是事後不會改變的事實，但快照仍記錄回應雜湊與 provenance，之後重建若有差異會被回報。
  - `/v1/stocks` 的 `industry` 是今日分類：不當作 PIT 特徵儲存
  - 資格過濾依 step-1 契約 §8：掛牌期間涵蓋 playbook date、M-1 月營收在資訊截止點可見、playbook date 前一個交易日有成交
  - 2020-01-02 之前的 cohort 明確失敗（超出 Data Center 涵蓋範圍）
  - 快照帶 provenance 與內容雜湊
  - 防禦性檢查：若 Data Center 回傳截止點之後才掛牌的股票，則失敗
  - 排除金融保險業：`industry` = 金融保險業 的股票不列入任何 cohort（Phase 0 決議）
- 測試先行（永久保留）：
  - 排除未來才掛牌的股票
  - 之後才下市的股票仍具資格（例：2448 在 2021-01-05）
  - 股票從下市日起被排除（2448 在 2021-01-06）
  - 上櫃轉上市的股票在兩段掛牌期間都保有資格
  - M-1 月營收在資訊截止點不可見的股票被排除（例：2024-07 cohort 排除 8 檔 2024-06 營收未公布的股票）
  - 金融保險業被排除（例：2881；已下市但保留 industry 的 2809 在下市前也被排除）
  - industry 為 null 的下市股票（2867、2888）若出現資料集歷史，測試失敗並提示處理排除規則
  - 歷史股票池漂移：歷史 cohort 絕不使用今日的上市櫃清單
  - 記錄 provenance

---

# 10. Phase 3 — 符合 PIT 的資料集建構器

使用：

```text
Data Center observed 資料集
Data Center canonical 衍生資料集
```

保留：

```text
PIT 情境
來源 provenance
derivation 版本
```

不要用 `entry_date` 抓取特徵資料。

每個 cohort 各自以正確的 PIT 建構；絕不先建一份當前狀態的資料集再依日期切片。

## step-8-a: 資料集請求規格與符合 PIT 的抓取

- 預估程式碼：~450 行
- 拆分理由：完整的資料集建構器預估約 900 行。
- 內容：
  - 宣告式資料集規格：observed 與 canonical 資料集，並釘選 derivation version（來自 step-2）
  - 每個 cohort 只透過 `PitContext` 抓取
  - `derivation_version` 缺少或不符時失敗
  - 縱深防禦：若任何回傳列在知識截止點不可見，則失敗
- 測試先行（永久的資料洩漏回歸測試，使用假 client）：
  - 進場日偷看未來
  - 月營收延遲公布
  - Q4 / 2–3 月的可見性
  - canonical derivation version 不符

## step-8-b: Cohort panel 組裝與資料集 provenance

- 預估程式碼：~450 行
- 內容：
  - as-of 對齊：每檔股票、每個資料集取最新的可見列，接到股票池快照上
  - 明確的缺值政策（不做超出契約的靜默向前填補）
  - 彙整 provenance：每個輸入的 `dataset_code` + `derivation_version`、Data Center provenance、PIT 情境
  - 確定性的序列化與資料集雜湊
  - 建構器 API 接受單一 cohort 的 `PitContext`
- 測試先行：
  - 相同輸入產生相同雜湊
  - provenance 不完整時失敗
  - 建構 cohort A 時，絕不讀取只有之後的 cohort 才看得到的資料

---

# 11. Phase 4 — 模型專屬特徵管線

本 phase 只擁有排名專用的轉換。

範例：

```text
橫斷面排名
z-score
產業 / 股票池標準化
交互作用項
複合排名特徵
```

不要重新實作 Data Center 的 canonical 指標。

驗收條件：

- [ ] canonical 輸入與模型專屬轉換明確分開
- [ ] 特徵 schema 有版本
- [ ] 記錄 derivation 版本
- [ ] 輸出具確定性
- [ ] 不使用預測 EPS

## step-9: 特徵 schema 與 registry

- 預估程式碼：~350 行
- 內容：
  - `FeatureSpec`：名稱、canonical 輸入（`dataset_code`、欄位）、轉換 id、參數
  - 帶版本與雜湊的 `FeatureSchema`
  - canonical 直通與模型專屬轉換之間明確分開
  - registry 拒絕：
    - 被標記為標籤 / 未來報酬的輸入
    - 預測 EPS
    - 與 canonical 指標（§3）重複的轉換，除非附上 ADR id
- 測試先行：任何規格變動都會改變 schema 雜湊，且每條拒絕規則都有一個失敗案例。

## step-10: 橫斷面轉換

- 預估程式碼：~400 行
- 內容：
  - `features/transforms.py`、`features/cross_sectional.py`：排名、百分位、z-score、winsorize、股票池 / 產業相對標準化、缺值處理
  - 只有在有 PIT 產業資料來源時才做產業相對標準化（Phase 0 待決事項「產業分類不是 PIT」）；不使用 `/v1/stocks` 的今日產業
  - 確定性的同分處理（依股票代號）
  - 純函式，只作用於單一 cohort 的 panel；絕不跨 cohort
- 測試先行：
  - 已知值測試
  - 確定性
  - 轉換只看得到給定 cohort 的列

## step-11: 交互作用項、複合特徵、特徵建構器

- 預估程式碼：~450 行
- 內容：
  - `features/interactions.py`：交互作用項與複合排名特徵
  - `features/builder.py`：把 registry 套用到 cohort panel，產生特徵矩陣與特徵 manifest（帶著 schema 版本與 derivation 版本）
- 測試先行：
  - 輸出具確定性
  - manifest 中有 derivation 版本
  - 不相容的特徵 schema 明確失敗

---

# 12. Phase 5 — 未來報酬標籤

定義：

```text
進場日
出場日
價格慣例
label_available_at
```

標籤只有在期間完整結束後才能用於訓練。

目標 cohort 絕不能訓練自己。

## step-12: 未來報酬標籤計算

- 預估程式碼：~450 行
- 內容：
  - `LabelSpec`：期間、價格慣例（來自 step-2）、`label_available_at`
  - 公司行動由 Data Center `adjusted-prices-pit`（向後調整、含息）處理；不要從 `corporate-actions` 自行實作調整
  - 報酬是在同一個 PIT 情境下讀取的調整後價格比值，所以之後的事件會等比例縮放兩端；進場或出場時的 `adjustment_factor` 或價格為 null，標籤為缺值而非零
  - 期間內停牌 / 下市的明確政策
  - 標籤是 `labels/` 中獨立的型別，不能傳進特徵建構器
- 測試先行：
  - 已知值報酬
  - 套用公司行動：期間內除息得到總報酬（2330 跨 2024-06-13），變更面額不影響報酬（2327 跨 2025-08-25）
  - 進場或出場時價格或 `adjustment_factor` 為 null，得到缺值標籤
  - 依契約計算 `label_available_at`
  - 期間內下市的政策

## step-13: 標籤資格閘門

- 預估程式碼：~250 行
- 內容：對目標 cohort C，回傳標籤可用於訓練的 cohort，以及排除理由。排除：
  - C 本身
  - 所有之後的 cohort
  - `label_available_at` 晚於 C 截止點的較早 cohort（依 step-1 定義）
  - 標籤所需價格在 C 的 PIT 情境下查不到的 cohort（production 模式下資料擷取落後）
  - 依 step-1 的日曆，最近可訓練的是 C-1
- 測試先行（永久保留）：
  - 目標 cohort 自我訓練
  - 未完整的未來報酬標籤
  - 排除之後的 cohort
- 雖然與 step-12 合計不到 800 行，仍分開：這是 P0 的資料洩漏閘門，需要獨立審查。

---

# 13. Phase 6 — 訓練資料集契約

合併：

```text
符合 PIT 的股票池
canonical Data Center 特徵
模型專屬轉換
符合資格的歷史未來報酬標籤
```

Manifest 包含：

```text
資料集雜湊
目標 cohort
PIT 情境
canonical derivation 版本
特徵 schema 版本
符合資格的 cohort 範圍
被排除的 cohort 與理由
Data Center provenance
git commit
```

## step-14: 訓練資料集組裝器

- 預估程式碼：~450 行
- 內容：
  - 對目標 C：逐一獨立建構每個符合資格的 cohort（step 8、11），並接上其標籤（step-12），以 step-13 過濾
  - C 的推論矩陣另外建構，只有特徵
  - 以下每一種情況都明確失敗：
    - 訓練資料中出現目標 cohort 的列
    - 未完整的標籤
    - 各 cohort 的 derivation 版本不一致
    - 特徵 schema 不一致
- 測試先行：注入目標列、混用 derivation 版本、未完整標籤，各自都會失敗。

## step-15: 訓練 manifest 與資料集雜湊

- 預估程式碼：~350 行
- 內容：
  - 含上列所有欄位的 manifest，包括 git commit 與被排除的 cohort 及理由
  - 確定性的資料集雜湊
- 測試先行：
  - 缺任何 provenance 欄位即失敗
  - 相同輸入產生相同雜湊
  - manifest 可來回序列化

---

# 14. Phase 7 — Walk-Forward 選股訓練

使用擴展式 / 滾動式歷史訓練。

指標可包含：

```text
Spearman IC
Top-K 平均報酬
Top-K 命中率
覆蓋率
樣本數
若預測原始報酬，則加上迴歸指標
```

## step-16: Walk-forward 排程與評估指標

- 預估程式碼：~550 行
- 內容：
  - 排程：對目標 cohort 使用擴展式，以及明確記錄的滾動式視窗。訓練集來自 step-13，不另做 embargo 邏輯。
  - 排程不早於 Phase 0 確定的第一個訓練 cohort（Data Center 歷史資料從 2020-01-02 開始）
  - 上列指標
  - 主要評估不使用隨機切分
- 測試先行：
  - 排程絕不把目標 cohort 或之後的 cohort 放進訓練
  - 指標已知值

## step-17: 模型訓練器與 walk-forward 執行器

- 預估程式碼：~500 行
- 內容：
  - 模型介面與 v1 模型（函式庫來自 step-2）；超參數設定；固定 seed 與確定性設定
  - 執行器：對每個目標 cohort，組裝資料集 → 訓練 → 預測 → 評估，然後寫出執行報告
- 測試先行：
  - 相同 seed 與資料產生相同預測
  - 缺資料集 manifest 時執行器失敗

---

# 15. Phase 8 — 模型 Artifact

Artifact 必須包含：

```text
模型雜湊
目標 cohort
訓練截止點
PIT 情境
Data Center provenance
canonical 衍生依賴版本
訓練資料集雜湊
特徵 schema 版本
超參數
隨機 seed
git commit
套件版本
指標
```

## step-18: 模型 artifact

- 預估程式碼：~450 行
- 內容：
  - 序列化上列所有欄位；以內容定址儲存（位置來自 step-2）
  - 載入時驗證：特徵 schema 與 derivation 版本必須相符，否則明確失敗
- 測試先行：
  - 缺欄位即失敗
  - 被竄改的 artifact 無法通過雜湊檢查
  - 載入時 schema 不相容即失敗

---

# 16. Phase 9 — 排名 Artifact

產生不可變的排名 artifact。

包含：

```text
名次
股票
分數
是否入選
模型 ID
排名 ID
cohort
PIT 情境
特徵 schema
canonical derivation 版本
Data Center provenance
```

歷史重跑會建立新的 artifact；絕不覆寫原本的正式排名。

## step-19: 排名產生與不可變的排名 artifact

- 預估程式碼：~500 行
- 內容：
  - 用模型 artifact 為目標 cohort 評分；確定性的排名與入選規則
  - artifact 種類：`production` 或 `reconstruction`
  - production 執行前檢查資料新鮮度：資訊截止點前最後一個交易日（依 `/v1/trading-days`）若沒有日價格，或 `/v1/trading-days` 本身還沒涵蓋到截止點（交易日曆也會落後），則明確失敗，不產生排名
  - 只能寫入一次、拒絕覆寫的儲存；歷史重跑一律建立新的 reconstruction artifact
- 測試先行：
  - 覆寫嘗試失敗
  - 重跑建立新的排名 ID
  - 最後一個交易日缺日價格，或交易日曆未涵蓋到截止點時，production 排名失敗
  - 相同模型與資料產生相同排名

---

# 17. Phase 10 — 回測

回測器只吃凍結的排名。

它可以向 Data Center 取得：

```text
進場 / 出場價格
公司行動
基準 / 指數資料
```

它不可以：

```text
重建特徵
重跑模型
修補 PIT 問題
套用針對特定月份的資料洩漏補丁
```

## step-20: 基於凍結排名的回測引擎

- 預估程式碼：~550 行
- 內容：
  - 載入排名 artifact 並驗證其雜湊
  - 建構投資組合，進場 / 出場價格來自 Data Center；報酬來自 `adjusted-prices-pit`（總報酬），依 step-2 決定的價格慣例
  - 停牌 / 下市處理；成本模型
  - import 邊界守衛：`backtest/` 不得 import `features/`、`training/` 或資料集建構器
- 測試先行：
  - 被竄改的排名被拒絕
  - 守衛在禁止的 import 上失敗
  - 已知值投資組合報酬

## step-21: 基準比較與績效報告

- 預估程式碼：~400 行
- 內容：
  - 透過 Data Center `indices` 取得基準（來自 step-2）報酬，使用含息報酬指數
  - 超額報酬、累積報酬、回撤、周轉率、命中率
  - 帶排名 ID 與 provenance 的報告 artifact
- 測試先行：已知值指標，以及缺 provenance 的報告會失敗。

---

# 18. Phase 11 — 新舊回歸分析

必須涵蓋的歷史案例：

```text
進場日偷看未來
月營收延遲公布
Q4 / 2–3 月的可見性
歷史股票池漂移
目標 cohort 自我訓練
```

量化排名 / 績效的差異。

## step-22: 舊輸出匯入與比較工具

- 預估程式碼：~400 行
- 依賴：step-2（舊輸出的取得方式）、step-6（真實 Data Center 資料）
- 內容：
  - 以匯出的資料檔讀取舊專案的歷史排名 / 回測結果。不複製舊程式碼。
  - 對齊 cohort；計算排名相關係數、Top-K 重疊、績效差異
- 測試先行：以小型 fixture 匯出檔測試對齊與差異指標。

## step-23: 歷史資料洩漏案例研究

- 預估程式碼：~300 行 + 文件
- 內容：
  - 每個必要案例一份可重現、有量化差異的分析，放在 `docs/analysis/`
  - 每個案例也是一個永久的、以 fixture 為基礎的回歸測試，除非已在 step-7、step-8-a 或 step-13 涵蓋
- 驗收：
  - [ ] 五個案例全部量化並記錄

---

# 19. Phase 12 — CLI

建議的指令：

```text
stock-select build-universe
stock-select build-dataset
stock-select train
stock-select rank
stock-select backtest
stock-select inspect-manifest
```

使用明確的時間參數。

## step-24: CLI

- 預估程式碼：~500 行
- 內容：
  - 上列指令
  - 明確的時間參數（`--information-cutoff`、`--knowledge-cutoff`、`--system-cutoff`、`--cohort`）；沒有任何參數能讓進場日充當截止點
- 測試先行：
  - 缺 PIT 參數時被拒絕
  - 以假 client 做端到端 smoke test

---

# 20. Phase 13 — CI

基礎 CI（lint、型別檢查、測試）從 step-3 就已存在。本 phase 整併永久守衛。

永久守衛：

```text
不存取 DB/Redis
v1 不依賴 stock-eps-model
沒有 ADR 就不得重複實作 canonical 指標
entry_date 絕不控制特徵的可用性
目標 cohort 絕不訓練自己
排除未完整的標籤
歷史股票池符合 PIT
記錄 canonical derivation 版本
相同模型 / 資料 -> 相同排名
```

## step-25: 永久守衛整併

- 預估程式碼：~250 行
- 內容：
  - 橫跨 `data/`、`features/`、`labels/`、`training/`、`ranking/`、`backtest/` 的 import 分層契約
  - 資料洩漏回歸測試套件加上標記，每個 PR 都必須通過
  - 端到端確定性測試（相同模型 / 資料 → 相同排名）
  - 與 ADR 登錄表綁定的 canonical 重複實作守衛
  - `docs/` 中一張把上列每個守衛對應到其測試的表
- 驗收：
  - [ ] 上列每個守衛都對應到一個由 CI 強制執行的測試

---

# 21. 從舊專案遷移

可能可重用：

```text
排名規則
模型超參數
模型專屬交互作用
指標
投資組合規則
```

**不要**遷移：

```text
原始 SQL
DB 設定
手動的公布時間過濾
以進場日查詢特徵
現在由 Data Center 擁有的 canonical 指標
針對特定月份的 PIT 補丁
```

---

# 22. 完成定義

- [ ] 不直接存取 DB/Redis
- [ ] v1 不依賴 stock-eps-model
- [ ] 歷史股票池符合 PIT
- [ ] 可重用的 canonical 指標來自 Data Center
- [ ] 記錄 canonical 依賴的 derivation 版本
- [ ] 進場日絕不控制特徵的可用性
- [ ] 目標 cohort 絕不訓練自己
- [ ] 實作 walk-forward 訓練
- [ ] 排名 artifact 不可變
- [ ] 回測只吃凍結的排名
- [ ] 舊的資料洩漏案例有永久測試
- [ ] 每個 phase 都以測試先行實作
- [ ] 每個 step 都在 800 行實作以內，或附有書面的大小例外說明

---

# 23. 核心邊界

```text
stock-data-center：
    觀測資料
    canonical 可重用衍生資料
    derivation 版本

stock-model-selection：
    排名專用轉換
    未來報酬標籤
    訓練
    排名
    回測
```

第一版仍獨立於 `stock-eps-model`。
