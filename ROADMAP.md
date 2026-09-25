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

### Test-First Rule

Write tests before implementation code, for every phase and every change:

```text
1. write failing tests that encode the acceptance criteria / invariant
2. run them and confirm they fail for the expected reason
3. write the minimal implementation that makes them pass
4. refactor with tests green
```

- Bug fixes start with a regression test that reproduces the bug.
- Leakage and PIT invariants start as failing tests before the guarded code exists.
- A PR that adds implementation without tests written first is incomplete.

### Step Rules

- Each phase is delivered as one or more steps. One step = one branch (`step-N`) = one PR titled `step-N: <one-line goal>`.
- Target size: at most 800 lines of implementation code per step, excluding tests, test fixtures, and docs.
- If a step is estimated above 800 lines, split it into `step-N-a`, `step-N-b`, `step-N-c`, ... Each part is independently mergeable and carries its own tests.
- An unsplit step above 800 lines is allowed only with a strong reason written in its entry as `Size exception: <reason>`.
- Estimates in this roadmap are planning figures. Re-check at step start; if implementation grows past 800 lines mid-step, stop and split instead of merging an oversized PR.
- Work outside a step's scope is added to a later step, not fixed in passing.

---

## 5. Repository Structure

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

## 6. Step Overview

Line counts are planning estimates of implementation code, excluding tests.
Re-check the estimate at the start of each step (see Step Rules in §4).

| Step | Phase | Goal | Est. lines | Depends on |
|---|---|---|---|---|
| step-1 | 0 | Time and cohort semantics contract | 0 (docs) | — |
| step-2 | 0 | Data dependency, ownership, artifact contracts; open decisions | 0 (docs) | step-1 |
| step-3 | 1 | Repo skeleton, baseline CI, static boundary guards | ~250 | step-2 |
| step-4 | 1 | PIT and cohort domain models | ~450 | step-3 |
| step-5-a | 1 | Data Center client interface and response schemas | ~600 | step-4 |
| step-5-b | 1 | PIT-enforcing fake Data Center client | ~400 | step-5-a |
| step-6 | 1 | Real Data Center SDK adapter | ~300 | step-5-a (parallel line) |
| step-7 | 2 | PIT-safe historical universe | ~350 | step-5-b |
| step-8-a | 3 | Dataset request spec and PIT-safe fetch | ~450 | step-7 |
| step-8-b | 3 | Cohort panel assembly and dataset provenance | ~450 | step-8-a |
| step-9 | 4 | Feature schema and registry | ~350 | step-8-b |
| step-10 | 4 | Cross-sectional transforms | ~400 | step-9 |
| step-11 | 4 | Interaction terms, composites, feature builder | ~450 | step-10 |
| step-12 | 5 | Forward-return label computation | ~450 | step-5-b |
| step-13 | 5 | Label eligibility gate | ~250 | step-12 |
| step-14 | 6 | Training dataset assembler | ~450 | step-11, step-13 |
| step-15 | 6 | Training manifest and dataset hash | ~350 | step-14 |
| step-16 | 7 | Walk-forward schedule and evaluation metrics | ~550 | step-15 |
| step-17 | 7 | Model trainer and walk-forward runner | ~500 | step-16 |
| step-18 | 8 | Model artifact | ~450 | step-17 |
| step-19 | 9 | Ranking generation and immutable ranking artifact | ~500 | step-18 |
| step-20 | 10 | Backtest engine on frozen rankings | ~550 | step-19 |
| step-21 | 10 | Benchmark comparison and performance report | ~400 | step-20 |
| step-22 | 11 | Old-output ingestion and comparison harness | ~400 | step-21, step-6 |
| step-23 | 11 | Historical leakage case studies | ~300 + docs | step-22 |
| step-24 | 12 | CLI | ~500 | step-21 |
| step-25 | 13 | Permanent guard consolidation | ~250 | step-24 |

Parallel lines:

```text
step-6            can proceed in parallel with steps 7–21 (they develop against the fake client);
                  it must merge before step-22.
step-12..13       depend only on step-5-b and may run in parallel with steps 7–11.
```

---

# 7. Phase 0 — Contract Freeze

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

Open decisions that must be resolved (or explicitly deferred to a named step) in this phase:

```text
Data Center API/SDK surface (package, PIT query parameters, derivation metadata fields)
trading calendar source
price convention for labels and backtest (adjusted vs raw, open vs close)
benchmark index
model library for v1
artifact storage location and format
dataset serialization format used for hashing
access to old-project historical outputs (needed by Phase 11)
```

Acceptance criteria:

- [ ] v1 excludes predicted EPS
- [ ] entry date is never information cutoff
- [ ] target cohort cannot train itself
- [ ] canonical vs model-specific ownership is explicit
- [ ] every canonical dependency records derivation version

## step-1: Time and cohort semantics contract

- Estimated code: 0 lines (docs only)
- Deliverable: `docs/contracts/time-and-cohort.md`
  - cohort identity and playbook date
  - information / knowledge / system cutoffs and their ordering
  - entry/exit dates, label horizon, `label_available_at`
  - universe semantics
  - one worked timeline for a monthly cohort, including delayed monthly revenue and Q4 annual reports published in Feb–Mar
- Tests first: not applicable (docs only). The invariants written here become the first failing tests of step-4.
- Acceptance:
  - [ ] entry date is explicitly not an information cutoff
  - [ ] target-cohort exclusion rule stated (own rows, later cohorts, earlier cohorts with incomplete labels)
  - [ ] label availability rule stated

## step-2: Data dependency, ownership, and artifact contracts

- Estimated code: 0 lines (docs only)
- Deliverables:
  - `docs/contracts/data-dependencies.md`: every Data Center dataset consumed, with `dataset_code`, required `derivation_version`, PIT query semantics
  - `docs/contracts/feature-ownership.md`: canonical vs model-specific table
  - `docs/contracts/ranking.md`, `docs/contracts/backtest.md`
  - `docs/adr/0000-template.md`: ADR template required for any canonical-metric reimplementation
  - `docs/decisions.md`: resolution of every open decision listed above
- Acceptance:
  - [ ] v1 excludes predicted EPS
  - [ ] canonical vs model-specific ownership is explicit
  - [ ] every canonical dependency lists its derivation version
  - [ ] every open decision is resolved or deferred to a named step

---

# 8. Phase 1 — Repository Skeleton and Data Center Boundary

Create:

```text
PIT/cohort domain models
Data Center client
response schemas
derivation metadata
fake client
direct-DB guard
no-EPS-dependency guard
baseline CI
```

Acceptance criteria:

- [ ] no DB/Redis access
- [ ] no stock-eps-model dependency
- [ ] Data Center client is mockable
- [ ] no training yet

## step-3: Repository skeleton, baseline CI, static boundary guards

- Estimated code: ~250 lines
- Content:
  - `pyproject.toml` (package metadata, pytest, ruff, mypy), `src/` layout per §5, README with an honest status section
  - CI workflow running lint, type check, and pytest on every PR. Baseline CI lives here, not in Phase 13, so every later step runs under CI.
  - static guards that scan `src/` and `pyproject.toml`:
    - forbidden imports: PostgreSQL drivers, SQLAlchemy, Redis clients, `stock-eps-model` packages/clients
    - raw SQL patterns and Data Center table names
- Tests first: each guard is run against deliberately violating fixture files and must fail on them.
- Acceptance:
  - [ ] no DB/Redis access
  - [ ] no stock-eps-model dependency
  - [ ] CI green on the skeleton

## step-4: PIT and cohort domain models

- Estimated code: ~450 lines
- Content:
  - `PitContext` (information / knowledge / system cutoffs, ordering validation)
  - `Cohort` (id, playbook date, entry/exit, horizon, `label_available_at`)
  - `DerivationRef` (`dataset_code`, `derivation_version`) and provenance record types
  - feature-fetching APIs accept a `PitContext` only, never a bare date
- Tests first:
  - missing PIT context raises
  - building a `PitContext` from `entry_date` raises
  - cutoff ordering violation raises
  - `DerivationRef` without a version raises

## step-5-a: Data Center client interface and response schemas

- Estimated code: ~600 lines
- Split reason: the full client boundary (interface, schemas, fake) is estimated at ~1000 lines.
- Content:
  - `DataCenterClient` protocol: one method per v1 data source (§2). Feature data methods take `PitContext`. Trade-price, corporate-action, and index methods for labels/backtest take explicit dates.
  - response schemas carrying `dataset_code`, `derivation_version`, per-row availability timestamp, source provenance
  - error types: missing derivation version, PIT violation, missing provenance
- Tests first:
  - a response without `derivation_version` or provenance is rejected
  - no feature-data method accepts `entry_date`

## step-5-b: PIT-enforcing fake Data Center client

- Estimated code: ~400 lines
- Content:
  - in-memory fixture store. Every row has an availability timestamp, and the fake returns only rows visible at the knowledge cutoff. Without this, leakage tests cannot detect anything.
  - fixture builders: listings/delistings, monthly revenue with publication lag, quarterly/annual financials with late publication, prices, corporate actions
  - fault injection: wrong derivation version, missing provenance
- Tests first:
  - rows published after the cutoff are hidden
  - the delayed-revenue and Q4 timelines from step-1 are reproducible
- Acceptance:
  - [ ] Data Center client is mockable
  - [ ] no training yet

## step-6: Real Data Center SDK adapter

- Estimated code: ~300 lines
- Depends on: step-2 (API surface decision), step-5-a
- Content:
  - adapter implementing `DataCenterClient` over the Data Center API/SDK
  - configuration via environment (endpoint, credentials); no secrets in repo
  - response mapping to schemas; `derivation_version` verified per response
- Tests first: contract tests against recorded responses (no live network in CI); an optional live smoke test, marked and skipped in CI.
- Parallel line: steps 7–21 develop against the fake client. This step must merge before step-22.

---

# 9. Phase 2 — PIT-Safe Historical Universe

Construct historical candidate universe from Data Center.

Do not use today's active-stock list.

Acceptance criteria:

- [ ] future listings excluded
- [ ] later-delisted securities remain historically eligible when appropriate
- [ ] universe provenance captured

## step-7: PIT-safe historical universe

- Estimated code: ~350 lines
- Content:
  - `data/universe.py`: universe snapshot for a `PitContext` via Data Center PIT universe query
  - eligibility filters as defined in step-1
  - snapshot carries provenance and a content hash
  - defensive check: fail if Data Center returns a security listed after the cutoff
- Tests first (permanent):
  - future listings excluded
  - later-delisted securities remain eligible
  - historical-universe drift: today's active list is never used for a historical cohort
  - provenance captured

---

# 10. Phase 3 — PIT-Safe Dataset Builder

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

Each cohort is built PIT-correct on its own; never build one current-state dataset and slice it by date.

## step-8-a: Dataset request spec and PIT-safe fetch

- Estimated code: ~450 lines
- Split reason: the full dataset builder is estimated at ~900 lines.
- Content:
  - declarative dataset spec: observed and canonical datasets with pinned derivation versions (from step-2)
  - per-cohort fetch through `PitContext` only
  - fail on missing or mismatched `derivation_version`
  - defense in depth: fail if any returned row is not visible at the knowledge cutoff
- Tests first (permanent leakage regressions, on the fake client):
  - entry-date lookahead
  - delayed monthly revenue
  - Q4 / Feb–Mar visibility
  - canonical derivation-version mismatch

## step-8-b: Cohort panel assembly and dataset provenance

- Estimated code: ~450 lines
- Content:
  - as-of alignment: latest visible row per security per dataset, joined onto the universe snapshot
  - explicit missing-data policy (no silent forward-fill beyond the contract)
  - aggregated provenance: `dataset_code` + `derivation_version` per input, Data Center provenance, PIT context
  - deterministic serialization and dataset hash
  - builder API takes one cohort's `PitContext`
- Tests first:
  - same inputs produce the same hash
  - incomplete provenance fails
  - building cohort A never reads data visible only to a later cohort

---

# 11. Phase 4 — Model-Specific Feature Pipeline

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

## step-9: Feature schema and registry

- Estimated code: ~350 lines
- Content:
  - `FeatureSpec`: name, canonical inputs (`dataset_code`, column), transform id, parameters
  - `FeatureSchema` with version and hash
  - explicit split between canonical passthrough and model-specific transforms
  - registry rejects:
    - inputs tagged as labels / forward returns
    - predicted EPS
    - transforms that duplicate a canonical metric (§3) unless an ADR id is attached
- Tests first: the schema hash changes when any spec changes, and each rejection rule has a failing case.

## step-10: Cross-sectional transforms

- Estimated code: ~400 lines
- Content:
  - `features/transforms.py`, `features/cross_sectional.py`: rank, percentile, z-score, winsorize, universe/sector-relative normalization, missing-value handling
  - deterministic tie-breaking (by security id)
  - pure functions over one cohort's panel only; never across cohorts
- Tests first:
  - known-value tests
  - determinism
  - a transform sees only the given cohort's rows

## step-11: Interaction terms, composites, feature builder

- Estimated code: ~450 lines
- Content:
  - `features/interactions.py`: interaction terms and composite ranking features
  - `features/builder.py`: applies the registry to a cohort panel and produces a feature matrix plus a feature manifest (schema version and derivation versions carried through)
- Tests first:
  - deterministic output
  - derivation versions present in the manifest
  - an incompatible feature schema fails loudly

---

# 12. Phase 5 — Forward-Return Labels

Define:

```text
entry date
exit date
price convention
label_available_at
```

A label becomes trainable only after the horizon is complete.

Target cohort must never train itself.

## step-12: Forward-return label computation

- Estimated code: ~450 lines
- Content:
  - `LabelSpec`: horizon, price convention (from step-2), `label_available_at`
  - corporate actions handled from Data Center data (use Data Center adjusted prices if canonical; do not reimplement)
  - explicit policy for suspension/delisting within the horizon
  - labels are a distinct type in `labels/` and cannot be passed into the feature builder
- Tests first:
  - known-value returns
  - corporate action applied
  - `label_available_at` computed per contract
  - delisting-within-horizon policy

## step-13: Label eligibility gate

- Estimated code: ~250 lines
- Content: for target cohort C, return the cohorts whose labels are trainable, plus exclusion reasons. Excluded:
  - C itself
  - all later cohorts
  - earlier cohorts whose `label_available_at` is after C's cutoff (as defined in step-1)
- Tests first (permanent):
  - target-cohort self-training
  - incomplete forward-return labels
  - later cohorts excluded
- Kept separate from step-12 even though the combined size is under 800 lines: this is the P0 leakage gate and gets its own review.

---

# 13. Phase 6 — Training Dataset Contract

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

## step-14: Training dataset assembler

- Estimated code: ~450 lines
- Content:
  - for target C: build each eligible cohort independently (steps 8, 11) and join its labels (step-12) filtered by step-13
  - C's inference matrix is built separately and has features only
  - each of these fails loudly:
    - a target-cohort row in training
    - an incomplete label
    - derivation versions inconsistent across cohorts
    - an inconsistent feature schema
- Tests first: an injected target row, mixed derivation versions, and an incomplete label each fail.

## step-15: Training manifest and dataset hash

- Estimated code: ~350 lines
- Content:
  - manifest with every field listed above, including git commit and excluded cohorts with reasons
  - deterministic dataset hash
- Tests first:
  - any missing provenance field fails
  - identical inputs produce an identical hash
  - manifest round-trips

---

# 14. Phase 7 — Walk-Forward Selection Training

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

## step-16: Walk-forward schedule and evaluation metrics

- Estimated code: ~550 lines
- Content:
  - schedule: expanding and explicitly documented rolling windows over target cohorts. Training sets come from step-13, with no separate embargo logic.
  - metrics listed above
  - no random split in primary evaluation
- Tests first:
  - the schedule never places the target cohort or later cohorts in training
  - metric known values

## step-17: Model trainer and walk-forward runner

- Estimated code: ~500 lines
- Content:
  - model interface and the v1 model (library from step-2); hyperparameter config; fixed seeds and deterministic settings
  - runner: for each target cohort, assemble dataset → train → predict → evaluate, then write a run report
- Tests first:
  - same seed and data produce identical predictions
  - the runner fails when the dataset manifest is missing

---

# 15. Phase 8 — Model Artifact

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

## step-18: Model artifact

- Estimated code: ~450 lines
- Content:
  - serialization with every field above; content-addressed storage (location from step-2)
  - load-time validation: feature schema and derivation versions must match; fail loudly otherwise
- Tests first:
  - a missing field fails
  - a tampered artifact fails its hash check
  - an incompatible schema at load fails

---

# 16. Phase 9 — Ranking Artifact

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

## step-19: Ranking generation and immutable ranking artifact

- Estimated code: ~500 lines
- Content:
  - score the target cohort from a model artifact; deterministic ranking and selection rule
  - artifact kind: `production` or `reconstruction`
  - write-once store that refuses overwrites; historical reruns always create a new reconstruction artifact
- Tests first:
  - an overwrite attempt fails
  - a rerun creates a new ranking ID
  - same model and data produce an identical ranking

---

# 17. Phase 10 — Backtest

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

## step-20: Backtest engine on frozen rankings

- Estimated code: ~550 lines
- Content:
  - load a ranking artifact and verify its hash
  - portfolio construction, with entry/exit prices and corporate actions from Data Center
  - suspension/delisting handling; cost model
  - import-boundary guard: `backtest/` must not import `features/`, `training/`, or the dataset builder
- Tests first:
  - a tampered ranking is rejected
  - the guard fails on a forbidden import
  - known-value portfolio return

## step-21: Benchmark comparison and performance report

- Estimated code: ~400 lines
- Content:
  - benchmark (from step-2) returns via Data Center
  - excess return, cumulative return, drawdown, turnover, hit rate
  - report artifact carrying ranking IDs and provenance
- Tests first: known-value metrics, and a report missing provenance fails.

---

# 18. Phase 11 — Old vs New Regression Analysis

Required historical cases:

```text
entry-date lookahead
delayed monthly revenue
Q4/Feb-Mar visibility
historical-universe drift
target-cohort self-training
```

Quantify ranking/performance differences.

## step-22: Old-output ingestion and comparison harness

- Estimated code: ~400 lines
- Depends on: step-2 (access to old outputs), step-6 (real Data Center data)
- Content:
  - read the old project's historical rankings/backtest results as exported data files. Old code is not copied.
  - align cohorts; compute rank correlation, Top-K overlap, performance deltas
- Tests first: alignment and diff metrics on small fixture exports.

## step-23: Historical leakage case studies

- Estimated code: ~300 lines + docs
- Content:
  - one reproducible analysis per required case, with quantified differences, in `docs/analysis/`
  - each case is also a permanent fixture-based regression test, unless already covered in step-7, step-8-a, or step-13
- Acceptance:
  - [ ] all five cases quantified and documented

---

# 19. Phase 12 — CLI

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

## step-24: CLI

- Estimated code: ~500 lines
- Content:
  - the commands above
  - explicit time flags (`--information-cutoff`, `--knowledge-cutoff`, `--system-cutoff`, `--cohort`); no flag lets the entry date act as a cutoff
- Tests first:
  - missing PIT flags are rejected
  - end-to-end smoke test on the fake client

---

# 20. Phase 13 — CI

Baseline CI (lint, type check, tests) exists since step-3. This phase consolidates the permanent guards.

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

## step-25: Permanent guard consolidation

- Estimated code: ~250 lines
- Content:
  - import-layer contracts across `data/`, `features/`, `labels/`, `training/`, `ranking/`, `backtest/`
  - leakage regression suite marked and required on every PR
  - end-to-end determinism test (same model/data → same ranking)
  - canonical-duplication guard tied to the ADR registry
  - a table in `docs/` mapping each guard above to its test
- Acceptance:
  - [ ] every guard listed above maps to a CI-enforced test

---

# 21. Migration from Old Project

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

# 22. Definition of Done

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
- [ ] every phase implemented test-first
- [ ] every step within 800 implementation lines or carries a written size exception

---

# 23. Core Boundary

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
