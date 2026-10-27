# Contributing and feedback

Navital Gym is a set of deterministic, auto-graded environments for AI agents doing tasks set in India (trip planning, GST, forms, support in Hindi/Hinglish, UPI). No LLM judge: every task is graded by rules that recompute the answer from a synthetic sandbox world. The rules are simplified and documented in each environment's README; they are tests for agents, not statements about current law or railway/bank practice.

## Run it (Python 3.10+, standard library only)
    pip install -e .
    navital-gym list                              # the environments and task counts
    navital-gym run --env trip --agent oracle     # scripted reference agent, should print 1.00
    python -m unittest discover -s tests          # optional, no extra dependencies

Run your own model: any OpenAI-style chat API with tool calling (hosted, vLLM, Ollama, LM Studio). The key is read from the provider's environment variable (`OPENAI_API_KEY` for `openai:` specs, including a custom `@base_url`; `GROQ_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`), never from the command line.

    export OPENAI_API_KEY=...
    navital-gym run --env gst --agent "openai:<model>@https://<your-endpoint>/v1" --k 1 --out runs/gst.json
    navital-gym run --env support --split easy --agent ...     # the easy split (trip, gst, support, upi)
    navital-gym run --env trip --sample 15 --agent ...         # a small stratified sample first

Trip tasks can use 60-110k tokens each: start small, and set `--token-cap N` or `--spend-cap-usd X` to limit your own spend. A task that ends in a provider error is reported as not run, not as a wrong answer. To plug in your own agent loop instead, see `docs/CORE-API.md`; adapters for Inspect AI, verifiers and OpenEnv are described in the README.

## Get your model on the leaderboard
See `SUBMITTING.md`: you run the public tasks, `scripts/verify_submission.py` replays your files offline, and a verified submission is listed as "community, self-reported". The saved run files behind every listed row of our own results are under `runs/`, so you can replay them too.

## Feedback we want most
- A task that looks wrong or ambiguous, or a grader verdict you disagree with: open an issue with the task id and your run file or transcript.
- A rule that does not match how the real product works.
- Anything confusing about install or the command line.

Open an issue in this repository, or email dakshbathla@navitallabs.com with the task id (for example `IN-GST-017`) and what you expected. A confirmed grader bug is fixed in a new version, noted in `CHANGELOG.md`, and every listed row is re-graded by replay.

## Limits
Synthetic data and simplified rules; small samples (read small-n cells as indicative); the task files include the expected answers, because the graders need them. The Tamil, Bengali and Marathi support tasks are labelled experimental. Licences: code Apache-2.0, task data CC BY 4.0.
