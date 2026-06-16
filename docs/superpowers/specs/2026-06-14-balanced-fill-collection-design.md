# Balanced Fill Collection Design

## Goal

Add a collection workflow that builds a balanced active dataset with exactly 50 high-confidence candidates in each of the eight text/image/disaster buckets.

## Design

The new workflow will collect X candidates, download image media, auto-label them with the configured OpenAI model, then prune active database rows so no completed bucket exceeds the target. Bucket counts are based on the model-assigned labels and the existing minimum confidence threshold. Rows with unknown labels are left in place when a run is interrupted so `label_tweets.sh` can still resume them later.

The collector will support X API pagination during a single balanced fill run. This avoids repeatedly requesting the same first page for each query when several rounds are needed.

## CLI Behavior

Add a `research-agent fill-balanced` command with these defaults:

- `--target-per-case 50`
- `--max-rounds 20`
- `--limit-per-query 50`
- `--min-confidence 0.65`
- `--output exports/candidates.xlsx`

Update `collect_tweets.sh` to call `fill-balanced`, making that script the main collect-download-label-balance workflow. The script defaults to a smaller cost-controlled test run, while `TARGET_PER_CASE=50 MAX_ROUNDS=20 ./collect_tweets.sh 50` remains the full 400-row dataset run. Keep `label_tweets.sh` as a recovery script for interrupted or manually imported unlabeled rows.

## Completion

The command exits successfully only when all eight buckets reach the requested target. If API failures, OpenAI failures, or exhausted rounds prevent a full target, it still exports the current workbook but exits with a nonzero status so the researcher knows the dataset is incomplete.
