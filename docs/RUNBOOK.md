# Runbook

## Release

1. `make check` passes on `main`.
2. `make evals` passes the threshold. Commit the result file it wrote if it is the release
   evidence.
3. `make report`, then tag: `git tag -a vX.Y.Z -m "..."`.

## Rollback (revert and retag)

Never rewrite history on `main` and never move an existing tag.

1. Find the bad commit: `git log --oneline vPREVIOUS..vBAD`.
2. Revert it: `git revert <sha>` (one revert commit per bad commit).
3. `make check` and `make evals` on the revert. The revert must pass the same gates as any change.
4. Tag a new patch version on the revert commit: `git tag -a vX.Y.(Z+1) -m "rollback of <sha>"`.
5. Deploy the new tag. The bad tag stays in history as a record.

## Every incident becomes an eval case

An incident is anything a resident or funcionario saw that the spec says should not happen:
an invented horario, PII in a ticket or trace, a missed escalation, a wrong ticket status.

1. Reproduce it as a new line in `evals/dataset.jsonl` (set `ALLOW_TEST_EDITS=1`, this is the
   one legitimate reason to edit that file). Use synthetic data, never the resident's real data.
2. Run `make evals` and confirm the new case fails. A case that does not fail has not
   captured the incident.
3. If the cause is deterministic (a redaction pattern, a tool bug), add a unit test too.
4. Fix the code or the prompt. Do not touch the new case.
5. `make evals` passes, commit the result, release as above.

## Known issues

- O01 (passport, out of scope) fails the groundedness judge in v1: the agent names the
  institution that issues passports, which no tool returned.
- In the v0 run the judge returned no JSON for O01. The runner fails closed, so that case
  counts as failed in v0 for a measurement reason, not a behavior reason.
- The Claude hooks guard the Edit and Write tools. A shell command can still write to `tests/`.
  CI and review (REVIEW.md, pass 3) are the backstop.
- The CI workflows have not run yet: this repo has no remote.
