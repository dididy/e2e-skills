# Field scan v1 — deterministic scanner on public repositories

**This selection rule is frozen before the scan runs.** Committing the rule
first is the point: it is what distinguishes a sample from a set of results
picked after seeing them.

## What this is

The bundled scanner (`skills/e2e-reviewer/scripts/scan.sh`) is run over public
repositories at pinned commits, and **every** hit is published — file, line,
and pattern id — with no filtering for whether the hit looks good.

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

- [`ledger.md`](ledger.md) — the readable ledger: per-repository counts and a
  permalink to every P0 hit at the pinned commit.
- [`ledger.json`](ledger.json) — the same run as data, including the scanner's
  own Summary counts next to the parsed hits so a discrepancy is visible rather
  than silently absorbed.

Two labels in that ledger carry the honesty of the whole exercise:

- **Triage candidates are not defects.** Hits the scanner tags `[LLM-TRIAGE]`
  need a judgement the deterministic tier cannot make, so they are counted in
  their own column and never folded into a defect total.
- **An incomplete scan is a floor, not a reading.** When a rule exceeds the
  bounded per-rule limit it suppresses itself and reports nothing, so those
  rows are rendered with `≥`. A zero in an incomplete row does not mean the
  repository is clean; it means the check did not finish. The bound was left at
  its shipped default rather than raised after seeing the results.

## Result: a null result, and a runtime wall

Of the twelve pinned repositories, **eleven completed and one did not finish**
within the 30-minute per-repository budget. Across the eleven that completed,
the deterministic P0 tier reported **zero hits**, alongside ~1,942
`[LLM-TRIAGE]` candidates: shapes it cannot decide alone.

**That zero is bounded by what completed, and the repository that did not is
where it breaks.** An independent review scanned `ever-co/ever-gauzy`'s
`apps/gauzy-e2e` subtree directly — the same subtree the timing figure below
comes from — and the tier reports **294 `#3` hits there in the confirmed
bucket**, all in `tests/support/pages/*.po.ts`, none in the specs. An earlier
version of this file reported the zero as a corpus-wide result and treated the
unfinished repository as merely absent. It is not merely absent: it is the one
case that changes the answer.

The 294 are bounded rather than a floor. The scanner's own empty-catch pattern
hits 314 times across the whole repository; 311 are in that subtree and the
three outside carry no E2E markers, so the scope filter drops them. A completed
run would report the same 294 for this rule and nothing more.

A further 19% of them (55 hits) sit inside an enclosing `try`/`catch` block that
the scanner documents itself as unable to judge: `SKILL.md` states that
try/catch wrapping needs Phase 2 because grep cannot decide it. For those, the
tier is confirming a `.catch(` whose surrounding construct it has declared out
of its reach.

What they are worth is a narrower claim than the count suggests. A ten-hit
sample read against the consequence-based `#3` exemption — swallowed failure is
exempt only when it cannot change what the test proves — splits roughly one
third in scope and two thirds exempt, and **in every case the deciding evidence
was several lines after the hit**, outside the window the deterministic tier
reads. Two of the ten are clear true positives: a swallowed gate that lets a
later step pass on a state the test never established. So the honest reading is
that the tier flags 294 candidates it is not equipped to adjudicate, and that
adjudication is Phase 2's.

Both halves matter, and neither is flattering:

- **Zero P0 on popular public code.** The frozen rule above predicted a low hit
  rate from popularity sampling. It was not merely low. On this sample the
  deterministic tier decided nothing on its own, which is consistent with where
  the project's accepted upstream fixes actually came from -- see
  [Field review v1](../field-review-v1/README.md), where a model is in the loop.
  The first run of this scan reached the same result on eight repositories, and
  three more have completed since as the scanner got faster without moving it.
  But the zero describes the repositories that finish, and the one that does not
  carries 294 confirmed-bucket hits, so it is a statement about a sample rather
  than about public code.
- **One repository still does not finish**, and the reason is not the one an
  earlier version of this file gave. `ever-co/ever-gauzy` carries 9,232 scanned
  code files and has no pathological line. The cost that scales with file count is a
  per-file integrity fingerprint: the candidate manifest is built and
  revalidated six times per scan. It used to spawn one `python3` process per
  candidate file per pass -- about **0.18 s per code file measured on one
  host**, or roughly 28 minutes for 9,232 files before a single finding was
  evaluated. That is now one process per pass, which is what brought
  `open-mercato` (9,670 files) inside the budget; `ever-gauzy` is still outside
  it.

  Dividing a subtree's wall clock by its file count, as this file previously did,
  gives a number that does not extrapolate. Hit work does not grow with
  repository size, because each rule evaluates at most 1,000 candidates and is
  suppressed above that — on `ever-gauzy` thirteen rules exceed the cap, leaving
  roughly as many surviving evaluations as its own 350-file subtree.

  That has a consequence worth stating plainly, and `open-mercato` has now
  demonstrated it: **finishing is not the same as measuring.** Its completed
  scan reports `Summary [INCOMPLETE]` with **25 rules suppressed** and exit 2 --
  1,498 listed hits, none of them P0, from the rules that survived the cap. The
  same is expected of `ever-gauzy` if it is ever made to finish. The operative limit
  is the per-rule candidate cap rather than a time budget, and narrowing the scan
  root is the remedy for the cap — not a way to buy time.

### What the first run could not explain, and what it was

The first run timed out on four repositories and this file recorded the
mechanism as unidentified. It has since been found, and two of the four now
complete.

The scan runs with `--hidden --no-ignore` and treats `.cjs` as source, while the
exclusion list -- which already drops `node_modules`, `dist`, `build`, `out` and
`coverage` -- had no entry for vendored package-manager bundles, which are not
named `*.min.*`. On `LekoArts/gatsby-themes` that admitted
`.yarn/releases/yarn-4.8.1.cjs`, whose longest line is 337,344 characters. The
lexer then built its output one character at a time, which is quadratic in line
length: a single pass over that file took 12 seconds, and one check with two
candidates spent 676 seconds.

Both faults are fixed -- the vendored paths are excluded, the lexer no longer
builds output it discards, and an oversized-line guard now matches the limit the
scanner's embedded Python path already enforced. Re-running the frozen sample
produced **identical findings on every repository that had completed before**,
which is what distinguishes this from a change in behaviour.

The numbers were not re-run with a raised bound or a longer budget after seeing
them. Incomplete rows render with a floor marker so a zero in them cannot read
as a clean repository.

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
