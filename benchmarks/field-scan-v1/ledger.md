# Field scan v1 — ledger

Every hit the deterministic scanner produced on the pinned public repositories, with nothing removed for how it looks. No model was called (`model_calls: 0`), no pull request was opened, and no upstream repository was modified. Each line below links to the exact line at the pinned commit, so any row can be checked without trusting this page.

## How to read the counts

- **P0** — the deterministic checks for silent always-pass shapes. These are the load-bearing hits.
- **Triage candidates** — hits the scanner tags `[LLM-TRIAGE]`. The scanner cannot decide these on its own, so they are **candidates for review, not defects**, and are never added to a defect total.
- **AST-origin** — Tier 2 hits counted in the scanner's own Summary but printed in a different shape, so they are reconciled here rather than re-listed.
- **Incomplete** — a rule hit the bounded per-rule limit and was suppressed. That repository's counts are a floor, not a measurement.

## Selection

The selection rule was frozen and committed before this scan ran: [`benchmarks/field-scan-v1/README.md`](../../benchmarks/field-scan-v1/README.md).

Repositories excluded as contaminated (already used in development): **32**. Scanned: **11/12**.

## Per repository

| Repository | Commit | P0 | Triage candidates | Other | AST-origin | Complete |
|---|---|---:|---:|---:|---:|:--:|
| [remix-run/react-router](https://github.com/remix-run/react-router) | [`7aea711dd1`](https://github.com/remix-run/react-router/tree/7aea711dd1ae2bc5a076d13ff17291829690fa74) | ≥0 | ≥229 | ≥221 | ≥231 | **no** |
| [sweetalert2/sweetalert2](https://github.com/sweetalert2/sweetalert2) | [`566377edff`](https://github.com/sweetalert2/sweetalert2/tree/566377edff0ac0d8418972855fc34fa8542e80d2) | ≥0 | ≥29 | ≥0 | ≥0 | **no** |
| [ixartz/SaaS-Boilerplate](https://github.com/ixartz/SaaS-Boilerplate) | [`e3952a7ed5`](https://github.com/ixartz/SaaS-Boilerplate/tree/e3952a7ed5b0ef172ac4363c4644b8c334d1094b) | 0 | 1 | 0 | 0 | yes |
| [ever-co/ever-gauzy](https://github.com/ever-co/ever-gauzy) | `54b537baf8` | — | — | — | — | timeout |
| [francoischalifour/medium-zoom](https://github.com/francoischalifour/medium-zoom) | [`21332eb3c5`](https://github.com/francoischalifour/medium-zoom/tree/21332eb3c5abc181b48251a06ee19fd7792fab22) | 0 | 4 | 1 | 0 | yes |
| [i5ting/imove](https://github.com/i5ting/imove) | [`0529e81271`](https://github.com/i5ting/imove/tree/0529e8127132380196ae14ea5f505b332dfcf8a6) | 0 | 31 | 46 | 0 | yes |
| [livestorejs/livestore](https://github.com/livestorejs/livestore) | [`583bf8420b`](https://github.com/livestorejs/livestore/tree/583bf8420b43eb32b2335c22e440d14ad73c1b9c) | ≥0 | ≥90 | ≥6 | ≥0 | **no** |
| [kentcdodds/bookshelf](https://github.com/kentcdodds/bookshelf) | [`32e9e87db9`](https://github.com/kentcdodds/bookshelf/tree/32e9e87db958de863bead65761bfbe2dec0eafd4) | 0 | 45 | 1 | 0 | yes |
| [gautamkrishnar/nothing-private](https://github.com/gautamkrishnar/nothing-private) | [`7050e014a8`](https://github.com/gautamkrishnar/nothing-private/tree/7050e014a8e65041fd38bb42bc72f667b72ec0e7) | 0 | 2 | 0 | 0 | yes |
| [LekoArts/gatsby-themes](https://github.com/LekoArts/gatsby-themes) | [`0ee600732b`](https://github.com/LekoArts/gatsby-themes/tree/0ee600732beb88a49135760df9ed6f4d419fde2e) | 0 | 26 | 0 | 0 | yes |
| [open-mercato/open-mercato](https://github.com/open-mercato/open-mercato) | [`8b492325d3`](https://github.com/open-mercato/open-mercato/tree/8b492325d3db29c431cca43674dcc93f894110be) | ≥0 | ≥1415 | ≥83 | ≥3 | **no** |
| [jhipster/jhipster-sample-app](https://github.com/jhipster/jhipster-sample-app) | [`e06e87abe0`](https://github.com/jhipster/jhipster-sample-app/tree/e06e87abe0be8a3a194381ce651164a734811b3f) | ≥0 | ≥70 | ≥0 | ≥0 | **no** |
| **Total** | | **≥0** | **≥1942** | **≥358** | **≥234** | |

≥ marks a floor, not a count: 5 of 11 scanned repositories had at least one rule suppressed at the bounded per-rule limit, and a suppressed rule reports nothing. **A zero in one of those rows does not mean the repository is clean** — it means the check did not finish. The bound was left at its shipped default rather than raised after seeing these results.

### Incomplete scans

A rule that exceeds the bounded per-rule limit suppresses itself and reports nothing; the rest of the scan still runs. The counts for these repositories are therefore a lower bound.

- **remix-run/react-router** — 15 rule(s) suppressed:
  - these rules hit a bounded limit and reported nothing: #7 #4f #4f #4f #4f #4f #4f #5a #10d #15 #15 #16 #16 #16
  - Tier 3 #7 Focused test committed exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise the bounded limit
  - Tier 3 #4f Locator always-true assertion (truthy/defined/not-null) exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the sc
  - Tier 3 #4f Possible wrapped Locator truthiness assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or
  - Tier 3 #4f Possible Locator truthiness in unresolved test-fixture source exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow 
  - Tier 3 #4f Possible generic getBy/query truthiness assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan roo
  - Tier 3 #4f Possible Locator/POM identifier truthiness assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan 
  - Tier 3 #4f Possible Locator/POM member truthiness assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root
  - Tier 3 #5a Conditional branch contains assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise t
  - Tier 3 #10d Cypress async callback mixes promises with queued commands exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow th
  - Tier 3 #15 Missing await on Playwright expect exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise the 
  - Tier 3 #15 Missing await on Playwright retry assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or r
  - Tier 3 #16 Possible deferred/discarded Playwright action promise exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan
  - Tier 3 #16 Missing await on Playwright action exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise the 
  - Tier 3 #16 Possible missing await on Locator/POM action exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or 
- **sweetalert2/sweetalert2** — 3 rule(s) suppressed:
  - these rules hit a bounded limit and reported nothing: #15 #15
  - Tier 3 #15 Missing await on Playwright expect exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise the 
  - Tier 3 #15 Missing await on Playwright retry assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or r
- **livestorejs/livestore** — 11 rule(s) suppressed:
  - these rules hit a bounded limit and reported nothing: #7 #4f #4f #4f #4f #4f #4f #5a #15 #15
  - Tier 3 #7 Focused test committed exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise the bounded limit
  - Tier 3 #4f Locator always-true assertion (truthy/defined/not-null) exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the sc
  - Tier 3 #4f Possible wrapped Locator truthiness assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or
  - Tier 3 #4f Possible Locator truthiness in unresolved test-fixture source exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow 
  - Tier 3 #4f Possible generic getBy/query truthiness assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan roo
  - Tier 3 #4f Possible Locator/POM identifier truthiness assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan 
  - Tier 3 #4f Possible Locator/POM member truthiness assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root
  - Tier 3 #5a Conditional branch contains assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise t
  - Tier 3 #15 Missing await on Playwright expect exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise the 
  - Tier 3 #15 Missing await on Playwright retry assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or r
- **open-mercato/open-mercato** — 25 rule(s) suppressed:
  - these rules hit a bounded limit and reported nothing: #3 #3 #3 #3 #3 #3 #3 #7 #4f #4f #4f #4f #4f #4f #5a #10a #10d #10f #14 #15 #15 #16 #16 #16
  - Tier 3 #3 Error swallowing via empty catch (E2E scope) exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or r
  - Tier 3 #3 Possible best-effort setup, teardown, or cleanup empty catch exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow th
  - Tier 3 #3 Possible empty catch with unresolved test-outcome impact exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the sc
  - Tier 3 #3 Possible error swallowing in unresolved test-fixture source exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the
  - Tier 3 #3 Possible error swallowing via catch fallback exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or r
  - Tier 3 #3 Possible parameterized catch swallowing exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise 
  - Tier 3 #3 Possible assertion failure masked by finally return exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan ro
  - Tier 3 #7 Focused test committed exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise the bounded limit
  - Tier 3 #4f Locator always-true assertion (truthy/defined/not-null) exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the sc
  - Tier 3 #4f Possible wrapped Locator truthiness assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or
  - Tier 3 #4f Possible Locator truthiness in unresolved test-fixture source exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow 
  - Tier 3 #4f Possible generic getBy/query truthiness assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan roo
  - Tier 3 #4f Possible Locator/POM identifier truthiness assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan 
  - Tier 3 #4f Possible Locator/POM member truthiness assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root
  - Tier 3 #5a Conditional branch contains assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise t
  - Tier 3 #10a Positional selector exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise the bounded limit.
  - Tier 3 #10d Cypress async callback mixes promises with queued commands exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow th
  - Tier 3 #10f Cypress action followed by an unsafe continued chain exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan
  - Tier 3 #14 Hardcoded credential candidate exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise the boun
  - Tier 3 #15 Missing await on Playwright expect exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise the 
  - Tier 3 #15 Missing await on Playwright retry assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or r
  - Tier 3 #16 Possible deferred/discarded Playwright action promise exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan
  - Tier 3 #16 Missing await on Playwright action exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise the 
  - Tier 3 #16 Possible missing await on Locator/POM action exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or 
- **jhipster/jhipster-sample-app** — 3 rule(s) suppressed:
  - these rules hit a bounded limit and reported nothing: #15 #15
  - Tier 3 #15 Missing await on Playwright expect exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or raise the 
  - Tier 3 #15 Missing await on Playwright retry assertion exceeded E2E_SMELL_MAX_RULE_HITS=1000 while streaming raw candidates; this rule is suppressed and reported no findings. Narrow the scan root or r

## P0 hits

Deterministic P0 findings only. Triage candidates are listed separately below and are not defects.

_None listed._ This is not a finding of cleanliness: P0 rules were among those suppressed in the incomplete scans above.

## Triage candidates

**These are not defects.** The scanner flags them as needing a judgement it cannot make deterministically. They are published so the P0 column above cannot be inflated by quietly counting them.

| Pattern | Candidates |
|---|---:|
| `#10c` | 880 |
| `#4i` | 242 |
| `#11c` | 224 |
| `#5a` | 147 |
| `#4c-4e` | 79 |
| `#14` | 72 |
| `#10f` | 69 |
| `#4b` | 65 |
| `#10a` | 49 |
| `#4a` | 30 |
| `#6` | 23 |
| `#16` | 19 |
| `#8a` | 10 |
| `#18` | 9 |
| `#3` | 7 |
| `#9b` | 7 |
| `#15` | 5 |
| `#17` | 4 |
| `#4k` | 1 |

