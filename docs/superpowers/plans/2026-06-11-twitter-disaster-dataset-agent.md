# Twitter/X Disaster Dataset Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Python CLI that collects, imports, stores, downloads, exports, and balances candidate Twitter/X image tweets for disaster metaphor research.

**Architecture:** The project is a small Python package with focused modules for labels, persistence, imports, X API collection, image downloads, Excel export, and CLI orchestration. SQLite is the source of truth, and exports are generated from the database.

**Tech Stack:** Python 3.14, argparse, sqlite3, urllib, csv, PyYAML, pytest, stdlib ZIP/XML `.xlsx` generation.

---

## File Structure

- `pyproject.toml`: package metadata, console script, pytest path.
- `.gitignore`: ignore local data, exports, env files, caches, and `.DS_Store`.
- `.env.example`: documents `X_BEARER_TOKEN`.
- `config/queries.yaml`: starter disaster and non-disaster search queries.
- `README.md`: setup, commands, workflow, and research/compliance notes.
- `research_agent/__init__.py`: package marker.
- `research_agent/models.py`: dataclasses and controlled label values.
- `research_agent/labels.py`: eight-way case labels and balance scaffolding.
- `research_agent/store.py`: SQLite schema and candidate persistence.
- `research_agent/importer.py`: CSV/text tweet ID and URL import parsing.
- `research_agent/x_api.py`: X API client and response-to-candidate mapping.
- `research_agent/images.py`: image download paths and downloader.
- `research_agent/xlsx.py`: minimal workbook writer using stdlib XML/ZIP.
- `research_agent/exporter.py`: workbook sheet construction.
- `research_agent/cli.py`: `research-agent` command-line interface.
- `tests/`: pytest coverage for core behavior.

## Tasks

### Task 1: Project Scaffold and Labels

- [ ] Write failing tests for eight-way case label derivation and zero-filled balance rows in `tests/test_labels.py`.
- [ ] Run `python3 -m pytest tests/test_labels.py -q` and confirm failure from missing package.
- [ ] Add package scaffold, `models.py`, and `labels.py`.
- [ ] Re-run label tests and confirm pass.

### Task 2: SQLite Store and Imports

- [ ] Write failing tests for tweet URL parsing, raw ID parsing, candidate upserts, and duplicate prevention.
- [ ] Run targeted tests and confirm failure.
- [ ] Implement `store.py` and `importer.py`.
- [ ] Re-run targeted tests and confirm pass.

### Task 3: X API Mapping and Collection

- [ ] Write failing tests that map a fixture X API response with media includes into tweet-image candidate rows.
- [ ] Run targeted tests and confirm failure.
- [ ] Implement `x_api.py` with recent-search parameters, credential handling, and response mapping.
- [ ] Re-run targeted tests and confirm pass.

### Task 4: Image Download and Excel Export

- [ ] Write failing tests for stable image paths, failed download recording, and required workbook sheet names.
- [ ] Run targeted tests and confirm failure.
- [ ] Implement `images.py`, `xlsx.py`, and `exporter.py`.
- [ ] Re-run targeted tests and confirm pass.

### Task 5: CLI, Config, and Docs

- [ ] Write failing CLI smoke tests for `init`, `import`, `balance`, and `export`.
- [ ] Run targeted tests and confirm failure.
- [ ] Implement `cli.py`, `pyproject.toml`, `.gitignore`, `.env.example`, starter config, and README.
- [ ] Run full test suite with `python3 -m pytest -q`.
- [ ] Run CLI smoke commands against a temporary workspace.
- [ ] Commit implementation if verification passes.

## Acceptance Check

- X API credentials can be configured without committing secrets.
- X API collector can map image-bearing API responses into candidates.
- Tweet IDs/URLs can be imported from files.
- SQLite prevents duplicate tweet-image pairs.
- Image download paths are stable.
- Excel export contains `candidates`, `balance_summary`, and `collection_runs`.
- Balance output includes all eight cells, including zeros.
- README explains setup, use, and research/compliance cautions.
