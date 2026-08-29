# Reviewer holdout v6 evidence — terminated incomplete

Protocol `reviewer-holdout-v6` never completed its preregistered matrix and
**cannot be completed on any current machine.** This directory preserves the
five reports that survived, the driver logs, and the reason the protocol died,
rather than deleting a partial run.

No v6 accuracy result is claimed. No skill-lift result is claimed.

## Why it cannot complete

v6 preregisters an exact CLI identity:

```
codex:  codex-cli 0.149.0
claude: Claude Code 2.1.239
```

`scripts/evals/run-reviewer-holdout.py` enforces that identity by equality and
refuses to run on any other build. Claude Code retains only a short window of
installed versions, and `2.1.239` has since been pruned; the retained builds are
`2.1.247`, `2.1.248`, `2.1.250`, `2.1.251`. The codex build is still retained,
but `arm_comparison.required_matrix` is
`exact-three-profiles-by-three-hosts`, and six of the nine cells need the Claude
host.

This is the same failure that ended v5, which preregistered `Claude Code 2.1.220`.
A protocol that pins an exact build from an auto-updating, auto-pruning
distribution channel becomes unrunnable within days. See the "Execution identity
drift" section of `../STATUS.md`.

## What survived

Nine cells were preregistered. Four were lost before they were copied out of a
temporary directory (`full-codex`, `catalog-only-codex`, `no-skill-codex`,
`full-opus`). Five reports remain, in `reports/`:

| Report | Arm | Model | Execution complete | Status | Unique P / R / F1 | Infra errors |
| --- | --- | --- | --- | --- | --- | --- |
| `no-skill-opus.json` | no-skill | claude-opus-5 | yes | FAIL | 0.441 / 0.625 / 0.517 | 0/60 |
| `catalog-only-opus.json` | catalog-only | claude-opus-5 | yes | FAIL | 0.885 / 0.958 / 0.920 | 0/60 |
| `no-skill-fable.json` | no-skill | claude-fable-5 | no | INCONCLUSIVE | 0.452 / 0.583 / 0.509 | 2/60 |
| `catalog-only-fable.json` | catalog-only | claude-fable-5 | no | INCONCLUSIVE | 0.913 / 0.875 / 0.894 | 6/60 |
| `full-fable.json` | full | claude-fable-5 | no | INCONCLUSIVE | 0.882 / 0.625 / 0.732 | 22/60 |

Metrics are the protocol's primary unit: unique majority-stable labels and
predictions, not repeated run totals.

## How to read these numbers

**`FAIL` on a control arm is the expected outcome, not a defect.** The
protocol applies one threshold set to every arm, including `no-skill`. A
baseline arm that receives no pattern contracts is supposed to miss those
thresholds. Read `status_reasons` in each report for the specific metric.

**The `full` arm has no usable measurement on any host.** `full-codex` was lost
and `full-opus` never ran. `full-fable` lost 22 of 60 scheduled runs, and a
label needs 2 of 3 repetitions to become majority-stable, so the missing runs
suppress stable labels and depress its unique recall (0.625). That figure is an
artifact of infrastructure loss and must not be read as the full arm performing
worse than `catalog-only`.

**Only one arm contrast is defensible here:** `no-skill-opus` against
`catalog-only-opus`. Both are execution-complete with zero infrastructure
errors, same host, same model, same corpus:

| | Unique precision | Unique recall |
| --- | --- | --- |
| no-skill | 0.441 | 0.625 |
| catalog-only | 0.885 | 0.958 |

That is a single-host, single-model contrast on an inspectable public
development corpus. It is directionally consistent with the degraded fable
pair, and it is not a generalization result.

## What this evidence does not support

Every report carries `release_eligible: false`, `evidence_scope: "development"`,
and `corpus_visibility: "public-development"`, with the corpus declaring:

> Frozen public development corpus for balanced cross-provider regression
> measurement. It is not sealed and does not establish generalization.

The reports also record `development_only_no_release_isolation_attestation`.
Nothing here is a release gate, a generalized reviewer accuracy figure, or a
sealed holdout result. A release-grade run needs an external sealed `--cases`
bundle and an independently isolated environment; the bundled harness records
wrapper isolation as not proven and keeps such a report `INCONCLUSIVE`.

## Files

- `reports/*.json` — the five surviving reports, with raw model output, parsed
  findings, per-case scores, and provenance. Not rewritten or rescored.
- `driver-{codex,opus,fable}.log` — per-host driver timing and exit codes.
- `codex.log`, `opus.log`, `fable.log`, `redo.log` — runner console output,
  including the summary lines for the four reports that were later lost.

Absolute paths in these artifacts use the `/Users/user` placeholder, not a
contributor identity.
