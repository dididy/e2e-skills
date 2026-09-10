# Field scan v1 — ledger

This ledger retains every listed hit captured from scans of the pinned public repositories, with nothing removed for how it looks. No model was called (`model_calls: 0`), no pull request was opened, and no upstream repository was modified. Each line below links to the exact line at the pinned commit, so any row can be checked without trusting this page.

## How to read the counts

- **P0** — the deterministic checks for silent always-pass shapes. These are the load-bearing hits.
- **Triage candidates** — hits the scanner tags `[LLM-TRIAGE]`. The scanner cannot decide these on its own, so they are **candidates for review, not defects**, and are never added to a defect total.
- **AST-origin** — Tier 2 hits counted in the scanner's own Summary but printed in a different shape, so they are reconciled here rather than re-listed.
- **Incomplete** — the scan failed, lacks a complete Summary, suppressed a rule, or has unreconciled counts. Its displayed counts are a floor, not a complete measurement. A `scanned` process status alone does not establish completion.

## Selection

The selection rule was frozen and committed before this scan ran: [`benchmarks/field-scan-v1/README.md`](../../benchmarks/field-scan-v1/README.md).

Repositories excluded as contaminated (already used in development): **32**. Scanned: **10/12**.

## Per repository

| Repository | Commit | P0 | Triage candidates | Other | AST-origin | Complete |
|---|---|---:|---:|---:|---:|:--:|
| [remix-run/react-router](https://github.com/remix-run/react-router) | [`7aea711dd1`](https://github.com/remix-run/react-router/tree/7aea711dd1ae2bc5a076d13ff17291829690fa74) | 0 | 251 | 221 | 231 | yes |
| [sweetalert2/sweetalert2](https://github.com/sweetalert2/sweetalert2) | [`566377edff`](https://github.com/sweetalert2/sweetalert2/tree/566377edff0ac0d8418972855fc34fa8542e80d2) | 0 | 29 | 0 | 0 | yes |
| [ixartz/SaaS-Boilerplate](https://github.com/ixartz/SaaS-Boilerplate) | [`e3952a7ed5`](https://github.com/ixartz/SaaS-Boilerplate/tree/e3952a7ed5b0ef172ac4363c4644b8c334d1094b) | 0 | 1 | 0 | 0 | yes |
| [ever-co/ever-gauzy](https://github.com/ever-co/ever-gauzy) | `54b537baf8` | — | — | — | — | timeout |
| [francoischalifour/medium-zoom](https://github.com/francoischalifour/medium-zoom) | [`21332eb3c5`](https://github.com/francoischalifour/medium-zoom/tree/21332eb3c5abc181b48251a06ee19fd7792fab22) | 0 | 4 | 1 | 0 | yes |
| [i5ting/imove](https://github.com/i5ting/imove) | [`0529e81271`](https://github.com/i5ting/imove/tree/0529e8127132380196ae14ea5f505b332dfcf8a6) | 0 | 31 | 46 | 0 | yes |
| [livestorejs/livestore](https://github.com/livestorejs/livestore) | [`583bf8420b`](https://github.com/livestorejs/livestore/tree/583bf8420b43eb32b2335c22e440d14ad73c1b9c) | 0 | 97 | 6 | 0 | yes |
| [kentcdodds/bookshelf](https://github.com/kentcdodds/bookshelf) | [`32e9e87db9`](https://github.com/kentcdodds/bookshelf/tree/32e9e87db958de863bead65761bfbe2dec0eafd4) | 0 | 45 | 1 | 0 | yes |
| [gautamkrishnar/nothing-private](https://github.com/gautamkrishnar/nothing-private) | [`7050e014a8`](https://github.com/gautamkrishnar/nothing-private/tree/7050e014a8e65041fd38bb42bc72f667b72ec0e7) | 0 | 2 | 0 | 0 | yes |
| [LekoArts/gatsby-themes](https://github.com/LekoArts/gatsby-themes) | [`0ee600732b`](https://github.com/LekoArts/gatsby-themes/tree/0ee600732beb88a49135760df9ed6f4d419fde2e) | 0 | 26 | 0 | 0 | yes |
| [open-mercato/open-mercato](https://github.com/open-mercato/open-mercato) | `8b492325d3` | — | — | — | — | timeout |
| [jhipster/jhipster-sample-app](https://github.com/jhipster/jhipster-sample-app) | [`e06e87abe0`](https://github.com/jhipster/jhipster-sample-app/tree/e06e87abe0be8a3a194381ce651164a734811b3f) | 0 | 70 | 0 | 0 | yes |
| **Total** | | **≥0** | **≥556** | **≥275** | **≥231** | |

2 repositories have no completed scan recorded in this ledger. Their findings are not included in the totals, which are floors rather than complete measurements.

## P0 hits

Deterministic P0 findings only. Triage candidates are listed separately below and are not defects.

_None listed._ This is not a finding of cleanliness: the incomplete or unavailable scans above can omit P0 findings.

## Triage candidates

**These are not defects.** The scanner flags them as needing a judgement it cannot make deterministically. They are published so the P0 column above cannot be inflated by quietly counting them.

| Pattern | Candidates |
|---|---:|
| `#4c-4e` | 77 |
| `#14` | 72 |
| `#10f` | 69 |
| `#4b` | 58 |
| `#10a` | 49 |
| `#10c` | 45 |
| `#4i` | 41 |
| `#5a` | 31 |
| `#11c` | 26 |
| `#16` | 25 |
| `#6` | 21 |
| `#18` | 9 |
| `#8a` | 8 |
| `#3` | 7 |
| `#9b` | 7 |
| `#15` | 5 |
| `#17` | 4 |
| `#4k` | 1 |
| `#4a` | 1 |

