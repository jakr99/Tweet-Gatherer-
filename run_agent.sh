#!/usr/bin/env bash
set -euo pipefail

LIMIT="${1:-10}"
CONFIG_PATH="${CONFIG_PATH:-config/queries.yaml}"
EXPORT_PATH="${EXPORT_PATH:-exports/candidates.xlsx}"
TARGET_PER_CASE="${TARGET_PER_CASE:-12}"
MAX_ROUNDS="${MAX_ROUNDS:-5}"
MIN_CONFIDENCE="${MIN_CONFIDENCE:-0.65}"

cd "$(dirname "$0")"

echo "Initializing workspace..."
research-agent init

echo "Collecting, downloading, auto-labeling, and balancing candidates..."
research-agent collect-balanced \
  --config "$CONFIG_PATH" \
  --target-per-case "$TARGET_PER_CASE" \
  --max-rounds "$MAX_ROUNDS" \
  --limit-per-query "$LIMIT" \
  --min-confidence "$MIN_CONFIDENCE" \
  --output "$EXPORT_PATH"

echo "Current balance:"
research-agent balance

echo "Done. Workbook written to $EXPORT_PATH"
