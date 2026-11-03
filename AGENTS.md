# Working on this repository

## Fast feedback

- `pytest -q -m "not slow and not db"`: seconds (features, estimators, readers, policies, agent verifier, monitoring).
- `pytest -q`: adds the API and pipeline tests (need `tmr all`) and the PostgreSQL test (`TMR_TEST_DATABASE_URL`).
- `tmr all --profile quick`: build, train, study, report and gate on a small market in a few minutes (CI runs it
  into temporary folders). `tmr all` (profile `full`) regenerates the committed reports in about 10 minutes.
- `ruff check tmr tests`, `ruff format --check tmr tests`, `mypy tmr`.
- `cd web && pnpm lint && pnpm exec tsc -b && pnpm test && pnpm e2e`: the console (Playwright with axe, on recorded
  API responses in `web/e2e/fixtures`).

## Invariants (each has a test or a gate)

- **Truth isolation.** Only `tmr/sim` and `tmr/evaluate` read the simulator (`config/world.yaml`, `data/truth`).
  Features, readers, models, policies, the agent, serving and monitoring work from logged data only
  (`tests/test_isolation.py`; `config.load("world")` raises).
- **One definition of every feature.** `tmr/features/state.py` serves training, offline evaluation, the market
  replay and the API; it is point-in-time (`tests/test_features.py`).
- **Positions are logged, and some lots are shuffled.** Every shortlist goes to `shortlist_log` with its positions;
  a share of lots is served shuffled so position bias can be measured. Do not remove either: the next model and
  the next evaluation depend on them (docs/adr/0002).
- **Offline numbers are position-corrected.** NDCG on logged labels is reported, never used to choose a model;
  the release gate uses the doubly-robust estimate (docs/adr/0003).
- **The model reads and words; code decides.** The planner's decisions pass a verifier (constraints, shortlist,
  deadline, no amounts) or are replaced by the code's plan (`tests/test_agent.py`).
- **Settings live in `config/`**: ranking, models, release gate, monitoring, agent. Not in code.
- **Generated files are not edited by hand:** `docs/REPORT.md`, `reports/*.json`, `reports/release.md`,
  `reports/heldout/*/first_run.json`.

## Held-out sets

`heldout/<set>/lots.yaml` are written from `heldout/WRITING_LOTS.md` by someone who never saw the code or data;
the held-out month is the market's last month. Never change readers, features or models to do better on a
held-out set. A set's first run (`reports/heldout/<set>/first_run.json`) is never rewritten. If you study a set's
failures, write `regression` to `heldout/<set>/STATUS` and have someone who has not seen the code write a new set.
