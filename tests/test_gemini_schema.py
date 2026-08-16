import json

from council.schemas import FinalDecision, Proposal, gemini_response_schema, strict_json_schema


def test_additional_properties_is_removed():
    """Gemini rejects the whole request with HTTP 400 if this survives."""
    assert "additionalProperties" in json.dumps(strict_json_schema(FinalDecision))
    assert "additionalProperties" not in json.dumps(gemini_response_schema(FinalDecision))


def test_refs_are_inlined_because_gemini_cannot_follow_them():
    narrowed = gemini_response_schema(FinalDecision)
    assert "$ref" not in json.dumps(narrowed)
    assert "$defs" not in narrowed


def test_optional_field_becomes_nullable_not_anyof():
    experiment = gemini_response_schema(FinalDecision)["properties"]["experiment"]
    assert experiment.get("nullable") is True
    assert "anyOf" not in experiment
    assert experiment["type"] == "object"


def test_nested_experiment_fields_survive():
    experiment = gemini_response_schema(FinalDecision)["properties"]["experiment"]
    for field in ("hypothesis", "price_yen", "sample_size", "success_condition"):
        assert field in experiment["properties"]


def test_plain_schema_is_still_usable():
    narrowed = gemini_response_schema(Proposal)
    assert narrowed["type"] == "object"
    assert "position" in narrowed["properties"]
