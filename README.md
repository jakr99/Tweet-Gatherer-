# Research Agent

Local Python agent for collecting candidate Twitter/X image tweets for a balanced disaster communication and metaphor dataset.

The tool is designed for candidate gathering, not final annotation. Labels are provisional until you review them.

## Setup

Use Python 3.11 or newer.

```bash
python3 -m pip install -e .
```

Paste your X API bearer token into `.env`:

```text
X_BEARER_TOKEN=your-token
```

Initialize the local workspace:

```bash
research-agent init
```

## Collect From X API

Edit `config/queries.yaml` to tune disaster and non-disaster searches. Then run:

```bash
research-agent collect --config config/queries.yaml --limit 100
```

The collector uses X API recent search and requests image media expansions. Direct browser scraping is intentionally not part of this first version.

## Import Candidate IDs Or URLs

You can import a text file with one tweet URL or ID per line:

```bash
research-agent import path/to/tweets.txt
```

CSV imports can include `tweet_id`, `tweet_url`, `url`, or `id` columns.

Imported references are stored even before hydration so you can keep track of leads when API quota is limited.

## Download Images

```bash
research-agent download-images
```

Images are stored under:

```text
data/images/<tweet_id>/<image_id>.<extension>
```

Rows remain in the database when image downloads fail, with the failure recorded.

## Export Excel Workbook

```bash
research-agent export --output exports/candidates.xlsx
```

The workbook contains:

- `candidates`: tweet ID, image ID, text, image URL, image path, labels, review status, source query, timestamps, and notes.
- `balance_summary`: counts for all eight target cells, including zero-count cells.
- `collection_runs`: query run metadata and errors.

## Balance Counts

```bash
research-agent balance
```

The eight tracked cells are:

- literal text + literal image + real disaster
- literal text + figurative image + real disaster
- figurative text + literal image + real disaster
- figurative text + figurative image + real disaster
- literal text + literal image + not real disaster
- literal text + figurative image + not real disaster
- figurative text + literal image + not real disaster
- figurative text + figurative image + not real disaster

## Research Notes

This project stores local metadata and optional image files for annotation. Follow X/Twitter terms, your institution's research requirements, and dataset redistribution rules. For many research releases, sharing tweet IDs and annotation labels is safer than redistributing full tweet text or images.
