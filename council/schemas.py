from __future__ import annotations

from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Proposal(StrictModel):
    position: str
    assumptions: list[str]
    recommendations: list[str]
    risks: list[str]
    rejected_options: list[str]
    needs_external_fact: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class Critique(StrictModel):
    supported_points: list[str]
    errors: list[str]
    missing_considerations: list[str]
    conflicts: list[str]
    revised_recommendation: str


class FinalDecision(StrictModel):
    decision: str
    consensus: list[str]
    disagreements: list[str]
    rejected_options: list[str]
    risks: list[str]
    next_action: str
    user_question: str | None
    confidence: float = Field(ge=0.0, le=1.0)


RunState = Literal[
    "queued",
    "preparing_context",
    "proposing",
    "criticizing",
    "judging",
    "completed",
    "degraded",
    "failed",
]


class CouncilRunRequest(StrictModel):
    task_type: Literal["general", "architecture", "implementation", "evaluation_design"]
    mode: Literal["fast", "local", "thorough", "benchmark"]
    question: str = Field(min_length=1, max_length=100_000)
    context: dict[str, Any]
    allowed_providers: list[Literal["claude", "deepseek", "codex", "sakana"]] = Field(
        min_length=1, max_length=4
    )

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped

    @field_validator("allowed_providers")
    @classmethod
    def providers_must_be_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("allowed_providers must not contain duplicates")
        return value


class CouncilRunAccepted(StrictModel):
    run_id: str
    status: RunState
    run_url: str
    events_url: str


class CouncilRunEvent(StrictModel):
    sequence: int
    run_id: str
    status: RunState
    occurred_at: str
    details: dict[str, Any]


ClaimType = Literal[
    "opinion",
    "inference",
    "external_evidence",
    "confirmed_fact",
]


class EvidenceClaim(StrictModel):
    claim: str
    claim_type: ClaimType
    source_urls: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class RoleProposal(StrictModel):
    role: Literal["research", "sales", "finance"]
    position: str
    hypotheses: list[str]
    recommendations: list[str]
    risks: list[str]
    evidence: list[EvidenceClaim]
    missing_information: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class CouncilCriticism(StrictModel):
    strongest_points: list[str]
    unsupported_claims: list[str]
    hidden_assumptions: list[str]
    failure_conditions: list[str]
    contradictions: list[str]
    required_tests: list[str]


class RoleRebuttal(StrictModel):
    role: Literal["research", "sales", "finance"]
    concessions: list[str]
    defended_points: list[str]
    revised_recommendations: list[str]
    remaining_unknowns: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class DecisionScore(StrictModel):
    criterion: Literal[
        "expected_impact",
        "evidence_strength",
        "cost",
        "execution_time",
        "reversibility",
        "risk",
        "strategic_fit",
    ]
    score: int = Field(ge=0, le=100)
    reason: str


class GuildlessDecision(StrictModel):
    decision: str
    decision_status: Literal["ready", "additional_research", "hold"]
    scores: list[DecisionScore] = Field(min_length=7, max_length=7)
    evidence_used: list[str]
    rejected_options: list[str]
    opposing_view: str
    unknowns: list[str]
    recommended_action: str
    review_after: str
    confidence: float = Field(ge=0.0, le=1.0)


class GitHubSelectionConstraints(StrictModel):
    license_allowlist: list[str] = Field(
        default_factory=lambda: ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"]
    )
    min_stars: int = Field(default=0, ge=0)
    max_candidates: int = Field(default=10, ge=1, le=30)
    active_within_days: int = Field(default=730, ge=1, le=3650)


class GuildlessRunRequest(StrictModel):
    goal: str = Field(min_length=1, max_length=100_000)
    github_queries: list[str] = Field(min_length=1, max_length=8)
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: GitHubSelectionConstraints = Field(default_factory=GitHubSelectionConstraints)
    allowed_providers: list[Literal["claude", "deepseek", "codex", "sakana"]] = Field(
        min_length=2, max_length=4
    )
    max_rounds: int = Field(default=3, ge=1, le=3)
    confidence_threshold: float = Field(default=0.8, ge=0.5, le=1.0)

    @field_validator("goal")
    @classmethod
    def strip_goal(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("goal must not be blank")
        return stripped

    @field_validator("github_queries")
    @classmethod
    def clean_queries(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item or len(item) > 300 for item in cleaned):
            raise ValueError("github_queries must contain non-empty values up to 300 characters")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("github_queries must not contain duplicates")
        return cleaned

    @field_validator("allowed_providers")
    @classmethod
    def guildless_providers_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("allowed_providers must not contain duplicates")
        return value


class ExecutionTestResult(StrictModel):
    command: str
    passed: bool
    summary: str


class ExecutionReport(StrictModel):
    status: Literal["completed", "partial", "blocked"]
    summary: str
    implementation_directory: str
    changed_files: list[str]
    artifacts: list[str]
    tests: list[ExecutionTestResult]
    blockers: list[str]
    approval_requests: list[str]
    next_action: str


class ImplementationFile(StrictModel):
    relative_path: str = Field(pattern=r"^output/[A-Za-z0-9_.\-/]{1,240}$")
    content: str = Field(max_length=300_000)


class ImplementationBundle(StrictModel):
    summary: str
    files: list[ImplementationFile] = Field(min_length=1, max_length=40)
    test_strategy: str
    approval_requests: list[str]


class GuildlessJobRequest(StrictModel):
    objective: str = Field(min_length=1, max_length=100_000)
    github_queries: list[str] = Field(min_length=1, max_length=8)
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: GitHubSelectionConstraints = Field(default_factory=GitHubSelectionConstraints)
    allowed_providers: list[Literal["claude", "deepseek", "codex", "sakana"]] = Field(
        min_length=2, max_length=4
    )
    workspace_label: str = Field(default="job", pattern=r"^[A-Za-z0-9_-]{1,40}$")
    max_rounds: int = Field(default=1, ge=1, le=3)
    max_execution_minutes: int = Field(default=20, ge=1, le=60)

    @field_validator("objective")
    @classmethod
    def strip_objective(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("objective must not be blank")
        return stripped

    @field_validator("github_queries")
    @classmethod
    def job_queries(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item or len(item) > 300 for item in cleaned):
            raise ValueError("github_queries must contain non-empty values up to 300 characters")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("github_queries must not contain duplicates")
        return cleaned

    @field_validator("allowed_providers")
    @classmethod
    def job_providers(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("allowed_providers must not contain duplicates")
        return value


SchemaModel = TypeVar("SchemaModel", bound=StrictModel)


def strict_json_schema(model_type: type[StrictModel]) -> dict:
    schema = model_type.model_json_schema()
    # Keep the wire schema within the conservative subset shared by provider
    # structured-output implementations. Pydantic still enforces numeric bounds
    # locally after the response is received.
    def clean(node):
        if isinstance(node, dict):
            for key in ("title", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
                node.pop(key, None)
            for value in node.values():
                clean(value)
        elif isinstance(node, list):
            for value in node:
                clean(value)

    clean(schema)
    return schema
