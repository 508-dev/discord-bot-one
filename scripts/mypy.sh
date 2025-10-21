#!/bin/bash
set -e

echo "Running mypy..."
uv run mypy bot/ --ignore-missing-imports