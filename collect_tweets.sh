#!/usr/bin/env bash
set -euo pipefail

LIMIT="${1:-100}"
CONFIG_PATH="${CONFIG_PATH:-config/queries.yaml}"
EXPORT_PATH="${EXPORT_PATH:-exports/candidates.xlsx}"

cd "$(dirname "$0")"

echo "Initializing workspace..."
research-agent init

echo "Collecting tweet-image candidates with limit=$LIMIT..."
research-agent collect --config "$CONFIG_PATH" --limit "$LIMIT"

echo "Downloading images..."
research-agent download-images

echo "Current balance:"
research-agent balance

echo "Exporting workbook..."
research-agent export --output "$EXPORT_PATH"

echo "Collection phase complete. Workbook written to $EXPORT_PATH"
