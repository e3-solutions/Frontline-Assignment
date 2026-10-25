#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS="$ROOT/evals/results"
REPORT="$RESULTS/report.md"
mkdir -p "$RESULTS"

{
  echo "# Voice-agent evaluation report"
  echo
  echo "> **FINDING — EXPECTED FAILURE:** An above-ceiling accepted agreement can call the external quote notifier when the LLM sends \`above_max=false\`. See \`evals/DESIGN.md\`; no product fix was applied."
  echo
  echo "## unittest run"
  python3 -m unittest discover "$ROOT/evals" -v
  echo
  echo "Expected failure: above-ceiling quote submission is a FINDING; see DESIGN.md."
  echo "Layer B skips unless OPENAI_API_KEY and runtime dependencies are available."
} >"$REPORT" 2>&1
cat "$REPORT"
