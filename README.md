# Research Agent

Local Python agent for collecting candidate Twitter/X image tweets for a balanced disaster communication and metaphor dataset.

The tool is designed for candidate gathering, not final annotation. Labels are provisional until you review them.

## Setup

Use Python 3.11 or newer.

```bash
python3 -m pip install -e .
```

Paste your X API bearer token and OpenAI API key into `.env`:

```text
X_BEARER_TOKEN=your-token
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-5.5
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

For queries seeded as `not_real_disaster`, you can set `required_terms` in `config/queries.yaml`. Those terms must appear in the returned tweet text before the candidate is stored, which keeps non-disaster rows focused on disaster terminology used outside an actual disaster context.

After auto-labeling, `fill-balanced` also removes any candidate labeled `not_real_disaster` if its tweet text does not contain the shared disaster terminology list. This prevents real-disaster-targeted searches from leaking unrelated non-disaster examples into the final dataset.

For balanced collection, each query can also set `target_cases`. During `fill-balanced`, the agent checks which buckets are still below the target and only runs queries whose `target_cases` overlap those underfilled buckets. Queries without `target_cases` still run for compatibility with older custom configs.

## One-Command Run

After setup, run the full collection/export workflow with:

```bash
./run_agent.sh
```

The default collection limit is `10` per query. Pass a number to change it:

```bash
./run_agent.sh 100
```

The script runs `init`, `collect-balanced`, `balance`, and exports `exports/candidates.xlsx`.

Optional tuning:

```bash
TARGET_PER_CASE=12 MAX_ROUNDS=5 MIN_CONFIDENCE=0.65 ./run_agent.sh 100
```

`collect-balanced` collects candidates, downloads images, auto-labels with the configured OpenAI model, and tries to fill each of the eight target cases.

## Two-Phase Run

If you want a balanced dataset in one command, use the collection script. It collects, downloads images, auto-labels every stored candidate, prunes overfilled buckets, removes any still-unlabeled leftovers, and exports the workbook. When a bucket has more than the target, the script keeps the strongest-confidence rows first; it does not shrink a bucket below target just because a kept row is lower-confidence.

By default, it runs a smaller test collection: 5 candidates in each of the eight buckets, up to 3 rounds, and 25 X results per query each round.

```bash
./collect_tweets.sh
```

Pass a number to change the X API page size per query:

```bash
./collect_tweets.sh 100
```

Optional tuning:

```bash
TARGET_PER_CASE=50 MAX_ROUNDS=20 MIN_CONFIDENCE=0.65 ./collect_tweets.sh 50
```

If collection or labeling stops because of API credits or rate limits, wait for the reset and rerun the same command to keep filling the buckets. To label existing unknown rows that came from manual imports or older runs without collecting more tweets, run:

```bash
./label_tweets.sh 50
```

`label_tweets.sh` does not collect more tweets; it resumes labeling rows that still have unknown labels.

You can also call the balanced fill command directly:

```bash
research-agent fill-balanced --target-per-case 50 --max-rounds 20 --limit-per-query 50
```

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

## Auto-Label Candidates

Use a multimodal OpenAI model to assign provisional labels:

```bash
research-agent auto-label --limit 50 --min-confidence 0.65
```

The model labels are best-effort suggestions for review, not final ground truth.

To collect and label toward an even distribution:

```bash
research-agent collect-balanced --target-per-case 12 --max-rounds 5 --limit-per-query 100
```

## Export Excel Workbook

```bash
research-agent export --output exports/candidates.xlsx
```

The workbook contains:

- `candidates`: tweet ID, image ID, text, image URL, image path, text label, image label, and disaster label.
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
