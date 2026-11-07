"""Permanent regression for the owner's non-disruptive browser contract.

This is a documentation/agent policy test; no browser is launched.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANON = "docs/operations/nonintrusive-desktop-and-browser-rule.md"


class NonintrusiveDesktopRuleTest(unittest.TestCase):
    def test_both_agent_entrypoints_link_canonical_rule(self):
        for relative in ("AGENTS.md", ".github/copilot-instructions.md"):
            with self.subTest(path=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(CANON, text)

    def test_policy_is_fail_closed_and_specific(self):
        rule = (ROOT / CANON).read_text(encoding="utf-8")
        for required in (
            "owner-owned, not automation infrastructure",
            "Do **not** open Chrome/Edge/Firefox windows",
            "attach DevTools/CDP",
            "focus changes",
            "blocked / owner-interaction-required",
            "fresh, explicit, task-specific request",
            "one existing approved profile and one window",
            "Do not open it remotely",
            "never reset/clean the owner's dirty checkout",
        ):
            with self.subTest(phrase=required):
                self.assertIn(required, rule)

    def test_noninteractive_ci_remains_permitted(self):
        rule = (ROOT / CANON).read_text(encoding="utf-8")
        self.assertIn("Headless browser tests", rule)
        self.assertIn("truly isolated CI runner", rule)
        self.assertIn("not by itself", rule)


if __name__ == "__main__":
    unittest.main()
