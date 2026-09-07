#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The candidate manifest must still refuse what it refused before.

The manifest fingerprints every candidate file and is rebuilt and revalidated
six times per scan, so that a file changing underneath the scanner is caught
rather than silently scanned in two states. It is an integrity control, not a
cache.

It used to spawn one `python3` per candidate per pass -- 1,800 interpreters for
300 files -- which is about 0.18 s per code file before a single finding is
evaluated, and on a 9,232-file repository roughly 28 minutes on its own. That
is now one interpreter per pass. The fingerprinting code did not change; only
the number of processes running it did.

Which makes the failure path the thing worth testing. These cases assert that a
candidate the scanner cannot fingerprint still stops the scan with the same
message and exit code, and that a clean tree still produces a Summary. A
performance change to an integrity control has to be checked where the control
does its work, not only where it is fast.

Note the layering: a FIFO or symlink named like a spec is rejected earlier, by
the tree preflight, and never reaches the manifest. An unreadable regular file
passes preflight and fails at fingerprinting, which is why that is the case
used here.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCAN = ROOT / "skills/e2e-reviewer/scripts/scan.sh"

SPEC = (
    "import { test, expect } from '@playwright/test';\n"
    "test('a', async ({ page }) => {\n"
    "  await expect(page.getByTestId('x')).toBeVisible();\n});\n"
)


def run(tree: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/bin/bash", "-p", str(SCAN), str(tree)],
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "E2E_SMELL_NO_ESLINT_DOWNLOAD": "1"},
    )


class ManifestTests(unittest.TestCase):
    def test_an_unfingerprintable_candidate_stops_the_scan(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tree = Path(raw)
            (tree / "tests").mkdir()
            (tree / "tests/ok.spec.ts").write_text(SPEC, encoding="utf-8")
            locked = tree / "tests/locked.spec.ts"
            locked.write_text(SPEC, encoding="utf-8")
            locked.chmod(0o000)
            try:
                result = run(tree)
            finally:
                locked.chmod(0o644)

        out = result.stdout + result.stderr
        self.assertEqual(
            result.returncode, 2,
            "a candidate that cannot be fingerprinted must fail the scan closed",
        )
        self.assertIn(
            "scanner candidate changed after discovery", out,
            "the scan must say why it stopped",
        )
        self.assertIn(
            "locked.spec.ts", out,
            "the message must name the candidate that failed, not another one",
        )
        self.assertNotRegex(
            out, r"(?m)^Summary",
            "a scan that could not fingerprint a candidate must emit no Summary",
        )

    def test_a_clean_tree_still_scans(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tree = Path(raw)
            (tree / "tests").mkdir()
            (tree / "tests/focused.spec.ts").write_text(
                "import { test, expect } from '@playwright/test';\n"
                "test.only('a', async ({ page }) => {\n"
                "  await expect(page.getByTestId('x')).toBeVisible();\n});\n",
                encoding="utf-8",
            )
            result = run(tree)

        out = result.stdout + result.stderr
        self.assertRegex(out, r"(?m)^Summary", "a clean tree must reach a Summary")
        self.assertNotIn("scanner candidate changed", out)
        self.assertEqual(result.returncode, 1, "the focused-test finding still exits 1")

    def test_every_candidate_is_fingerprinted_not_just_the_first(self) -> None:
        """One interpreter per pass must not mean one file per pass."""
        with tempfile.TemporaryDirectory() as raw:
            tree = Path(raw)
            (tree / "tests").mkdir()
            for index in range(6):
                (tree / f"tests/s{index}.spec.ts").write_text(SPEC, encoding="utf-8")
            # The failure is last in path order, so reaching it proves the pass
            # did not stop after the first record.
            locked = tree / "tests/zz_last.spec.ts"
            locked.write_text(SPEC, encoding="utf-8")
            locked.chmod(0o000)
            try:
                result = run(tree)
            finally:
                locked.chmod(0o644)

        out = result.stdout + result.stderr
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            "zz_last.spec.ts", out,
            "the pass must fingerprint every candidate, not stop at the first",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
