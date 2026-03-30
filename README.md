# e2e-skills — E2E Test Generation, Review, and Debugging

E2E tests that always pass are worse than no tests — they give false confidence while real bugs slip through. A [Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview) plugin that catches what CI misses: **tests that pass but prove nothing**, and **failures that are hard to trace**.

Four complementary skills that cover the full E2E lifecycle:

1. **`playwright-test-generator`** — generates Playwright E2E tests from scratch, from coverage gap analysis to passing, reviewed tests
2. **`e2e-reviewer`** — static analysis of existing Playwright, Cypress, and Puppeteer specs; finds 13 anti-patterns that make tests pass CI while missing real regressions
3. **`playwright-debugger`** — diagnoses failures from `playwright-report/` and classifies root causes (flaky timing, selector drift, auth, environment mismatch, and more)
4. **`cypress-debugger`** — same for Cypress report files

### Workflow

1. Run `playwright-test-generator` → generate with approval → auto-reviewed by `e2e-reviewer`
2. Generated tests fail → `playwright-debugger` invoked automatically after 3 fix attempts
3. Existing tests: `e2e-reviewer` → fix → re-run
4. Tests fail → `playwright-debugger` or `cypress-debugger` → fix → re-run

## Installation

```bash
# npx skills (recommended)
npx skills install dididy/e2e-skills

# Claude Code plugin marketplace
/plugin marketplace add dididy/e2e-skills
/plugin install e2e-skills@dididy

# Clone directly
mkdir -p ~/.claude/skills
git clone https://github.com/dididy/e2e-skills.git ~/.claude/skills/e2e-skills
```

---

## Skill 1: `playwright-test-generator` — Test Generation

Generates Playwright E2E tests from scratch for any project. Starts from coverage gap analysis, explores the live app via agent-browser tools, designs scenarios with your approval, and auto-reviews generated tests with `e2e-reviewer`.

### When to Use

- You have a page or feature with no E2E coverage
- You want to bootstrap a test suite for an existing app
- You need to quickly add tests before a release

### Usage

```
Generate playwright tests
Generate playwright tests for the login page
Write e2e tests for the settings page
Add playwright coverage for checkout flow
```

### Pipeline

```
Step 1: Detect environment (config, baseURL, test dir, POM structure)
Step 2: Coverage gap analysis → user picks target
Step 3: Live browser exploration via agent-browser tools
Step 4: Scenario design → Plan Mode → user approves
Step 5: Code generation (POM + spec or flat spec, auto-detected)
Step 6: YAGNI audit + e2e-reviewer quality gate
Step 7: TS compile + test run → playwright-debugger on failure
```

### Key Behaviors

- **Structure-aware**: detects POM pattern and matches project conventions
- **No hallucinated selectors**: explores real DOM before writing any code
- **Approval gate**: shows scenario plan and locator table before generating code
- **Quality loop**: YAGNI audit removes unused locators; `e2e-reviewer` catches P0 issues before you ever run the tests
- **Self-healing**: 3 auto-fix attempts on failure, then hands off to `playwright-debugger`

---

## Skill 2: `e2e-reviewer` — Quality Review

Catches issues in E2E tests that pass CI but fail to catch real regressions.

### When to Use

- Your tests always pass but bugs still slip through to production
- Tests pass CI but you suspect they miss real regressions
- Your test suite is fragile — tests break on every UI change
- You want to audit test quality before a release or code review
- You're reviewing Playwright, Cypress, or Puppeteer specs

### Usage

```
Review my E2E tests
Audit the spec files in tests/
Find weak tests in my test suite
My tests always pass but miss bugs
Tests pass CI but miss regressions
My tests are fragile and break on every UI change
We have coverage but bugs still slip through
```

### 13 Patterns Detected

#### Tier 1 — P0/P1 (always check)

| # | Pattern | Before | After |
|---|---------|--------|-------|
| 1 | **Name-assertion mismatch** | Name says "status" but only checks `toBeVisible()` | Add assertion for status content, or rename to match actual check |
| 2 | **Missing Then** | Cancel action, verify text restored — but input still visible? | Verify both restored state and dismissed state |
| 3 | **Error swallowing** | `try/catch` in spec, `.catch(() => {})` in POM | Let errors fail; remove silent catch from POM methods |
| 4 | **Always-passing assertion** | `toBeGreaterThanOrEqual(0)`; `toBeAttached()` with no comment; `expect(await el.isVisible()).toBe(true)` (one-shot); `expect(await el.textContent()).toBe(x)` (one-shot); `expect(locator).toBeTruthy()` (Locator always truthy); `{ timeout: 0 }` on assertions (disables retry) | `toBeGreaterThan(0)`; `toBeVisible()`; web-first assertions with auto-retry |
| 5 | **Bypass patterns** | `if (await el.isVisible()) { expect(...) }`; `{ force: true }` without comment | Always assert; move env checks to `beforeEach`; add `// JUSTIFIED:` to force:true |
| 6 | **Raw DOM queries** | `document.querySelector` in `evaluate()` | Use framework element API (`locator` / `cy.get` / `page.$`) |
| 7 | **Focused test leak** | `test.only(...)` committed — CI runs one test, silently skips the rest | Delete `.only`; use `--grep` or `--spec` for local focus |
| 8 | **Missing assertion** | `await page.locator('.x');` (discarded); `await el.isVisible();` (boolean thrown away) | Add `await expect(locator).toBeVisible()` or delete the line |

#### Tier 2 — P1/P2 (check when time permits)

| # | Pattern | Before | After |
|---|---------|--------|-------|
| 9 | **Hard-coded sleep** | `waitForTimeout(2000)` / `cy.wait(2000)` | Rely on framework auto-wait; use condition-based waits |
| 10 | **Flaky test patterns** | `items.nth(2)` without comment; `test.describe.serial()` | Use `data-testid` or role selectors; replace serial with self-contained tests |
| 11 | **YAGNI + Zombie Specs** | `clickEdit()` never called; empty wrapper class; single-use Util; entire spec duplicated by another | Delete unused members; inline single-use Util methods; delete zombie spec files |
| 18 | **`expect.soft()` overuse** | All assertions in a test are `expect.soft()` — test never fails early | Ensure at least one hard `expect()` gates per test; use `soft` only for independent details |
| 3b | **Cypress `uncaught:exception` suppression** | `cy.on('uncaught:exception', () => false)` blanket-swallows app errors | Scope handler to specific known errors; re-throw unknown errors |

### References

- [Playwright best practices](https://playwright.dev/docs/best-practices)
- [Cypress best practices](https://docs.cypress.io/app/core-concepts/best-practices)

### Review Workflow

Three-phase review with P0/P1/P2 severity:

1. **Phase 1: Automated grep** — mechanically detects #3 (POM `.catch()`), #3b (Cypress `uncaught:exception`), #4 (always-passing), #5 (bypass patterns), #6 (raw DOM queries), #7 (focused test leak), #8 (missing assertions), #9 (hard-coded sleeps), #10 partial (positional selectors, describe.serial), #18 (`expect.soft()`)
2. **Phase 2: LLM analysis** — #1 name-assertion alignment, #2 missing Then, #3 `try/catch` in specs (context-dependent), #8 Cypress dangling selectors, #10 flaky pattern judgment, #11 YAGNI + zombie specs, #18 overuse confirmation
3. **Phase 3: Coverage gaps** — suggests missing error paths, edge cases, accessibility, and auth boundary tests

---

## Skill 3: `playwright-debugger` — Playwright Failure Debugger

Diagnoses Playwright test failures from a `playwright-report/` directory — whether failures happened locally or in CI. Classifies root causes and provides concrete fixes.

### When to Use

- You have a `playwright-report/` directory (local or downloaded from CI) with failures to understand
- Tests pass locally but fail in CI
- You're dealing with flaky or intermittent test failures
- You get `TimeoutError` or `locator not found` without a clear cause

### Usage

```
Debug these failing tests
Why did these tests fail?
Tests pass locally but fail in CI
```

> **Note:** Provide the report as a local path. Download CI artifacts manually from GitHub Actions and pass the directory path — automatic artifact fetching is not supported.

### 14 Root Cause Categories

| # | Category | Signals |
|---|----------|---------|
| F1 | **Flaky / Timing** | `TimeoutError`, passes on retry |
| F2 | **Selector Broken** | `locator not found`, strict mode violation |
| F3 | **Network Dependency** | `net::ERR_*`, unexpected API response |
| F4 | **Assertion Mismatch** | `Expected X to equal Y`, subject-inversion |
| F5 | **Missing Then** | Action completed but wrong state remains |
| F6 | **Condition Branch Missing** | Element conditionally present, assertion always runs |
| F7 | **Test Isolation Failure** | Passes alone, fails in suite |
| F8 | **Environment Mismatch** | CI vs local only; viewport, OS, timezone |
| F9 | **Data Dependency** | Missing seed data, hardcoded IDs |
| F10 | **Auth / Session** | Session expired, role-based UI not rendered |
| F11 | **Async Order Assumption** | `Promise.all` order, parallel race |
| F12 | **POM / Locator Drift** | DOM structure changed, POM not updated |
| F13 | **Error Swallowing** | `.catch(() => {})` hiding actual failure |
| F14 | **Animation Race** | Element visible but content not yet rendered |

### Debug Workflow

1. **Extract** — parse `results.json` for failed tests, error messages, duration
2. **Classify** — map each failure to F1–F14 using error signals (most failures resolved here)
3. **Trace** — if still unclear, extract `trace.zip` and inspect step-by-step: failed actions, DOM snapshots, network errors, JS console errors
4. **Fix** — concrete code suggestion per failure, P0/P1/P2 priority

---

## Skill 4: `cypress-debugger` — Cypress Failure Debugger

Diagnoses Cypress test failures from mochawesome or JUnit report files. Classifies root causes and provides concrete fixes.

### When to Use

- You have a `cypress/reports/` directory (local or downloaded from CI) with failures to understand
- Cypress tests pass locally but fail in CI
- You're dealing with flaky or intermittent Cypress failures
- You get `Timed out retrying` or `Expected to find element` without a clear cause

### Usage

```
Debug these failing Cypress tests
Why did these Cypress tests fail?
Analyze cypress/reports/
Cypress tests pass locally but fail in CI
```

### 14 Root Cause Categories

| # | Category | Signals |
|---|----------|---------|
| F1 | **Flaky / Timing** | `Timed out retrying`, passes on retry |
| F2 | **Selector Broken** | `Expected to find element`, `cy.get() failed` |
| F3 | **Network Dependency** | `cy.intercept()` not matched, `XHR failed` |
| F4 | **Assertion Mismatch** | `expected X to equal Y`, `AssertionError` |
| F5 | **Missing Then** | Action completed but wrong state remains |
| F6 | **Condition Branch Missing** | Element conditionally present, assertion always runs |
| F7 | **Test Isolation Failure** | Passes alone, fails in suite |
| F8 | **Environment Mismatch** | CI vs local only; baseUrl, viewport, OS |
| F9 | **Data Dependency** | Missing seed data, `cy.fixture()` mismatch |
| F10 | **Auth / Session** | `cy.session()` expired, role-based UI not rendered |
| F11 | **Async Order Assumption** | `.then()` chain order, parallel `cy.request()` race |
| F12 | **Selector Drift** | DOM changed, custom command or POM selector not updated |
| F13 | **Error Swallowing** | `cy.on('uncaught:exception', () => false)` hiding failures |
| F14 | **Animation Race** | Element visible but content not yet rendered |

### Debug Workflow

1. **Extract** — parse `mochawesome.json` or JUnit XML for failed tests, error messages, duration
2. **Classify** — map each failure to F1–F14 using error signals (most failures resolved here)
3. **Screenshot/Video** — if still unclear, inspect `cypress/screenshots/` and `cypress/videos/`
4. **Fix** — concrete code suggestion per failure, P0/P1/P2 priority

---

## Compatibility

**`playwright-test-generator`** — Playwright only. Generates tests for any project with a `playwright.config.ts`. Uses agent-browser tools for live exploration; falls back to `npx playwright codegen` for manual selector discovery.

**`e2e-reviewer`** — Framework-agnostic. Covers [Playwright](https://playwright.dev/), [Cypress](https://www.cypress.io/), and [Puppeteer](https://pptr.dev/).

**`playwright-debugger`** — Playwright only. Parses `results.json` and `trace.zip` from `playwright-report/`.

**`cypress-debugger`** — Cypress only. Parses `mochawesome.json` or JUnit XML from `cypress/reports/`.

## License

Apache-2.0 — same as [anthropics/skills](https://github.com/anthropics/skills).
