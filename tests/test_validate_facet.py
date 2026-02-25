#!/usr/bin/env python3
"""Tests for validate_facet.py — covers ai_execution field validation."""

import json
import subprocess
import sys
import os
import pytest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "scripts", "validate_facet.py"
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_FACET = {
    "session_id": "test-001",
    "date": "2026-02-25",
    "duration_min": 45,
    "goal": "测试 ai_execution 验证",
    "goal_category": "debug_fix",
    "outcome": "fully_achieved",
    "friction": ["tool_misuse"],
    "loop_detected": False,
    "loop_detail": "",
    "key_decision": "none",
    "learning": "ai_execution validation works",
    "tools_used": ["Claude"],
    "files_changed": 3,
    "domain_knowledge_gained": "madness skill internals",
    "ai_collab": {
        "sycophancy": "",
        "logic_leap": "",
        "lazy_prompting": "",
        "automation_surrender": "",
        "anchoring_effect": "",
    },
    "extraction_confidence": 0.85,
}


def make_facet(**overrides):
    """Return a copy of BASE_FACET with overrides merged."""
    f = json.loads(json.dumps(BASE_FACET))
    f.update(overrides)
    return f


def run_validate(facet: dict) -> dict:
    """Run validate_facet.py validate via subprocess, return parsed result."""
    proc = subprocess.run(
        [sys.executable, SCRIPT, "validate", "--input", "-"],
        input=json.dumps(facet),
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# ai_execution — backward compatibility
# ---------------------------------------------------------------------------


class TestAiExecutionBackwardCompat:
    """ai_execution is optional; missing it should warn, not error."""

    def test_missing_ai_execution_passes(self):
        r = run_validate(BASE_FACET)
        assert r["valid"] is True

    def test_missing_ai_execution_warns(self):
        r = run_validate(BASE_FACET)
        assert any("ai_execution" in w for w in r["warnings"])


# ---------------------------------------------------------------------------
# ai_execution — valid inputs
# ---------------------------------------------------------------------------


class TestAiExecutionValid:
    def test_complete_valid(self):
        r = run_validate(
            make_facet(
                ai_execution={
                    "param_fidelity": "用户给了 Playground 坐标但 AI 偏移了 50px",
                    "spec_compliance": "",
                    "first_round_accuracy": "partial",
                    "rework_attribution": "ai_deviation",
                }
            )
        )
        assert r["valid"] is True
        assert not any("ai_execution" in e for e in r["errors"])

    def test_all_empty_strings(self):
        """Empty strings = no issue detected, perfectly valid."""
        r = run_validate(
            make_facet(
                ai_execution={
                    "param_fidelity": "",
                    "spec_compliance": "",
                    "first_round_accuracy": "",
                    "rework_attribution": "",
                }
            )
        )
        assert r["valid"] is True

    @pytest.mark.parametrize("fra", ["correct", "partial", "wrong"])
    @pytest.mark.parametrize("ra", ["user_change", "ai_deviation", "both", ""])
    def test_all_enum_combos(self, fra, ra):
        r = run_validate(
            make_facet(
                ai_execution={
                    "param_fidelity": "",
                    "spec_compliance": "",
                    "first_round_accuracy": fra,
                    "rework_attribution": ra,
                }
            )
        )
        assert r["valid"] is True, f"fra={fra}, ra={ra} should be valid"


# ---------------------------------------------------------------------------
# ai_execution — type errors
# ---------------------------------------------------------------------------


class TestAiExecutionTypeErrors:
    def test_not_a_dict(self):
        r = run_validate(make_facet(ai_execution="bad"))
        assert r["valid"] is False
        assert any("must be a dict" in e for e in r["errors"])

    def test_subfield_not_string(self):
        r = run_validate(
            make_facet(
                ai_execution={
                    "param_fidelity": 123,
                    "spec_compliance": "",
                    "first_round_accuracy": "correct",
                    "rework_attribution": "",
                }
            )
        )
        assert r["valid"] is False
        assert any("param_fidelity" in e and "string" in e for e in r["errors"])


# ---------------------------------------------------------------------------
# ai_execution — missing sub-fields (warn, not error)
# ---------------------------------------------------------------------------


class TestAiExecutionMissingSubfields:
    def test_missing_3_subfields_still_valid(self):
        r = run_validate(make_facet(ai_execution={"param_fidelity": "test"}))
        assert r["valid"] is True

    def test_missing_3_subfields_warns(self):
        r = run_validate(make_facet(ai_execution={"param_fidelity": "test"}))
        missing = [w for w in r["warnings"] if "ai_execution missing key" in w]
        assert len(missing) == 3


# ---------------------------------------------------------------------------
# ai_execution — invalid enum values
# ---------------------------------------------------------------------------


class TestAiExecutionEnumErrors:
    def test_invalid_first_round_accuracy(self):
        r = run_validate(
            make_facet(
                ai_execution={
                    "param_fidelity": "",
                    "spec_compliance": "",
                    "first_round_accuracy": "invalid_value",
                    "rework_attribution": "",
                }
            )
        )
        assert r["valid"] is False
        assert any("first_round_accuracy" in e for e in r["errors"])

    def test_invalid_rework_attribution(self):
        r = run_validate(
            make_facet(
                ai_execution={
                    "param_fidelity": "",
                    "spec_compliance": "",
                    "first_round_accuracy": "correct",
                    "rework_attribution": "bad_value",
                }
            )
        )
        assert r["valid"] is False
        assert any("rework_attribution" in e for e in r["errors"])
