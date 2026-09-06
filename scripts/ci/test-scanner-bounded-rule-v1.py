#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""One noisy rule must not destroy the whole scan.

Found by running the scanner over public repositories at pinned commits: on
sweetalert2 (18k stars) the shipped `#15` check exceeded
`E2E_SMELL_MAX_RULE_HITS` and the scan exited 2 having printed no Summary at
all. react-router behaved the same way. A user pointing `scan.sh` at an
ordinary Playwright repository got nothing back — not a partial result, not a
list of what did run, nothing.

The bounded limit itself is right: an unbounded rule could stream forever. What
was wrong is the blast radius. A truncated rule must disqualify itself, not the
other twenty-odd checks that completed normally.

The result must still fail closed — exit stays 2 and the truncated rule is
named — because a scan with a suppressed rule is not authoritative and must
never read as clean.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCAN = ROOT / "skills/e2e-reviewer/scripts/scan.sh"


def scan(files: dict[str, str], env: dict[str, str] | None = None):
    with tempfile.TemporaryDirectory() as tmp:
        for name, content in files.items():
            path = Path(tmp) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        result = subprocess.run(
            ["/bin/bash", "-p", str(SCAN), tmp],
            capture_output=True,
            text=True,
            env={**os.environ, "E2E_SMELL_NO_ESLINT_DOWNLOAD": "1", **(env or {})},
        )
    return result


def noisy_tree(files: int, per_file: int) -> dict[str, str]:
    """Many unawaited Playwright expects: the shape that tripped #15 in the field."""
    header = "import { test, expect } from '@playwright/test';\n\n"
    out = {}
    for index in range(files):
        body = "\n".join(
            f"test('case {index}_{n}', async ({{ page }}) => {{\n"
            f"  expect(page.getByTestId('x{n}')).toBeVisible();\n}});"
            for n in range(per_file)
        )
        out[f"tests/gen{index}.spec.ts"] = header + body
    return out


class BoundedRuleTests(unittest.TestCase):
    def test_a_truncated_rule_still_leaves_a_summary(self) -> None:
        # Cap deliberately tiny so the tree is small and the test stays fast.
        result = scan(noisy_tree(6, 10), {"E2E_SMELL_MAX_RULE_HITS": "5"})
        out = result.stdout + result.stderr

        # The counts must appear, but never under a bare `Summary:` label.
        # That exact string is reserved for runs where every rule completed, so
        # a reader grepping for it cannot pick up partial counts as whole ones.
        self.assertRegex(
            out, r"(?m)^Summary \[INCOMPLETE",
            "a truncated rule must not suppress the counts for every other check",
        )
        self.assertNotRegex(
            out, r"(?m)^Summary:",
            "a bare `Summary:` must mean every rule ran",
        )
        self.assertIn(
            "INCOMPLETE", out,
            "the truncated rule must still be reported as incomplete",
        )
        self.assertEqual(
            result.returncode, 2,
            "a scan with a suppressed rule is not authoritative and must fail closed",
        )

    def test_the_truncated_rule_is_named(self) -> None:
        result = scan(noisy_tree(6, 10), {"E2E_SMELL_MAX_RULE_HITS": "5"})
        out = result.stdout + result.stderr
        self.assertRegex(
            out, r"INCOMPLETE.*#\d+",
            "the user needs to know which rule was suppressed, not just that one was",
        )

    def test_other_rules_still_report(self) -> None:
        files = noisy_tree(6, 10)
        # A distinct, low-volume smell that a working scan should still surface.
        files["tests/only.spec.ts"] = (
            "import { test, expect } from '@playwright/test';\n\n"
            "test.only('focused', async ({ page }) => {\n"
            "  await expect(page.getByTestId('a')).toBeVisible();\n});\n"
        )
        result = scan(files, {"E2E_SMELL_MAX_RULE_HITS": "5"})
        out = result.stdout + result.stderr
        self.assertIn(
            "#7", out,
            "checks that completed must still report; one noisy rule cannot mute them",
        )

    def test_an_unbounded_scan_is_unaffected(self) -> None:
        result = scan({
            "tests/a.spec.ts": (
                "import { test, expect } from '@playwright/test';\n\n"
                "test.only('focused', async ({ page }) => {\n"
                "  await expect(page.getByTestId('a')).toBeVisible();\n});\n"
            )
        })
        out = result.stdout + result.stderr
        self.assertNotIn("INCOMPLETE", out)
        self.assertRegex(out, r"(?m)^Summary:")
        self.assertEqual(result.returncode, 1, "a P0 finding still exits 1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
