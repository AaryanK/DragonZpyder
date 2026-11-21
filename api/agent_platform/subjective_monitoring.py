"""Evidence-bound subjective-monitoring recommendation contract.

This module validates provenance/approval boundaries, not the correctness of
subjective judgment. The verdict still needs human rubric evaluation.
No tools, credentials, or external side effects are available here.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SubjectiveRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observed_bucket: str = Field(min_length=1, max_length=80)
    verdict: Literal["ignore", "watch", "escalate"]
    uncertainty: Literal["low", "medium", "high"]
    rationale: str = Field(min_length=20, max_length=1500)
    evidence_ids: list[str] = Field(min_length=1, max_length=10)
    counterargument: str = Field(min_length=20, max_length=1000)

    @field_validator("evidence_ids")
    @classmethod
    def distinct_evidence_ids(cls, values: list[str]):
        if len(values) != len(set(values)):
            raise ValueError("Evidence ID repeated")
        if any(not isinstance(i, str) or not 1 <= len(i) <= 80 for i in values):
            raise ValueError("Invalid evidence ID")
        return values


def validate_subjective_recommendation(
    candidate: SubjectiveRecommendation,
    *,
    observed_bucket: str,
    available_evidence_ids: set[str],
) -> dict:
    """Check trace linkage and abstain from automated approval.

    Do not label the model's recommendation objectively correct. Even
    high-confidence recommendations cannot authorize an external mutation.
    """
    if candidate.observed_bucket != observed_bucket:
        raise ValueError("Recommendation references a different observation bucket")
    if not available_evidence_ids or not set(candidate.evidence_ids) <= available_evidence_ids:
        raise ValueError("Unverifiable subjective evidence reference")
    return {
        "verdict": candidate.verdict,
        "uncertainty": candidate.uncertainty,
        "evidence_references_valid": True,
        "verification": "evidence_references_only",
        "subjective_correctness_verified": False,
        "human_review_required": True,
        "external_action_authorized": False,
    }
