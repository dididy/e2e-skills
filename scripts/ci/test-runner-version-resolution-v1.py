#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression test: resolve_runner_executable must not silently prefer a
stale CLI build merely because its install root sorts earlier in
trusted_runner_search_path().

Root cause this guards against: on a machine with codex-cli installed both
via Homebrew (/opt/homebrew/bin/codex) and via the standalone installer
(~/.local/bin/codex), trusted_runner_search_path() lists /opt/homebrew/bin
before ~/.local/bin. shutil.which() returns the first PATH hit, so the old
resolve_runner_executable silently picked whichever install happened to sit
in the earlier directory -- 0.149.0 (Homebrew) instead of the newer 0.152.1
(standalone installer) actually available on the same machine, regardless of
which one is more current. The fix enumerates every trusted install and
selects deterministically by actual installed version, not by directory
order.
"""

from __future__ import annotations

import importlib.util
import os
import stat
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/evals/run-reviewer-holdout.py"
BEHAVIORAL_PATH = ROOT / "scripts/evals/run-behavioral-evals.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_runner():
    return load_module("holdout_runner_for_version_test", RUNNER_PATH)


RUNNER = load_runner()
BEHAVIORAL = load_module("behavioral_runner_for_version_test", BEHAVIORAL_PATH)


def make_fake_codex(directory: Path, version: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / "codex"
    script.write_text(
        "#!/bin/sh\n"
        f'if [ "$1" = "--version" ]; then echo "codex-cli {version}"; exit 0; fi\n'
        "exit 1\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


class RunnerVersionResolutionTests(unittest.TestCase):
    def test_prefers_highest_installed_version_regardless_of_directory_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Reproduces the real bug layout: the earlier-searched directory
            # (stands in for /opt/homebrew/bin) holds the STALE build; a
            # later-searched directory (stands in for ~/.local/bin) holds the
            # CURRENT build.
            stale_dir = root / "early-searched-root"
            current_dir = root / "late-searched-root"
            stale = make_fake_codex(stale_dir, "0.149.0")
            current = make_fake_codex(current_dir, "0.152.1")
            fake_path = os.pathsep.join([str(stale_dir), str(current_dir)])

            with mock.patch.object(RUNNER, "trusted_runner_search_path", return_value=fake_path):
                resolved = RUNNER.resolve_runner_executable("codex")

            self.assertEqual(Path(resolved).resolve(), current.resolve())
            self.assertNotEqual(Path(resolved).resolve(), stale.resolve())

    def test_single_install_is_unaffected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            only_dir = Path(tmp) / "only-root"
            only = make_fake_codex(only_dir, "0.152.1")
            with mock.patch.object(
                RUNNER, "trusted_runner_search_path", return_value=str(only_dir)
            ):
                resolved = RUNNER.resolve_runner_executable("codex")
            self.assertEqual(Path(resolved).resolve(), only.resolve())

    def test_find_all_trusted_executables_deduplicates_identical_realpaths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_dir = root / "real"
            link_dir = root / "link-root"
            real = make_fake_codex(real_dir, "0.152.1")
            link_dir.mkdir(parents=True, exist_ok=True)
            (link_dir / "codex").symlink_to(real)
            fake_path = os.pathsep.join([str(real_dir), str(link_dir)])
            with mock.patch.object(RUNNER, "trusted_runner_search_path", return_value=fake_path):
                found = RUNNER.find_all_trusted_executables("codex")
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0], real.resolve())

    def test_meets_frozen_minimum_floor_after_deterministic_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale = make_fake_codex(root / "a", "0.149.0")
            current = make_fake_codex(root / "b", "0.152.1")
            fake_path = os.pathsep.join([str(root / "a"), str(root / "b")])
            with mock.patch.object(RUNNER, "trusted_runner_search_path", return_value=fake_path):
                resolved = RUNNER.resolve_runner_executable("codex")
                identity = RUNNER.command_output([resolved, "--version"])
            self.assertTrue(
                RUNNER.runner_identity_matches("codex", identity, "codex-cli 0.150.0", "minimum")
            )
            self.assertFalse(
                RUNNER.runner_identity_matches("codex", "codex-cli 0.149.0", "codex-cli 0.150.0", "minimum")
            )


class BehavioralRunnerVersionResolutionTests(unittest.TestCase):
    """run-behavioral-evals.py carries its own resolve_runner_executable.

    It must reach the same deterministic decision as the shared holdout
    runner: directory order in the trusted roots is not a freshness signal.
    Patching the SHARED module's search path is what proves delegation --
    if the behavioral copy still did its own first-match shutil.which, the
    layout below would resolve to the stale build.
    """

    def test_prefers_highest_installed_version_regardless_of_directory_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale_dir = root / "early-searched-root"
            current_dir = root / "late-searched-root"
            stale = make_fake_codex(stale_dir, "0.149.0")
            current = make_fake_codex(current_dir, "0.152.1")
            fake_path = os.pathsep.join([str(stale_dir), str(current_dir)])

            with mock.patch.object(
                BEHAVIORAL.SHARED_RUNNER,
                "trusted_runner_search_path",
                return_value=fake_path,
            ):
                resolved = BEHAVIORAL.resolve_runner_executable("codex")

            self.assertEqual(Path(resolved).resolve(), current.resolve())
            self.assertNotEqual(Path(resolved).resolve(), stale.resolve())

    def test_single_install_is_unaffected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            only_dir = Path(tmp) / "only-root"
            only = make_fake_codex(only_dir, "0.152.1")
            with mock.patch.object(
                BEHAVIORAL.SHARED_RUNNER,
                "trusted_runner_search_path",
                return_value=str(only_dir),
            ):
                resolved = BEHAVIORAL.resolve_runner_executable("codex")
            self.assertEqual(Path(resolved).resolve(), only.resolve())

    def test_unparsable_versions_fall_back_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_dir = root / "a"
            second_dir = root / "b"
            for directory in (first_dir, second_dir):
                directory.mkdir(parents=True, exist_ok=True)
                script = directory / "codex"
                script.write_text("#!/bin/sh\necho 'no version here'\n", encoding="utf-8")
                script.chmod(
                    script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
                )
            fake_path = os.pathsep.join([str(first_dir), str(second_dir)])
            with mock.patch.object(
                BEHAVIORAL.SHARED_RUNNER,
                "trusted_runner_search_path",
                return_value=fake_path,
            ):
                resolved = BEHAVIORAL.resolve_runner_executable("codex")
            # Unparsable identity must not crash and must stay inside the
            # trusted roots rather than falling through to ambient PATH.
            self.assertIn(
                Path(resolved).resolve().parent,
                {first_dir.resolve(), second_dir.resolve()},
            )

    def test_custom_runner_still_requires_absolute_path(self) -> None:
        # The behavioral runner is stricter than the shared one here; the
        # delegation must not loosen it.
        with self.assertRaises(ValueError):
            BEHAVIORAL.resolve_runner_executable("some/relative/tool")

    def test_untrusted_ambient_path_is_not_consulted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trusted_dir = root / "trusted"
            ambient_dir = root / "ambient"
            trusted = make_fake_codex(trusted_dir, "0.150.0")
            make_fake_codex(ambient_dir, "9.9.9")
            with mock.patch.object(
                BEHAVIORAL.SHARED_RUNNER,
                "trusted_runner_search_path",
                return_value=str(trusted_dir),
            ):
                with mock.patch.dict(
                    os.environ, {"PATH": str(ambient_dir)}, clear=False
                ):
                    resolved = BEHAVIORAL.resolve_runner_executable("codex")
            # The higher-versioned ambient build must be ignored entirely.
            self.assertEqual(Path(resolved).resolve(), trusted.resolve())


if __name__ == "__main__":
    unittest.main(verbosity=2)
