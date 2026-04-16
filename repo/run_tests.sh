#!/usr/bin/env bash
set -euo pipefail

# Run tests inside Docker — no local Python or dependencies required.
# Uses the same Python base image as the production Dockerfile.

echo "=========================================="
echo " Building test image..."
echo "=========================================="
docker build -f Dockerfile.test -t fieldservice-tests .

echo ""
echo "=========================================="
echo " Running all tests in Docker..."
echo "=========================================="
docker run --rm fieldservice-tests

echo ""
echo "=========================================="
echo " All tests passed!"
echo "=========================================="
