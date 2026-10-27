# Submitting your model's results

Anyone can add a model to the leaderboard. You run the public tasks yourself; the public grader replays your saved run offline and either reproduces your scores or it does not. Nothing is trusted except your model's own words and tool calls.

## 1. Run
Use the current `main` (or the latest release tag) of this repo, on a clean checkout, and run the whole split for each environment you want listed. One run per cell (`--k 1`); all tools and the default settings, no custom prompts.

    pip install -e .
    export OPENAI_API_KEY=...                 # keys stay in the provider's environment variable (GROQ_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY, ...); an openai: spec with @base_url uses OPENAI_API_KEY
    M="openai:<model>@https://<endpoint>/v1"  # any OpenAI-style chat API with tool calling; or anthropic:<model>, gemini:<model>, groq:<model>
    mkdir -p submissions/<model-slug>
    navital-gym run --env gst   --agent "$M" --k 1 --out submissions/<model-slug>/gst-<model-slug>-full.json
    navital-gym run --env gst   --agent "$M" --k 1 --split easy --out submissions/<model-slug>/gst-<model-slug>-easy.json

- Environments: `trip`, `gst`, `form`, `form_multidoc`, `support`, `upi`. The easy split exists for `trip`, `gst`, `support`, `upi`.
- File names must be `<env>-<model-slug>-<full|easy>.json` (a stratified sample, `--sample N`, is named `...-sN.json` and is listed as a sample). `--out` also writes `<same name>.transcripts.json`: send both.
- `support`: the standard split is the 50 core tasks; adding `--env-kw include_experimental=true` runs the 26 labelled-experimental Tamil, Bengali and Marathi tasks as well. Both are accepted for `-full`.
- Tasks that end in a provider error (rate limit, outage) are saved as *not run*. Re-run with `--resume` until none are left; incomplete files are not listed.
- Trip tasks use 60-110k tokens each. Set `--token-cap` or `--spend-cap-usd` to limit your own spend.

## 2. Describe it: `submissions/<model-slug>/submission.json`
    {"model": "<exact model name>", "provider": "<who serves it>", "date": "2026-11-03", "submitter": "<name, org or GitHub handle>", "notes": "<optional: quantisation, endpoint, settings>"}
`model` must equal the model in the run file. `date` is the day you ran it.

## 3. Check it yourself
    python3 scripts/verify_submission.py submissions/<model-slug>/gst-<model-slug>-full.json
It prints `PASS`, or `FAIL` with every reason. It never calls a model.

## 4. Send it
Open a pull request that adds the folder `submissions/<model-slug>/` (run files, transcripts, `submission.json`), or open an issue and attach the files (zip them). We run the same verification before anything is listed.

## What the check does
- Reads the files; the run must hold exactly one model, and `submission.json` must name it.
- The task ids must be exactly the public ids of that split (or the deterministic stratified sample): no held-out, invented, missing or extra tasks.
- Each transcript must start with that task's public prompt.
- Every tool call is replayed on a fresh deterministic world: each recorded tool result must equal the replayed one. The final answer is then graded by the current public grader, and `solved`, score and rules must equal what the file claims, and so must the summary.
- If the file was graded at another grader version, that is reported; the replay at the current grader decides.
- Every task must be answered. Whether an answer was repaired or ran out of turns is read from the transcript, and the published numbers are recomputed by the replay: nothing in your summary or `meta` is taken on trust.

## What disqualifies a run
- Edited transcripts, tool results, answers or scores (the replay catches a change in a tool result, a final answer or a claimed verdict).
- Held-out or private tasks, or a task set that is not the public split.
- Changes to the grader, the worlds, the tools, the prompts or the task files (run the released code unmodified).
- Another model's output saved under a different name, or answers produced by someone looking at the answer keys (the task files contain them, because the graders need them; do not feed them to the model, tools or prompts).
- More than one run presented as one (pick the run and say so in `notes`; for pass^k use `--k 3` and keep all of it).

## How it is shown
Rows from submissions are labelled **community, self-reported** with the submitter and date. A passing check proves that the file is consistent and reproducible by the public grader. It cannot prove which model wrote the words, so those rows are never mixed into our own results tables or headline numbers. We may drop a row if we learn it was not what it says; a confirmed grader bug is fixed for everyone and all rows are re-graded by replay.
