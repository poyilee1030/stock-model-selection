# AGENTS.md

## Purpose

This repository implements `stock-model-selection`.

Version 1 trains and evaluates stock-selection models using PIT-safe data from `stock-data-center`.

Version 1 intentionally does NOT use `stock-eps-model` or predicted EPS features.

Highest-priority requirement:

> The model that ranks a cohort may use only information available before that cohort and labels from earlier cohorts whose outcomes were already complete.

---

# 1. Source of Truth

The canonical roadmap is:

```text
ROADMAP.md
```

Work one phase at a time.

Do not begin the next phase until all current acceptance criteria pass.

At the end of each phase, produce:

```text
Phase N Acceptance Report
```

with PASS/FAIL and concrete evidence.

If a required criterion fails, stop.

---

# 2. Fixed Technology Stack

Unless `ROADMAP.md` is explicitly amended:

```text
Python 3.12+
Pydantic 2.x
pandas
numpy
scikit-learn
LightGBM
httpx
pytest
joblib
```

Do not add stock-data database drivers.

---

# 3. Absolute Rule — No Direct Stock DB Access

This repository must never connect directly to the `stock-data-center` database.

Forbidden:

```python
create_engine(DATA_CENTER_DB_URL)
psycopg.connect(...)
asyncpg.connect(...)
```

Forbidden concepts:

```text
raw SQL against Data Center
knowledge of Data Center table names
manual publication-time SQL filters
```

All stock/accounting data comes through the Data Center API or SDK.

---

# 4. Absolute Rule — No `stock-eps-model` Dependency in v1

Do not add:

```text
predicted_eps
EPS prediction artifacts
stock_eps_model imports
EPS model API client
```

in v1.

Historical actual EPS from Data Center is allowed if PIT-safe.

If predicted EPS is added later, it requires:

```text
new feature schema version
ADR
ROADMAP amendment
incremental-value evaluation
```

---

# 5. PIT Context Is Mandatory

Preferred types:

```text
MarketPitContext
    information_as_of
    knowledge_as_of

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

Do not collapse these into an ambiguous `date`.

---

# 6. Entry Date Is Never the Information Cutoff

This is a non-negotiable invariant.

Forbidden:

```python
fetch_features(as_of=entry_date)
```

unless a future explicit contract states that `entry_date == information_as_of`.

Normal design:

```text
information_as_of < entry_date
```

The old entry-date look-ahead bug must remain permanently covered by regression tests.

---

# 7. Historical Universe Must Be PIT-Safe

Do not use today's active-stock list for historical cohorts.

The universe must come from Data Center under the cohort PIT context.

A future-listed stock cannot appear early.

A later-delisted stock may appear historically if it was eligible then.

---

# 8. Data Center Client Boundary

All external stock-data access goes through one client abstraction.

Feature modules do not issue HTTP requests directly.

Tests must be able to replace the client with a fake/in-memory implementation.

---

# 9. Feature Rules

Feature modules:

- accept normalized PIT-safe data
- compute deterministic features
- do not query databases
- do not query external services
- do not decide publication visibility
- do not future-fill unavailable historical data
- do not use predicted EPS in v1

Every feature must document:

```text
inputs
formula
missing-value behavior
dtype
schema version
```

---

# 10. Feature Schema

The base schema should be explicitly versioned, for example:

```text
selection_features_v1_base
```

Do not rely on dataframe column order alone.

Models must fail loudly on incompatible schemas.

---

# 11. Forward-Return Label Rules

Future return is allowed as a historical supervised label.

It is never allowed as a feature.

A label must define:

```text
entry date
exit date
entry price convention
exit price convention
label_available_at
```

A label is training-eligible only after its horizon has completed.

---

# 12. Target Cohort Cannot Train Itself

This is a P0 leakage invariant.

For target cohort C:

```text
train_model_for(C)
```

must exclude:

```text
C
all later cohorts
all earlier cohorts whose labels are not yet available
```

Do not infer eligibility from filenames or current DB state.

Derive it from the explicit label-availability contract.

---

# 13. Training Split Rules

Primary historical evaluation must be time-aware.

Use:

```text
walk-forward
expanding window
explicit rolling window
```

Do not use random train/test split as the primary evaluation.

---

# 14. Dataset Construction Rule

Do not build one present-day dataset and merely slice it by historical dates.

Each cohort's features must be reconstructed with its own PIT context.

---

# 15. Missing Data Rules

Historical missing data remains missing unless a documented transformation uses only already-visible data.

Forbidden:

```text
future fill
later financial statement substitution
later revenue substitution
current-value substitution
```

ML imputation is separate from historical availability.

---

# 16. Model Artifact Rules

Every selection model must retain:

```text
model hash
target cohort
training cutoff
PIT context
Data Center provenance
training dataset hash
feature schema version
hyperparameters
random seed
git commit
package versions
metrics
```

A model without reproducible provenance is incomplete.

---

# 17. Ranking Artifact Rules

Every ranking batch must retain:

```text
ranking ID
model ID
cohort ID
playbook date
PIT context
entry date
candidate count
Top-K
feature dataset hash
Data Center provenance
git commit
```

Once published, a ranking artifact is immutable.

A later historical rerun creates a new reconstruction artifact; it must not overwrite the original production ranking.

---

# 18. Backtest Rules

Backtester consumes frozen ranking artifacts.

It must not:

- rebuild features
- query financial data to "fix" a ranking
- apply month-specific PIT patches
- silently skip known-bad cohorts instead of fixing data semantics

Trading rules, fees, slippage, and rebalance logic must be explicit.

---

# 19. No Month-Specific Leakage Workarounds

Forbidden pattern:

```python
if month in (2, 3):
    skip_entry = True
```

when the underlying reason is unavailable financial information.

Availability belongs to Data Center.

Missing features should be handled by the model/data contract, not hidden inside backtest logic.

---

# 20. Leakage Regression Tests

Permanently protect at least:

```text
7/11 feature request cannot use 7/13 entry-date data
7/10 cutoff cannot see later revenue through selection code
future Q4 data cannot leak into earlier cohort features
today's universe cannot replace historical universe
target cohort cannot train itself
incomplete forward-return label cannot enter training
future return cannot appear as feature
same PIT/model inputs -> same ranking
```

A leakage bug is not fixed until a regression test exists.

---

# 21. Direct DB Guard

Add an architectural/static test that detects forbidden dependencies such as:

```text
psycopg
asyncpg
Data Center create_engine
known Data Center table names
```

Do not rely only on review discipline.

---

# 22. No-EPS-Dependency Guard

During v1, tests/static checks should reject accidental dependencies on:

```text
stock_eps_model
predicted_eps
eps_prediction
```

except documentation that explicitly explains their exclusion.

---

# 23. Hashing Rules

Deterministic dataset/model/ranking identities must not include unstable values such as:

```text
temporary paths
random UUIDs
wall-clock timestamps
```

unless those values are part of semantic identity.

Timestamps may exist in manifests without contaminating deterministic content hashes.

---

# 24. Timezone Rules

All real-world timestamps must be timezone-aware.

Taiwan-market interpretation uses:

```text
Asia/Taipei
```

Use ISO 8601 with explicit offsets at system boundaries.

Never silently compare naive and aware datetimes.

---

# 25. Error Handling

Fail loudly on:

```text
missing PIT context
invalid temporal ordering
entry_date used as feature cutoff
target cohort found in training data
incomplete label horizon
incompatible feature schema
missing provenance
ambiguous ranking/model artifact
```

Never silently fall back to latest data.

---

# 26. Migration Rules

Do not copy old:

```text
strategies/
models_selection/
backtester/
```

wholesale.

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
DB setup
manual publish-time filters
entry-date feature lookup
current-universe assumptions
month-specific PIT workarounds
implicit model-date logic
```

If old behavior conflicts with PIT correctness, PIT correctness wins.

---

# 27. Scope Discipline

When implementing one phase:

- implement only that phase
- do not pre-build later phases unless required
- do not add EPS prediction support in v1
- do not refactor unrelated modules
- do not change PIT semantics silently
- record major decisions in `docs/decisions/`
- do not weaken acceptance criteria

---

# 28. Phase Completion Checklist

Before declaring a phase complete:

```text
tests pass
documentation updated
acceptance criteria evaluated
no direct DB access introduced
no stock-eps-model dependency introduced
entry-date invariant preserved
target-cohort exclusion preserved
PIT invariants preserved
no leakage regression introduced
```

Then provide the Acceptance Report.

---

# 29. Priority Order

When tradeoffs exist:

```text
1. no leakage
2. PIT correctness
3. target-cohort isolation
4. reproducibility
5. provenance
6. deterministic behavior
7. clear contracts
8. maintainability
9. model performance
10. convenience
```

Do not improve backtest performance by weakening the first six.

---

# 30. Core Invariants

A. `stock-model-selection` never directly accesses the stock DB.

B. Version 1 does not depend on `stock-eps-model`.

C. Every historical cohort uses an explicit PIT context.

D. `entry_date` is not an information cutoff.

E. Historical universe is PIT-safe.

F. Future return is a label, never a feature.

G. A target cohort cannot train the model that ranks itself.

H. Cohorts with incomplete label horizons cannot enter training.

I. Published ranking artifacts are immutable.

J. Backtester consumes rankings and never repairs PIT mistakes.

K. Every model, ranking, and backtest retains reproducible provenance.

---

# 31. Core Boundary

```text
stock-data-center owns:
    source collection
    security universe history
    publication evidence
    ingestion history
    revision history
    PIT visibility

stock-model-selection owns:
    selection feature engineering
    forward-return labels
    training datasets
    walk-forward selection models
    ranking / Top-K
    ranking artifacts
    backtesting
```

Version 1 must remain independent of `stock-eps-model`.
