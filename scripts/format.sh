#!/bin/bash
set -e

echo "Running ruff format..."
uv run ruff format bot/ tests/