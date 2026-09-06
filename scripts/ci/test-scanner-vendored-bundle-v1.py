#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A vendored tool bundle must not be mistaken for test source.

Found while explaining why the field scan failed to finish on four of twelve
pinned public repositories. On LekoArts/gatsby-themes the scanner spent 676
seconds inside a single check that had two candidates. One of them was in
`.yarn/releases/yarn-4.8.1.cjs`: a vendored Yarn bundle whose longest line is
337,344 characters, on a line 81,499 characters long.

Two faults compounded. The scan runs with `--hidden --no-ignore` and treats
`.cjs` as source, and the exclusion list -- which already drops node_modules,
dist, build, out and coverage -- has no entry for vendored package-manager
bundles, which are not named `*.min.*`. Then the shipped lexer builds its output
one character at a time, which is quadratic in line length, so a single line of
that size costs seconds on every pass.

Yarn Berry and PnP layouts are common, so this is not an exotic input. A user
pointing the scanner at such a repository waits indefinitely.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCAN = ROOT / "skills/e2e-reviewer/scripts/scan.sh"

# A tree holding one spec file scans in about five seconds. The vendored
# bundle alone pushed the same scan past eighty. The budget sits between the
# two so the pathology fails the test and ordinary slowness does not.
BUDGET_SECONDS = 30


def tree_with_vendored_bundle(tmp: Path) -> None:
    spec = tmp / "tests/app.spec.ts"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(
        "import { test, expect } from '@playwright/test';\n\n"
        "test.only('focused', async ({ page }) => {\n"
        "  await expect(page.getByTestId('a')).toBeVisible();\n});\n",
        encoding="utf-8",
    )
    # The shape that matters: a hidden vendored directory, a .cjs extension, and
    # one enormous line carrying a token the scanner looks for.
    bundle = tmp / ".yarn/releases/yarn-4.8.1.cjs"
    bundle.parent.mkdir(parents=True, exist_ok=True)
    filler = "var a=1;" * 12000
    bundle.write_text(
        "#!/usr/bin/env node\n"
        f"{filler}document.querySelector('#x');{filler}\n",
        encoding="utf-8",
    )


class VendoredBundleTests(unittest.TestCase):
    def test_scan_finishes_and_reports(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            tree_with_vendored_bundle(tmp)
            started = time.monotonic()
            result = subprocess.run(
                ["/bin/bash", "-p", str(SCAN), str(tmp)],
                capture_output=True,
                text=True,
                timeout=BUDGET_SECONDS,
                env={**os.environ, "E2E_SMELL_NO_ESLINT_DOWNLOAD": "1"},
            )
            elapsed = time.monotonic() - started

        out = result.stdout + result.stderr
        self.assertRegex(
            out, r"(?m)^Summary",
            "the scan must produce a Summary rather than stalling on vendored code",
        )
        self.assertIn(
            "#7", out,
            "the real focused-test finding in tests/ must still be reported",
        )
        self.assertLess(
            elapsed, BUDGET_SECONDS,
            "a vendored bundle must not dominate the scan's runtime",
        )

    def test_vendored_bundle_is_not_a_finding_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            tree_with_vendored_bundle(tmp)
            result = subprocess.run(
                ["/bin/bash", "-p", str(SCAN), str(tmp)],
                capture_output=True,
                text=True,
                timeout=BUDGET_SECONDS,
                env={**os.environ, "E2E_SMELL_NO_ESLINT_DOWNLOAD": "1"},
            )
        out = result.stdout + result.stderr
        self.assertNotIn(
            "yarn-4.8.1.cjs", out,
            "a vendored package-manager bundle is not the project's test code",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
