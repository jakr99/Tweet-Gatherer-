# Auto-Label Balanced Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OpenAI-backed provisional multimodal labeling and balanced collection commands for the eight target tweet-image cases.

**Architecture:** Add focused modules for OpenAI request construction/parsing and balanced target counting. Extend the SQLite model/store with internal confidence/explanation fields while keeping the Excel candidate sheet limited to the user-requested eight columns.

**Tech Stack:** Python 3.14, argparse, sqlite3, urllib, OpenAI Responses API over HTTPS, pytest fixtures/fake clients.

---

## File Structure

- Create `research_agent/auto_label.py`: prompt construction, image encoding, OpenAI client, JSON parsing, validation, row labeling.
- Create `research_agent/balancer.py`: high-confidence case counts and target completion helpers.
- Modify `research_agent/models.py`: add internal confidence/explanation fields.
- Modify `research_agent/store.py`: migrate/add columns, list candidates needing labels, update labeling metadata.
- Modify `research_agent/cli.py`: add `auto-label` and `collect-balanced` commands.
- Modify `research_agent/exporter.py`: preserve existing eight-column candidate export.
- Modify `.env`: document OpenAI key/model placeholders.
- Modify `README.md`: document provisional labels, `auto-label`, and `collect-balanced`.
- Add tests in `tests/test_auto_label.py`, `tests/test_balancer.py`, and extend existing CLI/export tests.

## Tasks

### Task 1: Data Model and Store Migration

- [ ] Write tests for store migration adding `text_confidence`, `image_confidence`, `disaster_confidence`, `label_explanation`, `label_model`, and `labeled_at`.
- [ ] Run targeted tests and confirm failure.
- [ ] Extend `Candidate` and `CandidateStore` to preserve the new fields.
- [ ] Add `list_candidates_needing_labels()` and `update_candidate_labels()`.
- [ ] Run targeted tests and confirm pass.

### Task 2: Auto-Label Core

- [ ] Write tests for base64 image data URL construction and prompt payload contents.
- [ ] Write tests for valid/invalid model JSON parsing.
- [ ] Run targeted tests and confirm failure.
- [ ] Implement `research_agent/auto_label.py` with fake-client-friendly classification functions.
- [ ] Run targeted tests and confirm pass.

### Task 3: CLI Auto-Label

- [ ] Write CLI tests for missing `OPENAI_API_KEY`, fake successful labeling, and export columns unchanged.
- [ ] Run targeted tests and confirm failure.
- [ ] Add `research-agent auto-label --limit --min-confidence --relabel`.
- [ ] Run targeted tests and confirm pass.

### Task 4: Balanced Collection

- [ ] Write tests for high-confidence target counts and stopping when every case reaches target.
- [ ] Run targeted tests and confirm failure.
- [ ] Implement `research_agent/balancer.py` and `collect-balanced` command orchestration.
- [ ] Run targeted tests and confirm pass.

### Task 5: Docs, Runner, and Verification

- [ ] Update `.env`, `README.md`, and `run_agent.sh` usage notes.
- [ ] Run `python3 -m pytest -q`.
- [ ] Run non-network CLI checks for `auto-label` missing-key behavior and `balance`.
- [ ] Commit implementation.

## Acceptance Check

- Existing candidates can be labeled with provisional LLM labels.
- Confidence/explanation metadata is stored internally.
- `candidates.xlsx` still only exports the eight requested candidate columns.
- `collect-balanced` can pursue even target counts across all eight cases.
- Tests cover store migration, model parsing, CLI behavior, confidence thresholds, and export constraints.
