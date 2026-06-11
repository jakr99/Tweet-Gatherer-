#!/usr/bin/env bash
set -euo pipefail

LIMIT="${1:-10}"
MIN_CONFIDENCE="${MIN_CONFIDENCE:-0.65}"
EXPORT_PATH="${EXPORT_PATH:-exports/candidates.xlsx}"

cd "$(dirname "$0")"

echo "Auto-labeling existing candidates with limit=$LIMIT..."
research-agent auto-label --limit "$LIMIT" --min-confidence "$MIN_CONFIDENCE"

echo "Current balance:"
research-agent balance

echo "Exporting workbook..."
research-agent export --output "$EXPORT_PATH"

echo "Labeling phase complete. Workbook written to $EXPORT_PATH"
