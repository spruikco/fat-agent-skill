# Contributing to FAT Agent with Superpowers

## Adding a New Module

1. Create a new file in `plugins/fat-agent/scripts/modules/` (e.g. `my_module.py`).
2. Subclass `BaseModule` from `base.py` and implement:
   - `name` — Short identifier (snake_case, e.g. `my_module`).
   - `detect(html: str) -> bool` — Return `True` if the module is relevant based on HTML signals.
   - `audit(html: str, url: str, **kwargs) -> list[dict]` — Return a list of finding dicts with keys: `category`, `check`, `priority` (P0-P3), `description`, `fix`.
3. Register the module in `scripts/modules/__init__.py` by importing it and adding it to the `MODULES` list.
4. Add detection tests in `tests/test_modules_<name>.py` and audit-output tests covering at least the happy path and a "no findings" case.
5. If the module should be included in an existing profile, update `scripts/profiles.py`.

## Running Tests

```bash
cd plugins/fat-agent
python3 -m pytest tests/ -v
```

All tests must pass before submitting a PR. There are no external service dependencies; the test suite uses HTML fixtures and mocked responses.

## Code Style

- **Formatter:** [black](https://github.com/psf/black) (default settings).
- **Linter:** [ruff](https://github.com/astral-sh/ruff) (see `pyproject.toml` for rule config).
- Run both before committing:
  ```bash
  black scripts/ tests/
  ruff check scripts/ tests/ --fix
  ```

## Pull Request Process

1. Fork the repo and create a feature branch from `develop`.
2. Make your changes, add tests, and ensure `pytest` and `ruff` pass.
3. Open a PR targeting `develop` with a clear description of what the change does and why.
4. A maintainer will review and merge.
