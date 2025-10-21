#!/bin/bash
set -e

echo "Running ruff check..."
uv run ruff check bot/ tests/