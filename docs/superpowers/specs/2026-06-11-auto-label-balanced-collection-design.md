# Auto-Label and Balanced Collection Design

Date: 2026-06-11

## Goal

Add automatic provisional labeling for collected tweet-image candidates and a balanced collection workflow that can aim for an even distribution across the eight target dataset cases.

The feature should help the researcher move from raw candidate collection to a reviewable, balanced annotation pool. It must not present model labels as final ground truth.

## Background

The current agent collects tweet-image candidates through the X API, downloads images, stores metadata in SQLite, exports `candidates.xlsx`, and reports balance across:

1. literal text + literal image + real disaster
2. literal text + figurative image + real disaster
3. figurative text + literal image + real disaster
4. figurative text + figurative image + real disaster
5. literal text + literal image + not real disaster
6. literal text + figurative image + not real disaster
7. figurative text + literal image + not real disaster
8. figurative text + figurative image + not real disaster

Collected rows often have `text_label=unknown` and `image_label=unknown`, so they appear in `incomplete_or_unknown_labels` until reviewed or labeled.

## Feasibility and Limits

Automatic labeling is possible with a multimodal model, but the output is a best-effort provisional annotation. Figurative language and figurative image use are interpretive research judgments, so the system must preserve reviewability and confidence information internally.

Balanced output also cannot be guaranteed from a fixed number of collected tweets. Some cases may be rare, especially `figurative_text__figurative_image__real_disaster`. The agent should collect and label a larger candidate pool, then keep high-confidence rows until each target case reaches the requested count where possible.

## Model Strategy

Use the OpenAI API for multimodal classification. The classifier will send:

- tweet text
- local image as a base64 data URL when `image_path` exists
- source image URL as fallback when no local image file is available
- a strict labeling rubric

The model response must be JSON with:

- `text_label`: `literal` or `figurative`
- `image_label`: `literal` or `figurative`
- `disaster_label`: `real_disaster` or `not_real_disaster`
- `text_confidence`: number from 0 to 1
- `image_confidence`: number from 0 to 1
- `disaster_confidence`: number from 0 to 1
- `explanation`: short human-readable rationale

Default model configuration:

- `OPENAI_API_KEY` in `.env`
- `OPENAI_MODEL` in `.env`, defaulting to `gpt-5.5`

The OpenAI image input implementation should use official multimodal API patterns with image URLs or base64 data URLs.

## Label Semantics

### Text Label

`literal`: tweet text primarily describes the situation directly without metaphor, idiom, analogy, or strongly figurative phrasing.

`figurative`: tweet text uses metaphor, idiom, analogy, personification, hyperbole, symbolic language, or other non-literal phrasing to communicate meaning.

### Image Label

`literal`: image appears to depict the event, object, place, or situation directly referenced by the tweet text.

`figurative`: image appears to support or add meaning symbolically, metaphorically, humorously, emotionally, or by analogy rather than directly depicting the referent.

### Disaster Label

`real_disaster`: tweet appears to refer to an actual disaster, emergency, hazard, crisis, or disaster-response context.

`not_real_disaster`: tweet uses disaster-related language or imagery outside an actual disaster context, such as sports, politics, entertainment, personal frustration, jokes, marketing, or other metaphorical/non-disaster uses.

## Data Model Changes

Keep the existing candidate export columns unchanged:

- `tweet_id`
- `image_id`
- `tweet_text`
- `image_url`
- `image_path`
- `text_label`
- `image_label`
- `disaster_label`

Add internal SQLite columns for model labeling metadata:

- `text_confidence`
- `image_confidence`
- `disaster_confidence`
- `label_explanation`
- `label_model`
- `labeled_at`

These fields should not appear in the `candidates` sheet for this feature.

## Commands

### `research-agent auto-label`

Labels existing candidates that still need labels.

Proposed options:

```bash
research-agent auto-label --limit 50 --min-confidence 0.65
```

Behavior:

- reads candidates with unknown labels first
- skips rows that already have all three labels unless `--relabel` is passed
- uses local downloaded image when available
- falls back to image URL when no local file exists
- updates labels, confidence fields, explanation, model, timestamp, and derived `case_label`
- leaves a row unchanged if model output cannot be parsed or fails validation

### `research-agent collect-balanced`

Runs collection, image download, auto-labeling, and export in rounds until target buckets are filled or the round limit is reached.

Proposed command:

```bash
research-agent collect-balanced --target-per-case 12 --max-rounds 5 --limit-per-query 100 --min-confidence 0.65
```

Behavior:

- runs configured X API queries
- downloads images
- auto-labels unlabeled candidates
- counts high-confidence candidates per case
- stops early if every case reaches `target-per-case`
- exports workbook at the end
- reports underfilled cases

Rows below the confidence threshold stay in the database but do not count toward the balanced target.

## Error Handling

- Missing `OPENAI_API_KEY`: `auto-label` and `collect-balanced` fail with a clear message.
- Missing image path and image URL: row is skipped with a labeling explanation.
- Invalid model JSON: row remains unchanged and the error is shown.
- OpenAI API error: command stops with a clear error and preserves prior labels.
- X API credit or rate errors: `collect-balanced` uses existing clear X API error handling.

## Testing Strategy

Network-dependent OpenAI calls should be tested through fake clients and fixture responses. Tests must cover:

- prompt payload includes tweet text and an image input
- local image files are converted to base64 data URLs
- valid JSON model output updates labels and confidence fields
- invalid labels are rejected
- `auto-label` labels only rows that need labels by default
- `collect-balanced` stops when target case counts are reached
- confidence threshold excludes low-confidence rows from target counts
- candidate Excel export still contains only the eight user-requested columns

## Acceptance Criteria

The feature is complete when:

- `.env` supports `OPENAI_API_KEY` and optional `OPENAI_MODEL`
- existing candidates can be auto-labeled with provisional labels
- model confidence and explanation are stored internally
- balance counts reflect auto-labeled candidates
- balanced collection can target an even distribution across the eight cases
- low-confidence rows are not counted as balanced target rows
- tests cover labeling, balanced stopping, and export column constraints
- README explains the provisional nature of model labels and the new commands
