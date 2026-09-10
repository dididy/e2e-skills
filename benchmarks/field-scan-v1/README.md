# Field scan v1 — deterministic scanner on public repositories

**This selection rule is frozen before the scan runs.** Committing the rule
first is the point: it is what distinguishes a sample from a set of results
picked after seeing them.

## What this is

The bundled scanner (`skills/e2e-reviewer/scripts/scan.sh`) is run over public
repositories at pinned commits. For scans recorded in the ledger, every listed
hit is published — file, line, and pattern id — with no filtering for whether
the hit looks good. Timeout rows have no completed measurement.

No model is involved. Anyone can check out the same commit, run the same
command, and get the same output. That is the entire credibility mechanism: the
claim is falsifiable line by line, which the project's other evidence is not.

## Selection rule (frozen)

1. Candidates come from GitHub code search for `"@playwright/test"` and
   `"cypress"` in `package.json`.
2. Sort candidates by star count, descending. Ties break on repository name,
   ascending.
3. **Exclude** any repository this project has ever opened a pull request
   against. Those are contaminated: the smells were found and in several cases
   already fixed by this author.
4. **Exclude** forks, archived repositories, and repositories with no file
   matching the scanner's spec globs.
5. Take the first 12 surviving repositories.
6. Pin each at the default branch's HEAD commit at freeze time, recorded as a
   full 40-character SHA in `repos.json`.

Steps 1 and 2 are ordinary popularity sampling. Step 3 is the one that matters
for honesty and is the reason the author's own 14 merged fixes cannot inflate
this result.

## What the output supports

- **Supported:** "the scanner reports these candidates in this real code, and
  you can verify each one yourself."
- **Not supported: recall.** Nothing here establishes what the scanner missed.
  There is no labelled ground truth, and constructing one would return the
  independence problem this design exists to avoid.
- **Not supported without further work: precision.** A hit is a candidate, not
  a verdict — that is the scanner's documented contract. Turning this into a
  precision figure requires someone to adjudicate a sample, and if that someone
  is this author the figure inherits the same weakness as everything else here.

## Known biases, stated before the numbers

- Popularity sampling favours well-maintained repositories, so the hit rate
  here is probably **lower** than a random sample of Playwright/Cypress code.
- Pattern coverage is uneven: the deterministic tier can only see grep- and
  AST-detectable shapes. Semantic-only patterns (`#2`, `#12`, `#22`, `#23`) do
  not appear here at all, and their absence is a property of the method, not
  evidence that the code is clean.
- A hit on a repository is not a defect report about that repository. The
  scanner marks candidates for review; several documented shapes are legitimate
  in context, which is why the P0 exit gate is separate from triage output.

## Results

- [`ledger.md`](ledger.md) — per-repository completion, counts, and P0 locations.
- [`ledger.json`](ledger.json) — the generated data, including scanner Summary
  counts, listed candidates, and incomplete-rule diagnostics.

The latest rerun used all **12 pinned repository roots**, the original
**30-minute scan budget per repository**, and the shipped default candidate
limits. The scanner source was frozen for the run and remained byte-identical.
No model was called. The selection rule above is unchanged.

**Incomplete: 10/12 repositories completed with no suppressed rules.**
Timeouts: `ever-co/ever-gauzy`, `open-mercato/open-mercato`. Other incomplete rows: **0**.

Across the 10 complete scans, scanner Summary counts report **1062 total
hits: 0 P0, 278 P1/P2 heuristic, and 784 LLM-triage**.
**231** of those hits are AST-origin; that is a subset of the total, not an
additional count. The ledger displays listed candidates and AST-origin counts
in separate columns. Triage candidates need review and are not defect counts.

| Repository | Scan time | Outcome |
|---|---:|---|
| `remix-run/react-router` | 1236.435 s | complete; no suppressed rules |
| `sweetalert2/sweetalert2` | 1068.804 s | complete; no suppressed rules |
| `ixartz/SaaS-Boilerplate` | 9.293 s | complete; no suppressed rules |
| `ever-co/ever-gauzy` | 1800.192 s | timeout; no final Summary |
| `francoischalifour/medium-zoom` | 11.122 s | complete; no suppressed rules |
| `i5ting/imove` | 25.975 s | complete; no suppressed rules |
| `livestorejs/livestore` | 346.637 s | complete; no suppressed rules |
| `kentcdodds/bookshelf` | 24.291 s | complete; no suppressed rules |
| `gautamkrishnar/nothing-private` | 7.048 s | complete; no suppressed rules |
| `LekoArts/gatsby-themes` | 25.536 s | complete; no suppressed rules |
| `open-mercato/open-mercato` | 1800.159 s | timeout; no final Summary |
| `jhipster/jhipster-sample-app` | 103.832 s | complete; no suppressed rules |

A normal process exit alone does not establish complete coverage. A complete
row requires exit 0 or 1, a complete Summary, no suppressed rules, and reconciled
counts. Partial rows and aggregate totals containing unavailable results are
floors. A zero in an incomplete row does not establish that the repository is
clean. Timeout rows have no final Summary and contribute no complete count.

The prior ledger recorded 11 terminal scans, but only 6
met these completion conditions. Its earlier "eleven completed" description
included scans with suppressed rules. A finished process with partial coverage
must not be reported as a complete scan.

### Candidate preservation and recovered coverage

The fresh ledger is compared with the prior published ledger by file, line,
pattern ID, severity, triage tag, and title. Across 10 rows with
comparable Summary output, no prior listed finding was removed or reclassified.
Added findings from previously suppressed rules: `#16`: 6, `#5a`: 23. Rows without
comparable Summary output are not included in that comparison. Recovered
findings are candidates, not an accuracy score.

Scope checks now precede raw candidate limits. Conservative discovery guards
exclude shapes that the unchanged downstream classifiers cannot emit. The
focused-test rule no longer treats every array expression as a candidate.
The default bounds still apply, and any genuinely over-cap rule remains
explicitly incomplete.

### Historical correction to pattern `#3`

An earlier version reported 294 confirmed `#3` hits from a direct scan of
`ever-co/ever-gauzy`'s `apps/gauzy-e2e` subtree. That was an error in the scanner's
classification, not 294 established defects in that repository. The scanner
had promoted assertion-looking text without proving attachment, rejectable
failure, or the absence of soft-assertion behavior.

Every `#3` hit now reports as `[LLM-TRIAGE]`, including a `.catch()` attached
to a rejectable asynchronous assertion oracle (a web-first matcher, `toPass()`,
or a matcher under `expect.poll`, excluding `expect.soft(...)`) — that
attachment and rejectability check narrows which hits are LLM-TRIAGE
candidates worth Phase-2 review, but it does not promote any `#3` hit to
confirmed P0. The default `E2E_SMELL_FAIL_ON=p0` gate exits 0 on `#3` alone;
`E2E_SMELL_FAIL_ON=p0-candidate` is the opt-in way to gate on these triage
candidates. Swallowed actions and context-dependent consequences remain
`[LLM-TRIAGE]` rather than disappearing. The earlier isolated classification
differential retained all 1,922 hits while moving those 294 from confirmed to
triage; P1/P2 and AST counts were unchanged. Those historical differential
counts are not the latest full-root result.

### Runtime work and remaining limits

The earlier full-root `ever-gauzy` measurement took 3,679 seconds against the
same 1,800-second budget. The latest runtime is listed above. The runtime target
remains unmet wherever the table records a timeout.

The current implementation retains one private scope worker and its metadata,
avoiding repeated JSON state loading and rewriting. Small eligible ASCII
sources use a paired Python lexer, with the original shell helper retained for
unsupported inputs and explicit tool overrides. Ordinary pathname operations
avoid additional processes. Downstream scope filters reuse the same exact
predicate/file cache already populated during preselection.

A two-file warm-filter control produced byte-identical output in three paired
runs: 1.075–1.158 seconds before cache reuse and 0.229–0.371 seconds after it.
A captured-cache component fixture, remapped to the pinned checkout, measured
0.227 seconds for reading state, 0.702 seconds for writing it, 1.000 seconds for
validating 192,043 witnesses, and 0.008 seconds for one cached traversal. That
fixture is synthetic profiling evidence, not scan-completion evidence.
Full-run time attribution remains incomplete; these component timings do not
establish the share of any one operation in the whole scan.

Dependency validation still runs before and after each scope-worker query and
before the final Summary. Reusing missing-parent observations within a
validation pass was rejected because concurrent path creation could evade an
observation that the original implementation performs. Candidate integrity,
symlink protections, bounded rules, and fail-closed exits remain in force.

Earlier fixes also excluded vendored package-manager bundles and avoided
quadratic lexer output construction on long lines. Those historical fixes did
not remove the frozen time limit. This rerun makes no claim about recall,
precision, reviewer lift, or generator quality.

## Reproducing

```bash
python3 scripts/evals/run-field-scan.py --repos benchmarks/field-scan-v1/repos.json \
  --output benchmarks/field-scan-v1/ledger.json
python3 scripts/evals/render-field-scan-ledger.py \
  --ledger benchmarks/field-scan-v1/ledger.json \
  --output benchmarks/field-scan-v1/ledger.md
```

The script shallow-clones each pinned commit into a temporary directory, runs
the scanner, and writes the ledger. It makes no model calls, opens no pull
requests, and writes nothing outside its output path. The renderer reads only
the ledger; it runs no scan of its own.
