#!/bin/bash
set -e

echo "Running all checks..."
echo

./scripts/format.sh
echo

./scripts/lint.sh
echo

./scripts/mypy.sh
echo

echo "✅ All checks passed!"