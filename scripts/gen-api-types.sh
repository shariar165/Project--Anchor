#!/bin/bash
# Generate TypeScript types from the Core API's OpenAPI spec.
# Run this after any backend schema change and commit the result.
# Phase 5 of the monorepo upgrade plan.
#
# Prerequisites:
#   - Core API running at http://localhost:8000
#   - npx available (Node.js installed)

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$REPO_ROOT/packages/api-types/src"
SPEC_FILE="$REPO_ROOT/packages/api-types/openapi.json"

echo "Fetching OpenAPI spec from http://localhost:8000/openapi.json ..."
mkdir -p "$OUT_DIR"
curl -sf http://localhost:8000/openapi.json -o "$SPEC_FILE"

echo "Generating TypeScript types..."
npx openapi-typescript "$SPEC_FILE" -o "$OUT_DIR/index.ts"

echo "Done. Commit packages/api-types/src/index.ts to keep types in sync."
echo "CI will fail if the generated file differs from the committed version."
