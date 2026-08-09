#!/usr/bin/env bash
set -euo pipefail

# Development-only skills. They guide coding agents; Furina does not call Mem0 at runtime.
npx skills add https://github.com/mem0ai/mem0 --skill mem0
npx skills add https://github.com/mem0ai/mem0 --skill mem0-integrate
npx skills add https://github.com/mem0ai/mem0 --skill mem0-test-integration

echo "Mem0 engineering skills installed. Furina's runtime memory remains local-first."
