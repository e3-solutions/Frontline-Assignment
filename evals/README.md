# Voice-agent evaluations

From the repository root, run `python3 -m unittest discover evals`, then
`./evals/run.sh`. The latter writes `evals/results/report.md`. Read Layer A
for offline handler results, its expected failure as a finding, and Layer B
skip reasons. Layer B needs `OPENAI_API_KEY` and normal runtime dependencies.
