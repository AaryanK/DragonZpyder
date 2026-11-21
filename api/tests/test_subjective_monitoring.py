"""Subjective monitor assessments are evidence-linked but never self-approved."""
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.subjective_monitoring import (
    SubjectiveRecommendation, validate_subjective_recommendation,
)


def candidate(**changes):
    data = {
        "observed_bucket": "2026-11-21T08:15:00+00:00",
        "verdict": "escalate",
        "uncertainty": "medium",
        "rationale": "The sustained elevated memory merits investigation before remediation.",
        "evidence_ids": ["ram:08:15", "ram:08:10"],
        "counterargument": "A legitimate batch job may explain the sudden memory use.",
    }
    return SubjectiveRecommendation(**{**data, **changes})


def test_subjective_escalation_is_advice_even_with_grounded_evidence():
    v = validate_subjective_recommendation(
        candidate(), observed_bucket="2026-11-21T08:15:00+00:00",
        available_evidence_ids={"ram:08:15", "ram:08:10", "disk:08:15"},
    )
    assert v["verdict"] == "escalate"
    assert v["evidence_references_valid"]
    assert not v["subjective_correctness_verified"]
    assert v["human_review_required"]
    assert not v["external_action_authorized"]
    assert v["verification"] == "evidence_references_only"


def test_subjective_verdict_must_reference_current_observations():
    with pytest.raises(ValueError, match="different observation bucket"):
        validate_subjective_recommendation(
            candidate(), observed_bucket="2026-11-21T08:20:00+00:00",
            available_evidence_ids={"ram:08:15", "ram:08:10"},
        )
    with pytest.raises(ValueError, match="Unverifiable"):
        validate_subjective_recommendation(
            candidate(evidence_ids=["fabricated:00:00"]),
            observed_bucket="2026-11-21T08:15:00+00:00",
            available_evidence_ids={"ram:08:15", "ram:08:10"},
        )


def test_subjective_proposals_require_substantive_counterarguments_and_no_extra_args():
    for fields in (
        {"rationale": "Fine"},
        {"counterargument": "No"},
        {"evidence_ids": ["ram:08:15", "ram:08:15"]},
        {"verdict": "delete_service"},
        {"secret_token": "must-not-be accepted"},
    ):
        with pytest.raises(ValidationError):
            candidate(**fields)
