# Security policy

## Reporting a vulnerability

Please report security problems privately by email to **dakshbathla@navitallabs.com**. Do not open a public issue or pull request for them.

Include what you found, how to reproduce it, and which version (release tag or `git rev-parse HEAD`) you tested. We will reply to confirm we received it and tell you what we plan to do.

## What is in scope

- The code in this repository: the runner, the graders, the worlds and tools, and the scripts (for example `scripts/verify_submission.py`, which reads files that other people send).
- Ways for a submitted run file to make the verifier or a grader execute code, read files outside the run, or reach the network.
- Ways for an agent running in an environment to read hidden task fields (expected answers, feasibility) or change its own score. These are also welcome as normal issues if you prefer; use the "Score looks wrong" template.

## What is not a security problem

- The task files contain the expected answers, because the graders need them. That is by design; see SUBMITTING.md for what disqualifies a run.
- All data is synthetic. No real personal, payment or tax data is stored here.

## API keys

The code reads provider keys from environment variables only and never writes them to run files. If you find a place where a key could end up in a saved file or a log, please report it.
