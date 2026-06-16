[OPEN]

# Session: subagent-empty-response

## Symptoms
- Sometimes only shows `[Sub-agent Explore completed]` and then no direct answer to the user prompt.
- Sometimes a follow-up says the previous output was swallowed / multiple empty responses.

## Hypotheses (Falsifiable)
- A: Parent turn ends after tool execution (sub-agent `task`) without a synthesis assistant message (step limit / controller stop / early return).
- B: Model returns empty assistant content after tool results; retry logic stops and leaves no meaningful answer.
- C: Tool result folding/persistence truncates the sub-agent output into a short stub, making it look like “no answer”.
- D: TUI transcript/update pipeline drops an assistant message (race / state overwrite / render suppression).
- E: `task` tool output/message role formatting causes the parent loop to not request/attach a follow-up assistant step.

## Evidence Plan
1) Start debug server (writes `.dbg/subagent-empty-response.env` and `trae-debug-log-subagent-empty-response.ndjson`).
2) Reproduce: run 3–5 prompts that tend to trigger `task` explore.
3) Collect logs: query `/logs?last=200` and inspect the sequence around tool result + assistant emission.

## Status
- Instrumentation: pending
- Repro: pending
