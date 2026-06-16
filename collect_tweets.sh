#!/usr/bin/env bash
set -euo pipefail

LIMIT="${1:-25}"
CONFIG_PATH="${CONFIG_PATH:-config/queries.yaml}"
EXPORT_PATH="${EXPORT_PATH:-exports/candidates.xlsx}"
TARGET_PER_CASE="${TARGET_PER_CASE:-5}"
MAX_ROUNDS="${MAX_ROUNDS:-3}"
MIN_CONFIDENCE="${MIN_CONFIDENCE:-0.65}"

cd "$(dirname "$0")"

echo "Initializing workspace..."
research-agent init

echo "Filling balanced dataset with target_per_case=$TARGET_PER_CASE limit_per_query=$LIMIT..."
research-agent fill-balanced \
  --config "$CONFIG_PATH" \
  --target-per-case "$TARGET_PER_CASE" \
  --max-rounds "$MAX_ROUNDS" \
  --limit-per-query "$LIMIT" \
  --min-confidence "$MIN_CONFIDENCE" \
  --output "$EXPORT_PATH"

echo "Current balance:"
research-agent balance

echo "Collection phase complete. Workbook written to $EXPORT_PATH"
