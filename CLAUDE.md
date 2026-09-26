# CLAUDE.md

## 指令

- 環境：`uv sync`（Python 3.12，由 `.python-version` 指定）
- 檢查：`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy`、`uv run pytest`；這四項和 CI 相同，開 PR 前全部要過
- Data Center：`.env` 裡有 `STOCKDC_BASE_URL`、`STOCKDC_API_KEY`（`set -a && . ./.env && set +a`）；`.env` 不進 git

## 流程

- 一個 ROADMAP step = 一個 `step-N` branch = 一個 PR；PR 標題 `step-N: <一行目標>`，標題與描述用繁體中文
- 先寫會失敗的測試，確認它因預期原因失敗，再寫實作（ROADMAP §4）
- ROADMAP step 以外、只改文件的更新，可以直接 commit 並 push 到 `main`
- 沒有 `gh`：用 GitHub REST API 開 PR，token 取自 git remote URL，不要印出來，也不要改動 remote URL

## 慣例

- 文件（ROADMAP、`docs/`）用繁體中文；程式識別字、API 名稱、檔案路徑保持英文
- 決策寫在 `docs/decisions.md`，契約寫在 `docs/contracts/`；改動任何決策，同一個 PR 更新決策、契約與 ROADMAP
- `tests/guards/fixtures/` 是刻意違規的檔案，已排除在 ruff 與 mypy 之外，不要「修」它們

## 環境的坑

- `PYTHONPATH` 指向 ROS Humble 的 Python 3.10 site-packages，pytest 會載入 ROS 的 plugin 而失敗；已用 `--disable-plugin-autoload` 處理。新增需要的 pytest plugin 時，要在 `addopts` 用 `-p <plugin>` 明確載入
