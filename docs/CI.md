# Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request to `master`.

## What CI does

### Backend job

1. Checkout the repository.
2. Set up Python 3.12.
3. `pip install -r requirements.txt` (the same file the README uses).
4. Rebuild the synthetic dataset and evaluation reference labels, exactly as a
   fresh clone would:
   - `python -m scripts.generate_dataset`
   - `python -m scripts.validate_dataset`
   - `python -m scripts.generate_evaluation_cases`
5. `python -m scripts.seed_database`.
6. `python -m pytest -o addopts="" -q` — the full suite, including:
   - the grounding and refusal gate tests (an unsupported claim fails the build),
   - the next-action lexicon and sparse-evidence tests,
   - the role-security tests,
   - the human-evaluation framework tests.
7. `python -m scripts.measure_next_action` — confirms the evaluation still runs
   and prints the next-action metrics.

### Frontend job

1. Checkout the repository.
2. Set up Node 20.
3. `npm ci` in `frontend/` (uses the committed lockfile).
4. `npm run build` — runs `tsc -b && vite build`, so **type errors fail CI**.

## When CI fails

| Failure | Likely cause |
|---------|--------------|
| `generate_dataset` or `validate_dataset` | dataset generator regression, or a changed seed |
| `seed_database` imports 0 tickets | processed CSVs missing; run the generator |
| pytest | a behavioural regression, most often in an engine or the generator |
| `measure_next_action` | the evaluation pipeline broke; check the scorer in `evaluation_service.py` |
| `npm run build` | a TypeScript error or a broken import |

## Notes

- The suite uses a temporary SQLite database created by `tests/conftest.py`, so CI
  never touches a developer's `ticket_progress.db`.
- The dataset is deterministic (seed 42), so a CI failure on data generation
  always reflects a real code change.
- CI does not run the LLM generator, because it is optional and has no provider
  configured. The grounding gate is still exercised, against the rule-based
  generator, in both the tests and via the API.
