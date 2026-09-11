# AGENTS.md

## Purpose

This repository implements `stock-model-selection`.

Version 1 does NOT use `stock-eps-model`.

Highest-priority rule:

> Rank each cohort using only historically valid Data Center information and only earlier fully realized labels.

## 1. Canonical Roadmap

Use:

```text
ROADMAP.md
```

Work one phase at a time.

## 2. No Direct DB or Redis Access

Forbidden:

```text
PostgreSQL connections
raw SQL
Data Center table names
Redis access
```

All source/canonical data comes from Data Center API/SDK.

## 3. No stock-eps-model Dependency in v1

No predicted EPS features or EPS-model client/imports.

Historical actual EPS from Data Center is allowed.

## 4. Canonical Derived Data Rule

If Data Center provides a canonical metric, do not independently reimplement it here.

Examples:

```text
MA20
historical volatility
revenue YoY
TTM EPS
ROE
shareholding concentration
margin ratios
short-interest ratios
canonical valuation metrics
```

Reimplementation requires an ADR.

## 5. Model-Specific Feature Rule

This repo owns ranking-specific transforms such as:

```text
cross-sectional ranks
z-scores
percentiles
universe-relative normalization
interaction terms
composite ranking features
```

## 6. Derivation-Version Rule

Every consumed canonical derived dataset must record:

```text
dataset_code
derivation_version
```

in dataset, model, ranking, and backtest provenance.

## 7. Entry Date Rule

`entry_date` is not an information cutoff.

Forbidden:

```python
fetch_features(as_of=entry_date)
```

except under an explicitly changed contract.

## 8. Historical Universe Rule

Never use today's active universe for historical cohorts.

Universe comes from Data Center PIT queries.

## 9. Forward-Return Label Rule

Future return is allowed only as a historical label.

It is never a feature.

A label is trainable only after its horizon is complete.

## 10. Target Cohort Rule

Target cohort C must be excluded from:

```text
its own training rows
all later cohorts
all earlier cohorts with incomplete labels
```

Treat violations as P0 leakage bugs.

## 11. Dataset Construction Rule

Do not build one current-state dataset and slice by historical dates.

Each cohort is PIT-correct at construction time.

## 12. Feature Module Rule

Feature modules:

- consume normalized Data Center data
- compute only model-specific transforms
- do not fetch external data
- do not decide publication visibility
- do not duplicate canonical Data Center metrics

## 13. Training Split

Use walk-forward / expanding / explicitly documented rolling windows.

Random split is not primary historical evaluation.

## 14. Model Artifact Provenance

Every model must include:

```text
target cohort
training cutoff
PIT context
Data Center provenance
canonical derivation versions
training dataset hash
feature schema version
hyperparameters
random seed
git commit
package versions
metrics
```

## 15. Ranking Artifact Rule

Published ranking artifacts are immutable.

Historical reruns create new reconstruction artifacts.

Never overwrite an original production ranking.

## 16. Backtest Rule

Backtester consumes frozen rankings.

It must not:

```text
rebuild features
rerun model
repair PIT semantics
apply month-specific leakage workarounds
```

It may query Data Center for trade prices, corporate actions, and benchmark/index history.

## 17. Leakage Regression Tests

Permanent cases:

```text
entry-date lookahead
target cohort self-training
incomplete forward-return labels
historical-universe drift
future data leakage
canonical derivation-version mismatch
```

## 18. Migration Rule

Do not copy old `strategies/`, `models_selection/`, or `backtester/` wholesale.

Do not migrate canonical metric implementations now owned by Data Center.

## 19. Error Handling

Fail loudly on:

```text
missing PIT context
entry date used as feature cutoff
target cohort in training
missing/incompatible derivation version
missing provenance
incompatible feature schema
```

## 20. Priority Order

```text
1. no leakage
2. PIT correctness
3. target-cohort isolation
4. derivation-version reproducibility
5. provenance
6. deterministic behavior
7. maintainability
8. model performance
9. convenience
```

## 21. Core Boundary

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
