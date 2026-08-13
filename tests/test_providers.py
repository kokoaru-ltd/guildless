import pytest

from council.config import PriceSpec, ProviderConfig
from council.providers.base import (
    ProviderUnavailable,
    classify_failure,
    estimate_cost,
    parse_json_text,
)
from council.schemas import Proposal, strict_json_schema


def test_parse_fenced_json():
    assert parse_json_text('```json\n{"ok": true}\n```') == {"ok": True}


def test_cost_uses_cache_buckets():
    config = ProviderConfig(
        "test",
        "model",
        "key",
        "https://example.invalid",
        PriceSpec(10, 20, 1, 12),
    )
    usage = {
        "input_tokens": 1_000_000,
        "cached_input_tokens": 1_000_000,
        "cache_write_tokens": 1_000_000,
        "output_tokens": 1_000_000,
    }
    assert estimate_cost(config, usage) == 43


def test_strict_schema_forbids_extra_fields():
    schema = strict_json_schema(Proposal)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "position",
        "assumptions",
        "recommendations",
        "risks",
        "rejected_options",
        "needs_external_fact",
        "confidence",
    }


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("You have hit your usage limit", "usage_limit"),
        ("Token expired; please log in", "login_expired"),
        ("ordinary warning", "stderr"),
    ],
)
def test_failure_classification(text, reason):
    assert classify_failure(text) == reason


def test_unavailable_audit_never_enables_api_fallback():
    exc = ProviderUnavailable(
        "unavailable",
        provider="codex",
        model="default",
        reason="usage_limit",
        stderr="warning",
    )
    assert exc.audit_dict("judge")["automatic_api_fallback"] is False
