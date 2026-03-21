# Tests

Python tests live here and import Genify’s **`backend`** from [`src/genify/`](../src/genify/) (see each file’s `sys.path` tweak).

## Recommended: dedicated test venv (`.venv-test`)

Keeps test deps (including **pytest**) separate from a dev `.venv` if you use one.

From the **repository root**:

```bash
./scripts/setup_test_venv.sh
./scripts/run_tests.sh
```

- Creates **`.venv-test/`** (gitignored) with `tests/requirements-test.txt` → Genify [`requirements.txt`](../src/genify/requirements.txt) **+ pytest**.
- **`run_tests.sh`** uses `unittest` discovery by default. For pytest:

  ```bash
  TEST_RUNNER=pytest ./scripts/run_tests.sh
  # or
  .venv-test/bin/python -m pytest tests/ -v
  ```

Override interpreter for the setup script:

```bash
PYTHON=/path/to/python3.12 ./scripts/setup_test_venv.sh
```

To recreate the venv from scratch: `rm -rf .venv-test` then run `setup_test_venv.sh` again.

## Alternative: single `.venv` for dev + tests

```bash
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r src/genify/requirements.txt
pip install -r tests/requirements-test.txt   # adds pytest
python -m unittest discover -s tests -p 'test_*.py' -v
```

Use **Python 3.11 or 3.12** if `pip install` fails on 3.14 (some wheels are not published yet).

## `test_genify_sessions_answer.py`

Smoke tests for `POST /api/sessions/{id}/answer` (**409** vs **200**) with a **mocked** Lakebase pool (no real PostgreSQL).

Startup: `TestClient` runs the app **lifespan**; tests patch `backend.main.init_db` and `backend.main.seed_templates` so Lakebase is not touched. Per-request DB access is still mocked via `backend.routes.sessions._pool`.
