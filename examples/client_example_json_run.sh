#!/bin/bash
cd "$(dirname "$0")/.."
npx tsc && npx tsx examples/client_example_json.ts "$@"
