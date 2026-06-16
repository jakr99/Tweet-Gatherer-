# Balanced Fill Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a one-command collection workflow that fills each of the eight labeled buckets to 50 candidates and caps overfilled buckets.

**Architecture:** Add pagination-aware collection support, a pruning helper that deletes overflow rows after labeling, and a new `fill-balanced` CLI command. Update `collect_tweets.sh` so the user-facing collection script runs the full collect-download-label-balance loop.

**Tech Stack:** Python CLI, SQLite `CandidateStore`, existing X API client, existing OpenAI classifier, pytest.

---

### Task 1: Add Balanced Pruning Tests

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `tests/test_run_script.py`

- [ ] Add a CLI test that monkeypatches collection to insert labeled candidates for all eight cases plus one overflow row, runs `fill-balanced --target-per-case 1`, and asserts the database has exactly one row per case.
- [ ] Update the `collect_tweets.sh` test to expect `research-agent fill-balanced`, `TARGET_PER_CASE`, `MAX_ROUNDS`, `MIN_CONFIDENCE`, and no direct `download-images` command.

### Task 2: Add Store Deletion Support

**Files:**
- Modify: `research_agent/store.py`

- [ ] Add `delete_candidates(keys: list[tuple[str, str]]) -> int`.
- [ ] Use `executemany` with `delete from candidates where tweet_id = ? and image_id = ?`.
- [ ] Return the number of requested keys after executing deletion.

### Task 3: Add Pagination Support

**Files:**
- Modify: `research_agent/x_api.py`
- Modify: `research_agent/cli.py`
- Modify: `tests/test_x_api.py`

- [ ] Add an optional `next_token` argument to `XApiClient.recent_search_params` and `search_recent`.
- [ ] Include `pagination_token` only when `next_token` is present.
- [ ] Let `_collect_from_config` accept an optional `pagination_tokens` dictionary keyed by query name.
- [ ] After each search, write `payload["meta"]["next_token"]` back into the dictionary for that query.

### Task 4: Add Fill-Balanced Command

**Files:**
- Modify: `research_agent/cli.py`
- Modify: `README.md`

- [ ] Add the `fill-balanced` parser and command branch.
- [ ] Implement `_fill_balanced`, which loops collection, image download, auto-labeling, pruning, count printing, and export.
- [ ] Implement `_enforce_balanced_target`, which keeps the highest-confidence rows up to target and deletes overflow high-confidence rows.
- [ ] Return nonzero if the target is not reached after all rounds.

### Task 5: Update Script

**Files:**
- Modify: `collect_tweets.sh`

- [ ] Change the script to call `research-agent fill-balanced`.
- [ ] Set cost-controlled test defaults `LIMIT=25`, `TARGET_PER_CASE=5`, `MAX_ROUNDS=3`, `MIN_CONFIDENCE=0.65`.
- [ ] Keep `label_tweets.sh` unchanged.

### Task 6: Verify

**Files:**
- Run tests only.

- [ ] Run `python3 -m pytest -q`.
- [ ] Run `python3 -c "import yaml; yaml.safe_load(open('config/queries.yaml', encoding='utf-8')); print('config/queries.yaml OK')"` to confirm config syntax remains valid.
