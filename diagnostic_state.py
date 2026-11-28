"""Structured reply schema and evidence-backed notes for a troubleshooting session."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SpecializedCategory = Literal["internet", "performance", "storage", "audio", "gaming"]
Category = Literal[SpecializedCategory, "general"]
FactKind = Literal["system_information", "symptoms", "recent_changes", "attempted_steps", "reported_results"]

FACT_LABELS: dict[FactKind, str] = {
    "system_information": "System information",
    "symptoms": "Reported symptoms",
    "recent_changes": "Recent changes",
    "attempted_steps": "Steps already tried",
    "reported_results": "Reported results",
}


class Stage(StrEnum):
    IDENTIFY = "Problem identification"
    GATHER = "Gathering diagnostic information"
    EVALUATE = "Evaluating possible causes"
    GUIDE = "Guided troubleshooting"
    RESOLVE = "Resolution or escalation"


class ReportedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote: str = Field(description="An exact excerpt of a user message, including relevant qualifiers.")
    replaces: str | None = Field(description="The exact old note an explicit user correction supersedes, or null.")


class FactUpdates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system_information: list[ReportedFact] = Field(description="Reported Windows version or relevant hardware.")
    symptoms: list[ReportedFact] = Field(description="Specific behavior or an error reported by the user.")
    recent_changes: list[ReportedFact] = Field(description="Reported changes around the time the problem began.")
    attempted_steps: list[ReportedFact] = Field(description="Actions the user reports already taking.")
    reported_results: list[ReportedFact] = Field(description="What the user reports happened after an action.")


class PossibleCause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis: str
    evidence: str


class GuidedStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    title: str
    instructions: str
    expected: str = Field(description="What to look for or what should happen, without promising a fix.")
    safety: str | None = Field(description="Necessary warnings, prerequisites, or a safer alternative, or null.")


class StepOutcome(StrEnum):
    SOLVED = "Problem solved"
    STILL_A_PROBLEM = "Still having the problem"
    UNABLE = "Unable to complete this step"


@dataclass(frozen=True)
class StepFeedback:
    title: str
    instructions: str
    outcome: StepOutcome
    details: str


class DiagnosticReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str
    detected_category: Category | None
    stage: Stage
    new_facts: FactUpdates
    possible_causes: list[PossibleCause]
    unresolved_questions: list[str]
    citation_ids: list[str] = Field(description="IDs of supplied references actually used to support this reply.")
    step: GuidedStep | None = Field(description="One manual troubleshooting action, or null if none is recommended.")

    @model_validator(mode="before")
    @classmethod
    def ignore_unusable_citations(cls, data):
        """A missing or malformed citation field should not discard otherwise usable guidance."""
        if not isinstance(data, dict):
            return data
        ids = data.get("citation_ids")
        return {**data, "citation_ids": [item for item in ids if isinstance(item, str)] if isinstance(ids, list) else []}


@dataclass
class DiagnosticMemory:
    original_problem: str | None = None
    detected_category: Category | None = None
    stage: Stage = Stage.IDENTIFY
    facts: dict[FactKind, list[str]] = field(default_factory=dict)
    possible_causes: list[str] = field(default_factory=list)
    unresolved_questions: list[str] = field(default_factory=list)
    step_history: list[StepFeedback] = field(default_factory=list)

    def apply(self, reply: DiagnosticReply, user_reports: list[str]) -> None:
        """Apply one valid turn, keeping reported details until an explicit correction."""

        def has_evidence(quote: str) -> bool:
            return bool(quote) and any(quote in report for report in user_reports)

        self.detected_category = reply.detected_category
        self.stage = reply.stage
        for kind in FACT_LABELS:
            for fact in getattr(reply.new_facts, kind):
                quote = fact.quote.strip()
                if not has_evidence(quote):
                    continue
                notes = self.facts.setdefault(kind, [])
                if fact.replaces is not None and fact.replaces in notes and fact.replaces != quote:
                    notes.remove(fact.replaces)
                if quote not in notes:
                    notes.append(quote)

        self.possible_causes = list(dict.fromkeys(
            cause.hypothesis.strip()
            for cause in reply.possible_causes
            if cause.hypothesis.strip() and has_evidence(cause.evidence.strip())
        ))
        self.unresolved_questions = list(dict.fromkeys(
            question.strip() for question in reply.unresolved_questions if question.strip()
        ))
