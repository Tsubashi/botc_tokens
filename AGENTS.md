# Repository Guide

## Overview

- This repository contains the `botc_tokens` Python CLI for creating, updating, trimming, and grouping Blood on the Clocktower token assets.
- Application code lives in `src/botc_tokens/`.
- Tests live in `tests/`.
- Project configuration lives in `pyproject.toml`.

## Development Environment

- Use the repo-local uv virtual environment in `.venv` for all development commands.
- Prefer invoking tools through the checked-in environment directly, for example `./.venv/bin/pytest`.
- If the environment needs to be created or refreshed, use uv rather than raw `venv` tooling.
- Install test dependencies with `uv sync --extra test`.

## Runtime Prerequisites

- This project depends on ImageMagick through `wand`.
- On Apple Silicon, set `MAGICK_HOME=/opt/homebrew/` before running commands that exercise image generation if Wand does not auto-detect ImageMagick.

## Working In The Repo

- Keep imports, formatting, and naming consistent with the existing codebase.
- Add or update tests whenever behavior changes.
- Prefer focused changes with corresponding test coverage in the same change.
- Do not consider a task complete until validation passes in the repo-local `.venv`.

## Test And Validation Requirements

- Test coverage is a hard requirement in this repository.
- Every change must maintain **100% test coverage** for the measured codebase.
- Do not merge, commit, or hand off work that drops coverage below 100%.
- When code changes add branches or error paths, add tests for them immediately.

Run validation from the repository root:

```bash
./.venv/bin/pytest -q
./.venv/bin/pytest --cov=src --cov-branch --cov-report=term-missing --cov-fail-under=100
```

Use targeted commands while iterating on specific files, like so:

```bash
./.venv/bin/pytest tests/test_main.py -q
```

If you need verbose failure details, use:

```bash
./.venv/bin/pytest -vv
```

## Linting

- Run `./.venv/bin/flake8` before finishing changes that touch Python code.
- Treat lint failures as blocking.

## Pull Request Expectations

- Summarize the behavior change clearly.
- Include the exact validation commands that were run.
- Call out any environment assumptions such as `MAGICK_HOME`.
- Ensure the full pytest suite passes and the 100% coverage command passes before requesting review.
