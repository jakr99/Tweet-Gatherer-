# Twitter/X Disaster Metaphor Dataset Agent Design

Date: 2026-06-11

## Goal

Build a local research agent that gathers candidate multimodal Twitter/X posts for a balanced disaster-communication dataset. The dataset is intended to support annotation and analysis of literal and figurative language in tweet text and images, across disaster-relevant and non-disaster-relevant examples.

The agent must collect candidate posts with images, store tweet/media metadata, optionally download images, export an Excel workbook, and track balance across the eight requested case types:

1. literal text + literal image + refers to a real disaster
2. literal text + figurative image + refers to a real disaster
3. figurative text + literal image + refers to a real disaster
4. figurative text + figurative image + refers to a real disaster
5. literal text + literal image + does not refer to a real disaster
6. literal text + figurative image + does not refer to a real disaster
7. figurative text + literal image + does not refer to a real disaster
8. figurative text + figurative image + does not refer to a real disaster

## Collection Strategy

The first implementation will use an API/import-first design.

### Primary: X API Collector

The primary collector will use X/Twitter API access through a bearer token supplied by the researcher. It will query recent posts with image media using configured search queries. Queries will be stored in editable configuration files so the researcher can tune disaster and non-disaster searches without changing code.

The collector will request tweet fields and media expansions needed to store:

- tweet ID
- tweet text
- creation time
- author ID, if available under the API response
- media/image ID or media key
- media type
- image URL or preview image URL
- source query name
- source query text
- collection timestamp

The implementation should use documented API paths and should not require the user to provide their X password.

### Secondary: Import Collector

The import collector will accept researcher-provided candidate data so the workflow remains useful when API quota is limited. Initial import formats:

- CSV file containing tweet IDs or tweet URLs
- plain-text file containing one tweet URL or ID per line

Imported IDs can be hydrated through the API when credentials are available. If hydration is not possible, imported rows can still be stored as candidate references with missing metadata marked explicitly.

### Out of Scope for Version 1

Direct browser scraping of X pages is out of scope for the first version. X changes frequently, access controls vary, and scraping can create terms and reproducibility problems. The project will keep collectors pluggable so a future backend can be added if the researcher later secures a compliant collection method.

## Data Model

The local store will be SQLite. It will keep normalized candidate records and avoid duplicate tweet/media rows across repeated collection runs.

### Candidate Fields

Each candidate image row represents one tweet-image pair. A tweet with multiple images becomes multiple candidate rows because each image may carry different literal or figurative meaning.

Required fields:

- `tweet_id`
- `image_id`
- `tweet_text`
- `image_url`
- `image_path`
- `text_label`
- `image_label`
- `disaster_label`
- `case_label`
- `review_status`
- `source`
- `source_query`
- `collected_at`
- `notes`

Label values:

- `text_label`: `literal`, `figurative`, `unknown`
- `image_label`: `literal`, `figurative`, `unknown`
- `disaster_label`: `real_disaster`, `not_real_disaster`, `unknown`
- `review_status`: `candidate`, `needs_review`, `accepted`, `rejected`

The `case_label` is derived from the three label dimensions when none are `unknown`.

## Image Storage

Downloaded images will be stored under `data/images/` using stable names derived from tweet ID and image ID:

```text
data/images/<tweet_id>/<image_id>.<extension>
```

The database and Excel export will store both the source image URL and local path. Failed image downloads will keep the candidate row and record the failure reason.

## Labeling and Annotation Support

Version 1 will treat all automated labels as provisional. The tool can assign obvious seed labels from query configuration, but it must not present these as final human annotations.

Recommended default behavior:

- disaster-focused queries seed `disaster_label=real_disaster`
- non-disaster queries seed `disaster_label=not_real_disaster`
- text and image figurativeness start as `unknown` unless supplied during import or later review
- every collected row starts with `review_status=candidate`

This keeps the tool honest: it finds likely candidates and tracks balance, while the researcher still decides final annotation labels.

Future classification modules can be added for:

- text metaphor/figurative-language suggestions
- image literal/figurative suggestions
- multimodal explanation fields
- annotator agreement exports

## Excel Export

The export command will write an `.xlsx` workbook to `exports/`.

Workbook sheets:

1. `candidates`
   - one row per tweet-image pair
   - includes tweet ID, image ID, tweet text, image URL, image path, provisional labels, review status, source query, timestamps, and notes
2. `balance_summary`
   - counts for each of the eight target cells
   - separates `candidate`, `accepted`, `rejected`, and `needs_review` rows where useful
3. `collection_runs`
   - optional run metadata such as query name, query text, started time, finished time, result count, and errors

The balance summary must make missing cells visible with zero counts, not omit them.

## Command-Line Interface

The first version will expose a Python CLI.

Planned commands:

```bash
research-agent init
research-agent collect --config config/queries.yaml --limit 100
research-agent import path/to/tweets.csv
research-agent download-images
research-agent export --output exports/candidates.xlsx
research-agent balance
```

The CLI should be runnable locally and should create needed folders on first use.

## Configuration

Configuration files will live under `config/`.

Initial files:

- `config/queries.yaml`: named search queries and seed labels
- `.env.example`: documents required environment variables such as `X_BEARER_TOKEN`

The real `.env` file will be ignored by Git.

## Error Handling

The agent should preserve partial progress. API errors, rate limits, hydration failures, duplicate rows, and image download failures should be recorded without crashing the whole run when possible.

Expected behavior:

- duplicate tweet-image pairs are skipped or updated idempotently
- rate-limit responses stop the current collection run with a clear message
- failed image downloads leave metadata intact and mark `image_path` empty
- malformed imports report row-level errors
- missing API credentials fail only API-dependent commands

## Research and Compliance Notes

The project will store source identifiers and local metadata needed for annotation, but it should be designed so the researcher can refresh or remove stored content if posts are deleted or changed. The design avoids collecting private messages, credentials, or non-public content.

The README should include a research-use note reminding the user to follow X/Twitter terms, institutional review requirements, and dataset redistribution rules. For many research releases, sharing tweet IDs and annotation labels may be safer than redistributing full tweet text or images.

## Testing Strategy

The implementation should be built test-first.

Key tests:

- candidate rows derive the correct eight-way `case_label`
- balance summary includes all eight cells, including zero-count cells
- import parser extracts tweet IDs from URLs and raw IDs
- duplicate tweet-image rows do not create duplicate candidates
- Excel export contains required sheets and columns
- image downloader records successful and failed downloads correctly
- API collector maps X API media includes into candidate rows

Network-dependent behavior should be tested through fixtures or local fake responses so tests do not require live X API access.

## Acceptance Criteria

The feature is complete when:

- a user can configure X API credentials without committing secrets
- the agent can collect image-bearing candidate tweets through the X API
- the agent can import candidate tweet IDs or URLs from local files
- tweet-image pairs are stored locally without duplicates
- images can be downloaded into a stable folder structure when URLs are available
- Excel export includes tweet ID, image ID, tweet text, image URL, image path, labels, review status, source query, and timestamps
- balance reporting explicitly counts all eight requested cases
- tests cover core storage, import, balance, image path, and export behavior
- the README explains setup, collection, import, export, and research/compliance cautions
