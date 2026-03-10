---
name: e2e-test-debugger
description: Use when Playwright tests have failed and you need to diagnose root causes from report files. Triggers on tasks like "debug failing tests", "analyze test failures", "why did these tests fail", "investigate CI failures", or when given a playwright-report directory.
---

# E2E Failed Test Debugger

Diagnose Playwright test failures from report files. Classifies root causes and provides concrete fixes.

## Prerequisites: Run Tests First

**Do NOT run `playwright test` directly and read its stdout** — output may be truncated by token-optimizing proxies (e.g. rtk). Instead:

```bash
npx playwright test --reporter=json 2>/dev/null > playwright-report/results.json
```

Then parse the report file in Phase 1.

## Phase 1: Extract Failures

```bash
# Find report if path not specified
find . -name "results.json" -path "*/playwright-report/*" | head -5

# Extract failed tests (jq)
cat playwright-report/results.json | jq '[
  .. | objects |
  select(.status == "failed" or .status == "timedOut") |
  {title: .title, status: .status, error: .error.message, file: .location.file, duration: .duration}
] | unique'

# Extract failed tests (node fallback)
node -e "
const r = require('./playwright-report/results.json');
const flat = (s) => [s, ...(s.suites||[]).flatMap(flat), ...(s.specs||[]).flatMap(sp => sp.tests||[])];
flat(r).filter(t => t.status === 'failed' || t.status === 'timedOut')
  .forEach(t => console.log(t.status, t.title, t.error?.message?.slice(0,120)))
"
```

## Phase 2: Classify Root Cause

Use Phase 1 output (error message + duration + file) to classify. **Most failures are identifiable here — only go to Phase 3 if still unclear.**

| # | Category | Signals | Review Pattern |
|---|----------|---------|----------------|
| F1 | **Flaky / Timing** | `TimeoutError`, duration near maxTimeout, passes on retry | #13a, #13c |
| F2 | **Selector Broken** | `locator not found`, `strict mode violation`, element count mismatch | #7, #14 |
| F3 | **Network Dependency** | `net::ERR_*`, unexpected API response, `404`/`500` | #13b |
| F4 | **Assertion Mismatch** | `Expected X to equal Y`, subject-inversion, over-broad check | #4, #11, #11b |
| F5 | **Missing Then** | Action completed but wrong state remains | #2 |
| F6 | **Condition Branch Missing** | Element conditionally present, assertion always runs | #6 |
| F7 | **Test Isolation Failure** | Passes alone, fails in suite; leaked state | — |
| F8 | **Environment Mismatch** | CI vs local only; viewport, OS, timezone | — |
| F9 | **Data Dependency** | Missing seed data, hardcoded IDs | — |
| F10 | **Auth / Session** | Session expired, role-based UI not rendered | — |
| F11 | **Async Order Assumption** | `Promise.all` order, parallel race | — |
| F12 | **POM / Locator Drift** | DOM changed, POM locator not updated | #14 |
| F13 | **Error Swallowing** | `.catch(() => {})` hiding failure, test passes silently | #3 |
| F14 | **Animation Race** | Element visible but content not yet rendered | #13c |

Classification steps:
1. Match error message to signals above
2. `duration` near timeout → F1 or F3
3. CI-only failure → F7 or F8
4. Passes on retry → F1

## Phase 3: Trace Analysis (only if Phase 2 is unclear)

`trace.zip` structure:
- `trace.trace` — newline-delimited JSON (actions, snapshots, console)
- `trace.network` — newline-delimited JSON (network requests)
- `resources/` — JPEG screenshots

```bash
find playwright-report -name "*.zip" | head -10
```

Progressive disclosure — stop as soon as root cause is clear:

```bash
# 1. Which step failed?
unzip -p trace.zip trace.trace | node -e "
process.stdin.resume(); let d='';
process.stdin.on('data',c=>d+=c);
process.stdin.on('end',()=>d.trim().split('\n').map(l=>JSON.parse(l))
  .filter(e=>e.type==='after'&&e.error)
  .forEach(e=>console.log(e.apiName, e.error.message)));"

# 2. All actions with pass/fail
unzip -p trace.zip trace.trace | node -e "
process.stdin.resume(); let d='';
process.stdin.on('data',c=>d+=c);
process.stdin.on('end',()=>d.trim().split('\n').map(l=>JSON.parse(l))
  .filter(e=>e.type==='after')
  .forEach((e,i)=>console.log(i, e.apiName, e.error?'❌ '+e.error.message.slice(0,80):'✓')));"

# 3a. Selector issue — DOM at failed step
#     replace SNAPSHOT_NAME with beforeSnapshot value from step 2 (e.g. "snapshot@call@123")
unzip -p trace.zip trace.trace | node -e "
process.stdin.resume(); let d='';
process.stdin.on('data',c=>d+=c);
process.stdin.on('end',()=>d.trim().split('\n').map(l=>JSON.parse(l))
  .filter(e=>e.type==='frame-snapshot'&&e.snapshot?.name==='SNAPSHOT_NAME')
  .forEach(e=>console.log(JSON.stringify(e.snapshot.html).slice(0,3000))));"

# 3b. Network issue — failed requests
unzip -p trace.zip trace.network | node -e "
process.stdin.resume(); let d='';
process.stdin.on('data',c=>d+=c);
process.stdin.on('end',()=>d.trim().split('\n').map(l=>JSON.parse(l))
  .filter(e=>e.type==='resource-snapshot'&&e.response?.status>=400)
  .forEach(e=>console.log(e.response.status, e.request.url)));"

# 3c. JS errors
unzip -p trace.zip trace.trace | node -e "
process.stdin.resume(); let d='';
process.stdin.on('data',c=>d+=c);
process.stdin.on('end',()=>d.trim().split('\n').map(l=>JSON.parse(l))
  .filter(e=>e.type==='console'&&e.messageType==='error')
  .forEach(e=>console.log(e.text)));"

# 3d. Still unclear — add temporary screenshots, re-run, inspect via browser agent
#     await page.screenshot({ path: 'debug/before.png' });
#     await someAction();
#     await page.screenshot({ path: 'debug/after.png' });
#     → dispatch browser agent to open and compare. Remove after debugging.
```

## Phase 4: Fix Suggestions

```markdown
## [P0/P1/P2] `test name`

- **Category:** F2 — Selector Broken (#14 POM Drift)
- **Error:** `locator('.submit-btn') strict mode violation, 3 elements found`
- **Root Cause:** Button selector too broad after DOM refactor
- **Fix:**
  ```typescript
  // before
  await page.locator('.submit-btn').click();
  // after
  await page.locator('form[data-testid="login-form"] button[type="submit"]').click();
  ```
```

**Severity:**
- **P0:** Test passes silently when feature is broken (F6, F13)
- **P1:** Intermittent or misleading failures (F1, F2, F3, F7, F11, F14)
- **P2:** Consistent failures, straightforward fix (F4, F5, F8, F9, F10, F12)

## Output Format

```markdown
## Failure Summary
- Total: N failed (M flaky, K broken, J environment)

## [P0] `test name` — F13 Error Swallowing
...

## Review Summary
| Sev | Count | Top Category | Files |
|-----|-------|-------------|-------|
| P0  | 1     | Error Swallowing | auth.spec.ts |
| P1  | 3     | Flaky / Timing | dashboard.spec.ts |
| P2  | 2     | POM Drift | settings.spec.ts |

Fix P0 first. Run `npx playwright test --retries=2` to confirm flaky tests.
```
