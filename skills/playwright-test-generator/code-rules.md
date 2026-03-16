# Code Generation Rules

## Structure Detection

| What you find | What to generate |
|---------------|-----------------|
| POM directory exists, no POM for this page | New POM class (extends `BasePage` if present) + spec file |
| POM directory exists, POM for this page already exists | Extend existing POM — add new locators only + new spec file |
| No POM directory anywhere | Flat spec file only |

**Extending an existing POM:** Read the file first. Match its existing naming and structural patterns — even if they differ from the rules below. Apply rules below only to newly added code.

---

## Selector Priority (best → worst)

1. `getByRole('button', { name: 'Submit' })` — role + accessible name
2. `getByLabel('Email')` — form label
3. `getByTestId('submit-btn')` / `[data-testid="submit-btn"]` — explicit test hook
4. `getByText('Save')` / `.filter({ hasText: 'text' })` — visible text
5. attribute selector `[formControlName="email"]` — stable attribute
6. CSS class — **POM files only**, stable structural classes only (not styling classes)
7. `.nth()` / `.first()` / `.last()` — **forbidden** without `// JUSTIFIED:` on the line above

Never use XPath. Never use CSS class chains that couple to styling.

---

## POM Rules (new files only)

```typescript
import { Page, Locator } from '@playwright/test';

export class LoginPage {
  readonly form: {
    emailInput: Locator;
    passwordInput: Locator;
    submitButton: Locator;
  };
  readonly errorMessage: Locator;

  constructor(private page: Page) {
    this.form = {
      emailInput: page.getByLabel('Email'),
      passwordInput: page.getByLabel('Password'),
      submitButton: page.getByRole('button', { name: 'Sign in' }),
    };
    this.errorMessage = page.getByText('Invalid credentials');
  }

  async navigate() {
    await this.page.goto('/login');
  }
}
```

- `readonly` locators only — no getter methods
- Composition pattern: group related locators into named objects
- `navigate()` uses `page.goto(path)` unless a custom navigation utility exists in the project

---

## Spec Rules

```typescript
import { test, expect } from '@playwright/test';
import { LoginPage } from '../models/login-page';

test.describe('Login', () => {
  let loginPage: LoginPage;

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page);
    await loginPage.navigate();
  });

  test('should sign in with valid credentials', async ({ page }) => {
    // Given: user is on the login page (handled by beforeEach)

    // When: user fills in valid credentials and submits
    await loginPage.form.emailInput.fill('user@example.com');
    await loginPage.form.passwordInput.fill('password123');
    await loginPage.form.submitButton.click();

    // Then: user is redirected to the dashboard
    await expect(page).toHaveURL('/dashboard');
  });

  test('should show error for invalid credentials', async () => {
    // Given: user is on the login page

    // When: user submits invalid credentials
    await loginPage.form.emailInput.fill('wrong@example.com');
    await loginPage.form.passwordInput.fill('badpassword');
    await loginPage.form.submitButton.click();

    // Then: error message is shown
    await expect(loginPage.errorMessage).toBeVisible();
  });
});
```

- BDD comments: `// Given:`, `// When:`, `// Then:`
- Each test fully independent — own storage, session, cookies
- `beforeEach` for shared navigation setup only — never for shared state
- Mock external APIs with Playwright Network API; do not call real third-party services
- **Auto-waiting assertions only:** `toBeVisible()`, `toBeHidden()`, `toHaveText()`, `toContainText()`, `toHaveCount()`, `toHaveURL()`
- Use `expect.soft()` when verifying multiple independent conditions in one test

**Forbidden:**

| Forbidden | Use instead |
|-----------|-------------|
| `waitForTimeout(N)` | `await expect(el).toBeVisible({ timeout: N })` |
| `expect(await el.isVisible()).toBe(true)` | `await expect(el).toBeVisible()` |
| `const n = await el.count()` | `await expect(el).toHaveCount(N)` or `.first()` + `toBeVisible()` |
| Framework component selectors in spec (`app-button`, `my-component`) | POM only |
| XPath selectors | `getByRole` / `getByLabel` / `getByTestId` |
