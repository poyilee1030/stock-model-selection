# stock-model-selection ROADMAP

## 1. Project Goal

`stock-model-selection` trains stock-selection models, ranks candidate stocks, and evaluates those rankings using PIT-safe observed and canonical-derived data from `stock-data-center`.

Version 1 intentionally does NOT use `stock-eps-model`.

Core rule:

> Data Center owns reusable canonical metrics.
> Model Selection owns ranking-specific transformations, forward-return labels, training, ranking, and backtesting.

---

## 2. v1 Data Sources

Allowed Data Center inputs:

```text
historical universe
daily market data
monthly revenue
financial/XBRL data
historical actual EPS
TDCC
institutional/chip-flow source data
margin/SBL
market indices
corporate actions
official valuation
canonical derived datasets
```

No predicted EPS in v1.

---

## 3. Canonical vs Model-Specific Features

### Data Center canonical examples

```text
MA5/MA20/MA60
returns
historical volatility
RSI/MACD if standardized
revenue MoM/YoY
TTM EPS
ROE/ROA/margins
shareholding concentration
margin usage ratios
short-interest/SBL ratios
canonical valuation metrics
```

### Model Selection-owned examples

```text
cross-sectional z-scores
percentile/rank transforms
universe-relative features
momentum-quality interactions
ranking-oriented composites
model-specific interactions
```

Do not duplicate canonical Data Center formulas.

---

## 4. Hard Invariants

```text
no direct DB/Redis access
no stock-eps-model dependency in v1
entry_date is never information cutoff
historical universe must be PIT-safe
future return is label, never feature
target cohort cannot train itself
canonical Data Center dependencies must record derivation_version
backtester consumes frozen ranking artifacts
```

---

## 5. Repository Structure

```text
stock-model-selection/
├── README.md
├── ROADMAP.md
├── AGENTS.md
├── pyproject.toml
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
```

---

# 6. Phase 0 — Contract Freeze

Define:

```text
cohort identity
playbook date
information/knowledge/system cutoffs
entry/exit dates
label horizon
label availability
universe semantics
canonical Data Center dependencies
model-specific feature ownership
ranking contract
backtest contract
```

Acceptance criteria:

- [ ] v1 excludes predicted EPS
- [ ] entry date is never information cutoff
- [ ] target cohort cannot train itself
- [ ] canonical vs model-specific ownership is explicit
- [ ] every canonical dependency records derivation version

---

# 7. Phase 1 — Repository Skeleton and Data Center Boundary

Create:

```text
PIT/cohort domain models
Data Center client
response schemas
derivation metadata
fake client
direct-DB guard
no-EPS-dependency guard
```

Acceptance criteria:

- [ ] no DB/Redis access
- [ ] no stock-eps-model dependency
- [ ] Data Center client is mockable
- [ ] no training yet

---

# 8. Phase 2 — PIT-Safe Historical Universe

Construct historical candidate universe from Data Center.

Do not use today's active-stock list.

Acceptance criteria:

- [ ] future listings excluded
- [ ] later-delisted securities remain historically eligible when appropriate
- [ ] universe provenance captured

---

# 9. Phase 3 — PIT-Safe Dataset Builder

Consume:

```text
observed Data Center datasets
canonical derived Data Center datasets
```

Preserve:

```text
PIT context
source provenance
derivation versions
```

Do not use `entry_date` to fetch feature data.

---

# 10. Phase 4 — Model-Specific Feature Pipeline

This phase owns only ranking-specific transforms.

Examples:

```text
cross-sectional ranks
z-scores
sector/universe normalization
interaction terms
composite ranking features
```

Do not reimplement Data Center canonical metrics.

Acceptance criteria:

- [ ] canonical inputs and model-specific transforms are explicitly separated
- [ ] feature schema versioned
- [ ] derivation versions captured
- [ ] deterministic output
- [ ] no predicted EPS

---

# 11. Phase 5 — Forward-Return Labels

Define:

```text
entry date
exit date
price convention
label_available_at
```

A label becomes trainable only after the horizon is complete.

Target cohort must never train itself.

---

# 12. Phase 6 — Training Dataset Contract

Join:

```text
PIT-safe universe
canonical Data Center features
model-specific transforms
eligible historical forward-return labels
```

Manifest includes:

```text
dataset hash
target cohort
PIT context
canonical derivation versions
feature schema version
eligible cohort range
excluded cohorts/reasons
Data Center provenance
git commit
```

---

# 13. Phase 7 — Walk-Forward Selection Training

Use expanding/rolling historical training.

Metrics may include:

```text
Spearman IC
Top-K average return
Top-K hit rate
coverage
sample count
regression metrics if predicting raw returns
```

---

# 14. Phase 8 — Model Artifact

Artifact must include:

```text
model hash
target cohort
training cutoff
PIT context
Data Center provenance
canonical derived dependency versions
training dataset hash
feature schema version
hyperparameters
random seed
git commit
package versions
metrics
```

---

# 15. Phase 9 — Ranking Artifact

Produce immutable ranking artifacts.

Include:

```text
rank
security
score
selected
model ID
ranking ID
cohort
PIT context
feature schema
canonical derivation versions
Data Center provenance
```

Historical reruns create new artifacts; never overwrite original production ranking.

---

# 16. Phase 10 — Backtest

Backtester consumes frozen rankings.

It may use Data Center for:

```text
entry/exit prices
corporate actions
benchmark/index data
```

It must not:

```text
rebuild features
rerun model
repair PIT problems
apply month-specific leakage workarounds
```

---

# 17. Phase 11 — Old vs New Regression Analysis

Required historical cases:

```text
entry-date lookahead
delayed monthly revenue
Q4/Feb-Mar visibility
historical-universe drift
target-cohort self-training
```

Quantify ranking/performance differences.

---

# 18. Phase 12 — CLI

Suggested commands:

```text
stock-select build-universe
stock-select build-dataset
stock-select train
stock-select rank
stock-select backtest
stock-select inspect-manifest
```

Use explicit time flags.

---

# 19. Phase 13 — CI

Permanent guards:

```text
no DB/Redis access
no stock-eps-model dependency in v1
no duplicate canonical metric implementation without ADR
entry_date never controls feature availability
target cohort never trains itself
incomplete labels excluded
historical universe PIT-safe
canonical derivation versions captured
same model/data -> same ranking
```

---

# 20. Migration from Old Project

Potentially reusable:

```text
ranking rules
model hyperparameters
model-specific interactions
metrics
portfolio rules
```

Do NOT migrate:

```text
raw SQL
DB setup
manual publish-time filters
entry-date feature lookup
canonical metrics now owned by Data Center
month-specific PIT workarounds
```

---

# 21. Definition of Done

- [ ] no direct DB/Redis access
- [ ] no stock-eps-model dependency in v1
- [ ] historical universe PIT-safe
- [ ] canonical reusable metrics come from Data Center
- [ ] canonical dependency derivation versions are captured
- [ ] entry date never controls feature availability
- [ ] target cohort never trains itself
- [ ] walk-forward training implemented
- [ ] ranking artifacts immutable
- [ ] backtest consumes frozen rankings
- [ ] old leakage cases permanently tested

---

# 22. Core Boundary

```text
stock-data-center:
    observed data
    canonical reusable derived data
    derivation versions

stock-model-selection:
    ranking-specific transforms
    forward-return labels
    training
    ranking
    backtesting
```

Version 1 remains independent of `stock-eps-model`.
