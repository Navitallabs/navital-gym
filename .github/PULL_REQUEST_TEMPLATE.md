## What this changes

<!-- One or two sentences. Link the issue if there is one. -->

## Type

- [ ] Docs only
- [ ] Bug fix in code or scripts
- [ ] New or changed task, rule, world or prompt (this changes the grader id and needs a regrade)
- [ ] Run submission (`submissions/<model-slug>/`; see SUBMITTING.md)

## Checks

- [ ] `python -m unittest discover -s tests` passes
- [ ] For a run submission: `python3 scripts/verify_submission.py <file>` prints PASS for every file
- [ ] No API keys, private or held-out tasks, or personal paths in the diff
- [ ] If anything under `navital_gym/` changed: I say so below and explain why scores may change

## Notes for the reviewer
