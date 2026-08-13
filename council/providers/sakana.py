from __future__ import annotations

from council.schemas import SchemaModel, strict_json_schema

from .base import BaseProvider, ProviderResult, ProviderUnavailable


def _extract_output_text(body: dict) -> str:
    parts: list[str] = []
    for item in body.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                parts.append(content.get("text", ""))
    return "".join(parts)


class SakanaProvider(BaseProvider):
    """Sakana Fugu provider using its OpenAI-compatible Responses API."""

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_model: type[SchemaModel],
        schema_name: str,
        deterministic: bool,
    ) -> ProviderResult:
        if not self.config.api_key:
            raise ProviderUnavailable(
                "Missing SAKANA_API_KEY",
                provider=self.config.name,
                model=self.config.model,
                reason="login_expired",
            )
        payload = {
            "model": self.config.model,
            "instructions": system_prompt,
            "input": user_prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": strict_json_schema(schema_model),
                }
            },
            "reasoning": {"effort": "high"},
            "max_output_tokens": 8192,
            "stream": False,
        }
        body, attempts, latency = await self._post(
            self.config.base_url + "/v1/responses",
            headers={
                "authorization": f"Bearer {self.config.api_key}",
                "content-type": "application/json",
            },
            payload=payload,
        )
        raw_text = _extract_output_text(body)
        if not raw_text:
            raise ProviderUnavailable(
                "Sakana response did not contain output_text",
                provider=self.config.name,
                model=self.config.model,
                reason="invalid_json",
                latency_ms=latency,
                attempts=attempts,
            )
        parsed = self._validate(raw_text, schema_model)

        source_usage = body.get("usage", {})
        input_details = source_usage.get("input_tokens_details", {}) or {}
        output_details = source_usage.get("output_tokens_details", {}) or {}
        cached_user = int(input_details.get("cached_tokens", 0) or 0)
        orchestration_input = int(input_details.get("orchestration_input_tokens", 0) or 0)
        cached_orchestration = int(
            input_details.get("orchestration_input_cached_tokens", 0) or 0
        )
        user_input = int(source_usage.get("input_tokens", 0) or 0)
        visible_output = int(source_usage.get("output_tokens", 0) or 0)
        orchestration_output = int(
            output_details.get("orchestration_output_tokens", 0) or 0
        )
        usage = {
            "input_tokens": max(0, user_input - cached_user)
            + max(0, orchestration_input - cached_orchestration),
            "cached_input_tokens": cached_user + cached_orchestration,
            "cache_write_tokens": 0,
            "output_tokens": visible_output + orchestration_output,
        }
        return ProviderResult(
            provider=self.config.name,
            model=self.config.model,
            response_id=body.get("id"),
            raw_text=raw_text,
            parsed=parsed,
            usage=usage,
            estimated_cost_usd=0.0,
            latency_ms=latency,
            attempts=attempts,
            billing_mode="subscription",
        )
