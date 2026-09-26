# stock-model-selection

使用 `stock-data-center` 提供、符合 PIT（point-in-time，時點正確）的資料，訓練選股模型、對候選股票排名，並回測排名。v1 不依賴 `stock-eps-model`。

規劃見 [`ROADMAP.md`](ROADMAP.md)，決策見 [`docs/decisions.md`](docs/decisions.md)，契約見 [`docs/contracts/`](docs/contracts/)。

## 現況

| 範圍 | 狀態 |
|---|---|
| Phase 0：時間與 cohort 契約（step-1）、資料依賴與所有權契約（step-2） | 完成 |
| step-3：repo 骨架、基礎 CI、靜態邊界守衛 | 完成 |
| step-4：PIT 與 cohort 領域模型（`src/stock_model_selection/domain/`） | 完成 |
| 資料抓取、特徵、標籤、訓練、排名、回測 | **尚未開始**，目前沒有任何可執行的功能 |

目前有作用的程式只有兩塊：

- `src/stock_model_selection/domain/`：`PitContext`、交易日曆、`Cohort` / `LabelHorizon` 的日期計算、`DerivationRef`。只以 repo 內的交易日曆 fixture 測過，還沒有接上 Data Center。
- `tests/guards/` 的靜態守衛。

## 開發

需要 [uv](https://docs.astral.sh/uv/)。Python 版本由 `.python-version` 指定（3.12），uv 會自動安裝。

```bash
uv sync                      # 建立 .venv 並安裝開發工具
uv run ruff check .          # lint
uv run ruff format --check . # 格式
uv run mypy                  # 型別檢查（strict）
uv run pytest                # 測試
```

CI（`.github/workflows/ci.yml`）在每個 PR 與 push 到 `main` 時執行上面四項檢查。

## 靜態邊界守衛

`tests/guards/test_boundary.py` 掃描 `src/`、`pyproject.toml` 與 `uv.lock`，發現以下任一項就失敗：

| 規則 | 抓什麼 |
|---|---|
| `forbidden-import` | import PostgreSQL driver（psycopg 及其 `psycopg_c`、`psycopg_binary`、`psycopg_pool`，psycopg2、asyncpg、pg8000）、SQLAlchemy / SQLModel、Redis client（redis、aioredis、hiredis）、`stock_eps_model`；包括 `importlib.import_module("...")` 與 `__import__("...")` |
| `forbidden-dependency` | 上述套件出現在 `pyproject.toml` 的 dependencies、optional-dependencies、dependency-groups、`[tool.uv] dev-dependencies`，或出現在 `uv.lock`（間接依賴） |
| `raw-sql` | 字串中出現 SQL 語句（`SELECT … FROM`、`INSERT INTO`、`UPDATE … SET`、`DELETE FROM`、`CREATE/DROP/ALTER/TRUNCATE TABLE`）。全大寫的關鍵字一律算；其他大小寫要有語句結構才算，所以 `"Select a model from the registry"` 這類英文不會誤判。f-string 與字串相加會先組合再檢查；docstring 不檢查 |
| `data-center-table` | 字串中在 SQL 位置（`FROM`、`JOIN`、`INTO`、`UPDATE`、`TABLE` 之後）出現 Data Center 的資料表名稱，例如 `daily_prices` |

- 每條規則都有刻意違規的 fixture（`tests/guards/fixtures/violations/`），以及檢查誤判的乾淨 fixture（`tests/guards/fixtures/clean/`）。
- 守衛只解析檔案，不 import，所以 fixture 可以 import 沒有安裝的套件。
- Data Center 的實際資料表名稱我們看不到；清單取自 `/v1/datasets` 的資料集名稱（改成 snake_case）與 derivation 的 `dataset_code`。

## 已知的環境問題

- 若 `PYTHONPATH` 指向其他 Python 版本的 site-packages（例如 ROS 的 `/opt/ros/humble/lib/python3.10/site-packages`），pytest 會自動載入那裡的 plugin 而失敗。`pyproject.toml` 已設定 `--disable-plugin-autoload` 避開這個問題。
