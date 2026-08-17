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


class ExperimentDesign(StrictModel):
    """The executable half of a business decision.

    A council that stops at prose cannot be acted on or scored. Every business
    decision must land here: one falsifiable hypothesis, the exact contact set,
    the money at stake, and the conditions that end the experiment either way.

    ``next_review_hours`` is relative on purpose. Models cannot reliably produce
    a correct absolute timestamp; the engine stamps the real clock time.
    """

    hypothesis: str = Field(min_length=1)
    target_customer: str = Field(min_length=1)
    offer: str = Field(min_length=1)
    price_yen: int = Field(ge=0)
    channel: Literal["email", "phone", "dm", "form", "ads"]
    sample_size: int = Field(ge=1, le=10_000)
    max_budget_yen: int = Field(ge=0)
    success_condition: str = Field(min_length=1)
    failure_condition: str = Field(min_length=1)
    next_review_hours: int = Field(ge=1, le=8_760)


class FinalDecision(StrictModel):
    decision: str
    consensus: list[str]
    disagreements: list[str]
    rejected_options: list[str]
    risks: list[str]
    # Evidence and unknowns are separated from assumptions so a later scoring
    # pass can tell "we were wrong" apart from "we never knew".
    evidence: list[str]
    assumptions: list[str]
    unknowns: list[str]
    next_action: str
    # Null only for non-business questions. The business path rejects null.
    experiment: ExperimentDesign | None
    user_question: str | None
    confidence: float = Field(ge=0.0, le=1.0)


class CheckoutCreateRequest(StrictModel):
    offer_id: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=300)
    amount_yen: int = Field(ge=50, le=1_000_000)
    customer_ref: str = Field(min_length=1, max_length=200)
    experiment_id: str = Field(default="", max_length=100)
    decision_id: str = Field(default="", max_length=100)


class DecisionOutcomeRequest(StrictModel):
    """Counted results of an experiment. Never estimates, only observations."""

    contacted: int = Field(ge=0, default=0)
    replied: int = Field(ge=0, default=0)
    meetings: int = Field(ge=0, default=0)
    orders: int = Field(ge=0, default=0)
    revenue_yen: int = Field(ge=0, default=0)
    cost_yen: int = Field(ge=0, default=0)


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
    mode: Literal["fast", "local", "real", "thorough", "benchmark"]
    question: str = Field(min_length=1, max_length=100_000)
    context: dict[str, Any]
    allowed_providers: list[Literal["claude", "deepseek", "deepseek_api", "codex", "sakana", "gemini", "glm"]] = Field(
        min_length=1, max_length=6
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


class SalesLeadScoreRequest(StrictModel):
    company: str = Field(min_length=1, max_length=500)
    budget_signals: dict[str, Any] = Field(default_factory=dict)
    authority_signals: dict[str, Any] = Field(default_factory=dict)
    need_signals: dict[str, Any] = Field(default_factory=dict)
    timeline_signals: dict[str, Any] = Field(default_factory=dict)


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
    allowed_providers: list[Literal["claude", "deepseek", "deepseek_api", "codex", "sakana", "gemini", "glm"]] = Field(
        min_length=2, max_length=6
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
    files: list[ImplementationFile] = Field(min_length=1, max_length=60)
    test_strategy: str
    approval_requests: list[str]


class GuildlessJobRequest(StrictModel):
    objective: str = Field(min_length=1, max_length=100_000)
    github_queries: list[str] = Field(min_length=1, max_length=8)
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: GitHubSelectionConstraints = Field(default_factory=GitHubSelectionConstraints)
    allowed_providers: list[Literal["claude", "deepseek", "deepseek_api", "codex", "sakana", "gemini", "glm"]] = Field(
        min_length=2, max_length=6
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


def gemini_response_schema(model_type: type[StrictModel]) -> dict:
    """The same schema narrowed to the subset Gemini's responseSchema accepts.

    Gemini takes a restricted OpenAPI 3.0 dialect, not full JSON Schema. It
    rejects ``additionalProperties`` outright with HTTP 400, and expresses
    optional fields as ``nullable`` rather than an ``anyOf`` with null. It also
    cannot follow ``$ref``, so definitions are inlined.
    """
    schema = strict_json_schema(model_type)
    definitions = schema.pop("$defs", {})

    def convert(node):
        if isinstance(node, list):
            return [convert(item) for item in node]
        if not isinstance(node, dict):
            return node

        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            target = definitions.get(ref.split("/")[-1], {})
            merged = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
            return convert(merged)

        # "X | None" arrives as anyOf[X, null]. Gemini wants the real branch
        # marked nullable instead.
        options = node.get("anyOf") or node.get("oneOf")
        if isinstance(options, list):
            concrete = [item for item in options if item.get("type") != "null"]
            nullable = len(concrete) != len(options)
            if len(concrete) == 1:
                converted = convert(concrete[0])
                if nullable:
                    converted["nullable"] = True
                for key, value in node.items():
                    if key not in ("anyOf", "oneOf"):
                        converted.setdefault(key, convert(value))
                return converted

        result = {}
        for key, value in node.items():
            if key == "additionalProperties":
                continue
            result[key] = convert(value)
        return result

    return convert(schema)


class V0StartRequest(StrictModel):
    intent: str = Field(min_length=1, max_length=1000)
    budget_yen: int = Field(default=30_000, ge=1000, le=100_000)
    deadline_days: int = Field(default=14, ge=1, le=90)

    @field_validator("intent")
    @classmethod
    def strip_intent(cls, value: str) -> str:
        return value.strip()


class V0LoopIdRequest(StrictModel):
    loop_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")


class V0SelectRequest(StrictModel):
    loop_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    candidate_id: str = Field(min_length=1, max_length=80)


class V0DailyConfirmRequest(StrictModel):
    loop_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    note: str = Field(default="", max_length=300)


class V0OrderRequest(StrictModel):
    loop_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    company: str = Field(min_length=1, max_length=200)
    amount_yen: int = Field(ge=100, le=10_000_000)


class V0DeliverRequest(StrictModel):
    loop_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    order_id: str = Field(min_length=1, max_length=64)


class V0KillRequest(StrictModel):
    loop_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    reason: str = Field(default="", max_length=500)


class V0GotoRequest(StrictModel):
    loop_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    stage: str = Field(min_length=1, max_length=20)


class V0ResolveCapabilityRequest(StrictModel):
    loop_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    name: str = Field(min_length=1, max_length=200)
    source: str = Field(default="", max_length=240)


class RevenueAnalyzeRequest(StrictModel):
    product: str = Field(min_length=1, max_length=200)
    price_yen: int = Field(ge=300, le=10_000_000)
    target_revenue_yen: int | None = Field(default=None, ge=300, le=100_000_000)
    budget_yen: int = Field(default=30_000, ge=1_000, le=1_000_000)
    deadline_days: int = Field(default=14, ge=1, le=90)
    region: str = Field(default="", max_length=100)
    industry: str = Field(default="", max_length=100)

    @field_validator("product")
    @classmethod
    def strip_product(cls, value: str) -> str:
        return value.strip()


class RevenueScoutRequest(StrictModel):
    plan_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")


class AskAnswer(StrictModel):
    """What a model is allowed to return when asked about the run.

    One field. A shape with room for actions, next steps, or recommendations is
    an invitation to produce them, and this channel does not act.
    """

    answer: str = Field(max_length=600)


class AskRequest(StrictModel):
    """A question about a run in flight. Read-only by construction.

    Carries no run id and no target field on purpose: there is one run, and
    nothing here may name a thing to change. A request body that could address
    part of the run would be the beginning of a control channel.
    """

    question: str = Field(min_length=1, max_length=500)


class SparkRequest(StrictModel):
    """The only required input: a thought, and optionally what is already owned."""

    statement: str = Field(default="", max_length=2_000)
    available_resources: list[str] = Field(default_factory=list, max_length=20)
    capital_yen: int = Field(default=0, ge=0, le=100_000_000)
    deadline_days: int = Field(default=7, ge=1, le=365)
    max_loss_yen: int = Field(default=0, ge=0, le=100_000_000)
