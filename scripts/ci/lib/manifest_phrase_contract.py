# SPDX-License-Identifier: Apache-2.0
"""Canonical reviewer taxonomy keyed by checked ID, title, and severity."""

from __future__ import annotations


# (pattern ID, canonical Quick Reference title, severity group)
REVIEWER_TAXONOMY = (
    ("1", "Name-Assertion", "P0"),
    ("2", "Missing Then", "P0"),
    ("3", "Error Swallowing", "P0"),
    (
        "3b",
        "Cypress uncaught:exception suppression",
        "P0",
    ),
    (
        "4",
        "Vacuous / Retry-Weakening Assertions",
        "P0",
    ),
    ("5", "Bypass Patterns", "P0"),
    ("7", "Focused Test Leak", "P0"),
    ("8", "Missing Assertion", "P0"),
    ("12", "Missing Auth Setup", "P0"),
    ("6", "Raw DOM Queries", "P1"),
    ("9", "Hard-coded Sleeps", "P1"),
    ("10", "Flaky Test Patterns", "P1"),
    ("13", "Inconsistent POM Usage", "P1"),
    ("14", "Hardcoded Credentials", "P1"),
    ("15", "Missing await on expect", "P1"),
    ("16", "Missing await on action", "P1"),
    (
        "17",
        "Discouraged direct Page selector API",
        "P1",
    ),
    ("18", "`expect.soft()` dependency leak", "P1"),
    (
        "19",
        "Module-Level Mutable State",
        "P1",
    ),
    (
        "20",
        "Unmocked Real-Backend Writes",
        "P1",
    ),
    (
        "22",
        "Optimistic UI Without Call Proof",
        "P1",
    ),
    ("11", "YAGNI + Zombie Specs", "P2"),
    (
        "21",
        "Manual Session-File Dependency",
        "P2",
    ),
    (
        "23",
        "Fixture Ignores Render Guards",
        "P2",
    ),
)
