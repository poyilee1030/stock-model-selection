# stock-model-selection ROADMAP

## 1. Project Goal

`stock-model-selection` is a standalone repository responsible for training stock-selection models, ranking candidate stocks, and evaluating the resulting strategy using PIT-safe data supplied by `stock-data-center`.

Version 1 intentionally does **not** depend on `stock-eps-model`.

Core flow:

```text
stock-data-center
        |
        | PIT-safe market/accounting data
        v
universe construction
        |
        v
feature engineering
        |
        v
forward-return label construction
        |
        v
walk-forward training
        |
        v
ranking / Top-K selection
        |
        v
backtest / evaluation
        |
        v
reproducible model + ranking artifacts
```

Core rule:

> `stock-data-center` decides what information was knowable at time T.  
> `stock-model-selection` decides how to rank stocks using only that information.

---

## 2. Version 1 Scope

Version 1 may use PIT-safe inputs from these families:

```text
daily price
technical indicators derived from PIT-safe prices
monthly revenue
historical actual financial statements
historical actual EPS
TDCC/shareholding data
historical security metadata/universe
```

Version 1 must NOT use:

```text
predicted EPS
stock-eps-model artifacts
future analyst estimates
future realized returns as features
```

A later feature-set version may add EPS predictions only after `stock-eps-model` is independently PIT-safe and its incremental value is evaluated.

Suggested feature schema naming:

```text
selection_features_v1_base
```

Future optional version:

```text
selection_features_v2_with_eps_prediction
```

---

## 3. Non-Goals

This repository does NOT own:

- market-data scraping
- MOPS / TWSE / TPEx / TDCC collection
- raw XBRL storage
- publication-time inference
- stock database schemas
- market/system PIT resolution
- EPS model training
- EPS prediction
- broker execution
- live order management

---

## 4. Hard Architecture Boundaries

### 4.1 No direct stock DB access

Forbidden:

```text
psycopg
asyncpg
direct SQLAlchemy connection to stock-data-center DB
raw SQL against Data Center tables
knowledge of Data Center table names
```

All market/accounting data must come from the `stock-data-center` API or SDK.

### 4.2 No dependency on `stock-eps-model` in v1

Do not add:

```text
eps_prediction_reader
stock_eps_model client
predicted_eps feature
```

during v1.

### 4.3 Information cutoff is not entry date

These concepts are separate:

```text
playbook_date
information_as_of
knowledge_as_of
entry_date
exit_date
```

`entry_date` is a trading concept.

It must never be used as the information-availability cutoff unless an explicit future design changes the contract.

### 4.4 Target cohort must never train itself

A cohort's future return label becomes eligible only after the entire label horizon has completed.

The model that ranks a cohort must be trained only on earlier label-eligible cohorts.

---

## 5. Temporal Model

For a market reconstruction:

```text
MarketPitContext
    information_as_of
    knowledge_as_of
```

For an exact Data Center system reconstruction:

```text
SystemPitContext
    system_as_of
```

Selection-specific dates:

```text
playbook_date
entry_date
exit_date
label_available_at
```

Example:

```text
playbook_date        = 2026-07-11
information_as_of    = 2026-07-10 23:59:59+08:00
knowledge_as_of      = 2026-07-10 23:59:59+08:00
entry_date           = 2026-07-13
exit_date            = next rebalance exit date
```

All selection features must use the declared PIT context.

They must not use `entry_date` to fetch feature data.

---

## 6. Target Repository Structure

```text
stock-model-selection/
├── README.md
├── ROADMAP.md
├── AGENTS.md
├── pyproject.toml
├── .env.example
│
├── src/
│   └── stock_model_selection/
│       ├── config/
│       ├── domain/
│       │   ├── pit.py
│       │   ├── cohort.py
│       │   ├── ranking.py
│       │   └── artifacts.py
│       ├── data/
│       │   ├── client.py
│       │   ├── schemas.py
│       │   ├── universe.py
│       │   ├── dataset_builder.py
│       │   └── provenance.py
│       ├── features/
│       │   ├── price.py
│       │   ├── technical.py
│       │   ├── revenue.py
│       │   ├── financial.py
│       │   ├── tdcc.py
│       │   └── builder.py
│       ├── labels/
│       │   └── forward_return.py
│       ├── training/
│       │   ├── split.py
│       │   ├── trainer.py
│       │   ├── evaluator.py
│       │   └── metrics.py
│       ├── ranking/
│       │   ├── scorer.py
│       │   └── selector.py
│       ├── backtest/
│       │   ├── engine.py
│       │   ├── portfolio.py
│       │   └── metrics.py
│       └── artifacts/
│           ├── manifest.py
│           ├── model_store.py
│           └── ranking_store.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── pit/
│   └── regression/
│
├── models/
├── outputs/
└── docs/
    ├── architecture.md
    ├── data_contract.md
    ├── feature_contract.md
    ├── label_contract.md
    ├── training_contract.md
    ├── ranking_contract.md
    ├── backtest_contract.md
    └── decisions/
```

---

## 7. Fixed Technology Stack

Unless amended by ADR + ROADMAP update:

```text
Python        3.12+
Pydantic      2.x
pandas
numpy
scikit-learn
LightGBM
httpx
pytest
joblib
```

Do not add stock-data DB drivers.

---

# 8. Phase 0 — Define Selection Contracts

## Goal

Freeze semantics before migrating old `strategies`, `models_selection`, or `backtester` code.

## Tasks

- [ ] Define cohort identity
- [ ] Define playbook date
- [ ] Define information cutoff
- [ ] Define knowledge cutoff
- [ ] Define entry/exit dates
- [ ] Define label horizon
- [ ] Define label availability
- [ ] Define candidate universe semantics
- [ ] Define feature families
- [ ] Define ranking output
- [ ] Define Top-K semantics
- [ ] Define training eligibility
- [ ] Define model artifact identity
- [ ] Define ranking artifact identity
- [ ] Define backtest contract
- [ ] Document known old leakage bugs intentionally removed

## Required Documents

```text
docs/architecture.md
docs/data_contract.md
docs/feature_contract.md
docs/label_contract.md
docs/training_contract.md
docs/ranking_contract.md
docs/backtest_contract.md
docs/decisions/
```

## Acceptance Criteria

- [ ] No direct stock DB access is allowed
- [ ] v1 explicitly excludes predicted EPS
- [ ] `entry_date` is never an information cutoff
- [ ] Feature PIT semantics are explicit
- [ ] Forward-return label eligibility is explicit
- [ ] Target cohort cannot train its own model
- [ ] Universe PIT semantics are explicit
- [ ] Backtest uses frozen ranking artifacts
- [ ] Known historical leakage bugs are documented as removed

---

# 9. Phase 1 — Repository Skeleton and Data Center Boundary

## Goal

Create the clean repository boundary before implementing model logic.

## Tasks

- [ ] Create `pyproject.toml`
- [ ] Add package structure
- [ ] Add typed configuration
- [ ] Add PIT context models
- [ ] Add cohort/date models
- [ ] Define Data Center client interface
- [ ] Define normalized response schemas
- [ ] Define provenance models
- [ ] Add fake/in-memory Data Center client
- [ ] Add architectural direct-DB guard tests

## Acceptance Criteria

- [ ] Repository imports without stock DB drivers
- [ ] No raw SQL exists
- [ ] Data Center client is mockable
- [ ] PIT/cohort types are explicit
- [ ] No EPS-model dependency exists
- [ ] Tests pass
- [ ] No model training exists yet

---

# 10. Phase 2 — PIT-Safe Historical Universe

## Goal

Construct the candidate universe that actually existed at the requested historical cutoff.

## Inputs

Potential Data Center inputs:

```text
security metadata
listed/delisted state
market
security type
trading status
price/liquidity history
```

## Rules

Do not build a historical universe from today's active-stock list.

A stock listed after `information_as_of` cannot appear.

A stock delisted later may still appear in earlier cohorts if it was eligible then.

## Acceptance Criteria

- [ ] Future listings are excluded
- [ ] Historically active later-delisted stocks remain eligible where appropriate
- [ ] Universe uses explicit PIT context
- [ ] Universe selection has provenance
- [ ] Universe output is deterministic for fixed PIT inputs

---

# 11. Phase 3 — PIT-Safe Base Dataset Builder

## Goal

Assemble PIT-safe normalized source data for a cohort.

No feature engineering beyond alignment yet.

## Data Families

Initial:

```text
daily price
monthly revenue
historical financials
historical actual EPS
TDCC
security metadata
```

## Rules

Every request must carry the cohort's PIT context.

Missing historical data remains missing.

Do not fetch using `entry_date`.

## Required Metadata

Each build should record:

```text
cohort_id
playbook_date
PIT context
entry_date
Data Center query/snapshot IDs
source coverage
security count
build git commit
```

## Acceptance Criteria

- [ ] Every Data Center request carries PIT context
- [ ] No request uses entry date as feature cutoff
- [ ] Missing data is not future-filled
- [ ] Dataset has provenance
- [ ] Same Data Center responses produce deterministic output

---

# 12. Phase 4 — Feature Pipeline v1

## Goal

Build `selection_features_v1_base`.

## Feature Families

### Price / technical

Potential features:

```text
return_5d
return_20d
return_60d
MA5
MA20
MA60
price_vs_ma
volatility
volume
volume_ratio
turnover
```

### Monthly revenue

Potential features:

```text
revenue_mom
revenue_yoy
revenue_growth_trend
revenue_acceleration
```

### Historical actual financials

Potential features:

```text
actual_eps_history
ROE
ROA
gross_margin
operating_margin
net_margin
debt_ratio
cash-flow metrics
profit/revenue growth
```

### TDCC

Potential features:

```text
large_holder_ratio
holder_distribution
concentration_change
```

## Rules

Features may use only PIT-safe source rows already retrieved by the dataset builder.

Feature modules do not call Data Center directly.

No predicted EPS features in v1.

## Acceptance Criteria

- [ ] Feature builder is deterministic
- [ ] Feature schema is versioned
- [ ] Every feature documents formula and source inputs
- [ ] No feature fetches future data
- [ ] No feature uses entry date as information cutoff
- [ ] No predicted EPS feature exists
- [ ] Known-safe old/new feature comparisons exist

---

# 13. Phase 5 — Forward-Return Label Pipeline

## Goal

Define historical selection labels without allowing target-cohort leakage.

## Label Definition

Example:

```text
entry_price = price on cohort entry date
exit_price  = price on defined exit date

forward_return = exit_price / entry_price - 1
```

The exact price convention must be documented:

```text
open
close
VWAP
adjusted/unadjusted
```

and must not change silently.

## Label Availability

A forward-return label becomes training-eligible only after the exit observation is complete.

Conceptually:

```text
label_available_at >= exit market close / required source availability
```

## Critical Rule

For target cohort C:

```text
train_model_for(C)
```

must use only cohorts whose:

```text
label_available_at <= C.information_as_of
```

or another explicitly documented training cutoff.

The target cohort's own label can never train the model that ranks that cohort.

## Acceptance Criteria

- [ ] Label formula is explicit
- [ ] Entry/exit price convention is explicit
- [ ] Target cohort is excluded from its own training data
- [ ] Incomplete label horizons are excluded
- [ ] Label availability is auditable
- [ ] Regression test protects target-cohort self-training

---

# 14. Phase 6 — Training Dataset Contract

## Goal

Join PIT-safe features with only label-eligible historical cohorts.

## Training Row Identity

At minimum:

```text
security_id
cohort_id
playbook_date
feature PIT context
label horizon
```

## Required Dataset Manifest

```text
dataset_id/hash
target cohort
training cutoff
feature schema version
eligible cohort range
excluded cohorts + reasons
row count
Data Center provenance
build git commit
```

## Acceptance Criteria

- [ ] Target cohort never appears in training rows
- [ ] Cohorts with incomplete labels are excluded
- [ ] Feature/label join is explicit
- [ ] Dataset hash is deterministic
- [ ] Dataset can be reconstructed from manifest inputs

---

# 15. Phase 7 — Walk-Forward Selection Training

## Goal

Train ranking/selection models using only historically eligible cohorts.

## Required Strategy

Use walk-forward / expanding-window logic.

Example:

```text
Train through May realized labels -> rank July
Train through June realized labels -> rank August
...
```

Exact dates depend on the label horizon.

The implementation must derive eligibility from dates, not hard-coded month names.

## Metrics

At minimum consider:

```text
MAE/RMSE if regression target is raw return
rank correlation / Spearman IC
Top-K average return
Top-K hit rate
precision by positive-return threshold
coverage
sample count
```

## Acceptance Criteria

- [ ] Training split is deterministic
- [ ] Target cohort cannot train itself
- [ ] No cohort with unavailable label enters training
- [ ] Fold-level metrics are stored
- [ ] Aggregate metrics are stored
- [ ] Random seed is fixed where applicable

---

# 16. Phase 8 — Model Artifact Format

## Goal

Make every selection model reproducible.

Suggested layout:

```text
models/
└── 2026-07-11/
    ├── model.joblib
    ├── feature_schema.json
    ├── metrics.json
    ├── training_manifest.json
    └── environment.json
```

`training_manifest.json` must include:

```text
target cohort
training cutoff
PIT context
Data Center provenance
training dataset hash
feature schema version
model type
hyperparameters
random seed
git commit
package versions
```

## Acceptance Criteria

- [ ] Model refuses incompatible feature schemas
- [ ] Model artifact hash is recorded
- [ ] Training manifest is complete
- [ ] Metrics map to the exact model artifact
- [ ] Training can be reproduced from manifest inputs

---

# 17. Phase 9 — Ranking and Publication

## Goal

Score one target cohort and produce a frozen ranking artifact.

## Output

At minimum:

```text
rank
security_id
symbol
score
selected
feature schema version
model ID/hash
cohort ID
PIT context
Data Center provenance
```

## Ranking Manifest

Must include:

```text
ranking_id
playbook_date
information_as_of
knowledge_as_of or system_as_of
entry_date
model_id
feature dataset hash
candidate count
Top-K
git commit
```

## Critical Rule

Once published, a production ranking artifact is immutable.

Historical reruns are new artifacts, not replacements of the original ranking.

## Acceptance Criteria

- [ ] Ranking is deterministic for fixed model/data
- [ ] Top-K semantics are explicit
- [ ] Published artifact is immutable
- [ ] Original production ranking and later reconstruction remain distinguishable
- [ ] Ranking includes full provenance

---

# 18. Phase 10 — Backtest Engine

## Goal

Evaluate frozen ranking artifacts with explicit trading rules.

## Backtester Responsibilities

The backtester owns:

```text
entry execution convention
exit/rebalance convention
position sizing
Top-K portfolio logic
fees
slippage
capital accounting
performance metrics
```

It does NOT own:

```text
feature PIT fixes
financial-report availability workarounds
month-specific leakage patches
```

Forbidden workaround style:

```python
if month in (2, 3):
    skip_entry = True
```

when the real problem is data availability.

## Metrics

At minimum:

```text
cumulative return
CAGR
Sharpe
max drawdown
win rate
turnover
Top-K average return
benchmark-relative return
```

## Acceptance Criteria

- [ ] Backtester consumes frozen ranking artifacts
- [ ] Backtester never rebuilds features
- [ ] Trading rules are explicit
- [ ] Fees/slippage are configurable
- [ ] No month-specific PIT workaround exists
- [ ] Metrics are reproducible

---

# 19. Phase 11 — Old vs New Regression Analysis

## Goal

Quantify the effect of removing historical leakage from the old project.

## Required Historical Cases

At minimum cover:

### Case A — Entry-date feature leakage

Old behavior:

```text
7/11 cohort
feature fetch <= 7/13 entry date
```

New behavior:

```text
feature fetch strictly uses PIT context
```

### Case B — Delayed monthly revenue

7/13 publication must not appear under a 7/10 market-information cutoff unless the Data Center's PIT semantics explicitly make it visible.

### Case C — Q4 / Feb-Mar issue

Do not solve by skipping months in the backtester.

The Data Center determines what financial information is visible.

### Case D — Historical universe drift

Today's active universe must not replace the historical universe.

## Acceptance Criteria

- [ ] Old leakage cases are reproduced
- [ ] New architecture rejects them
- [ ] Ranking differences are quantified
- [ ] Performance degradation/improvement is reported honestly
- [ ] Results are documented

---

# 20. Phase 12 — CLI

Suggested commands:

```text
stock-select build-universe
stock-select build-dataset
stock-select train
stock-select rank
stock-select backtest
stock-select inspect-manifest
```

Prefer explicit flags:

```text
--playbook-date
--information-as-of
--knowledge-as-of
--system-as-of
--entry-date
--top-k
```

Avoid ambiguous `--date`.

## Acceptance Criteria

- [ ] Temporal inputs are validated
- [ ] Commands emit manifests
- [ ] CLI help explains PIT semantics
- [ ] Invalid feature/model schema fails loudly

---

# 21. Phase 13 — CI and Quality Gates

CI should run:

```text
pytest
package build
PIT regression tests
feature-schema compatibility tests
direct-DB guard
no-EPS-dependency guard for v1
```

Permanent regression tests must include:

```text
entry_date never controls feature availability
target cohort never trains itself
incomplete forward-return labels are excluded
historical universe is PIT-safe
future listing not visible
delayed source data obeys Data Center PIT
same model/data -> same ranking
backtest consumes frozen ranking artifact
```

## Acceptance Criteria

- [ ] CI runs on pull requests
- [ ] CI blocks PIT regressions
- [ ] CI blocks target-cohort leakage
- [ ] CI blocks direct DB access
- [ ] CI blocks accidental stock-eps-model dependency in v1

---

# 22. Migration from Old Project

Do NOT copy these directories wholesale:

```text
strategies/
models_selection/
backtester/
```

Migration order:

```text
1. document old behavior
2. identify reusable feature formulas
3. rebuild Data Center access
4. rebuild historical universe
5. rebuild forward-return labels
6. rebuild training split
7. rebuild ranking
8. rebuild backtest
9. compare old vs new
```

Potentially reusable after review:

```text
feature formulas
model hyperparameters
metrics
ranking rules
portfolio rules
```

Do not migrate:

```text
raw SQL
DB configuration
manual publish_time filters
entry-date feature fetching
current-universe assumptions
month-specific PIT workarounds
implicit model-date selection
```

---

# 23. Suggested Milestones

```text
M0 Contracts                  -> Phase 0
M1 Clean Boundary             -> Phases 1-3
M2 Base Features              -> Phase 4
M3 Labels + Training Dataset  -> Phases 5-6
M4 Walk-Forward Model         -> Phases 7-8
M5 Ranking                    -> Phase 9
M6 Backtest                   -> Phase 10
M7 Leakage Comparison         -> Phase 11
M8 Operations / CI            -> Phases 12-13
```

---

# 24. Definition of Done for v1

- [ ] No direct stock DB access
- [ ] No dependency on `stock-eps-model`
- [ ] Historical universe is PIT-safe
- [ ] Every feature uses explicit PIT context
- [ ] Entry date is never an information cutoff
- [ ] Feature schema is versioned
- [ ] Forward-return labels have explicit availability semantics
- [ ] Target cohort never trains itself
- [ ] Walk-forward training is implemented
- [ ] Model artifacts are reproducible
- [ ] Ranking artifacts are immutable
- [ ] Backtest consumes frozen rankings
- [ ] Known old leakage cases are permanently tested
- [ ] CLI uses explicit temporal arguments
- [ ] CI protects core invariants

---

# 25. Recommended First Implementation Sprint

Implement:

```text
Phase 0
Phase 1
Phase 2
Phase 3
```

Before training any model, prove:

```text
1. historical universe is correct
2. no feature request uses entry_date
3. all data comes through Data Center
4. v1 has no stock-eps-model dependency
```

Then implement the forward-return label contract and target-cohort exclusion tests before adding LightGBM training.

---

# 26. Core Design Principles

1. No direct stock database access.
2. No predicted EPS dependency in v1.
3. Data availability belongs to Data Center.
4. Entry date is not an information cutoff.
5. Historical universe must be PIT-safe.
6. Future return may be a historical label, never a current feature.
7. A cohort cannot train the model that ranks itself.
8. Time-aware training is mandatory.
9. Published rankings are immutable artifacts.
10. Backtesting consumes rankings; it does not repair PIT mistakes.
11. Model performance is secondary to leakage-free evaluation.
12. Every result must retain provenance.
