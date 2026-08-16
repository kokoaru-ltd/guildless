from __future__ import annotations

import json

from council.schemas import SchemaModel, gemini_response_schema

from .base import BaseProvider, ProviderResult, ProviderUnavailable


class GeminiProvider(BaseProvider):
    """Google Gemini provider via the REST :generateContent endpoint."""

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
                "Missing GEMINI_API_KEY",
                provider=self.config.name,
                model=self.config.model,
                reason="login_expired",
            )
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": gemini_response_schema(schema_model),
                "temperature": 0 if deterministic else 0.6,
            },
        }
        url = f"{self.config.base_url}/v1beta/models/{self.config.model}:generateContent"
        body, attempts, latency = await self._post(
            url,
            headers={
                "x-goog-api-key": self.config.api_key,
                "content-type": "application/json",
            },
            payload=payload,
        )
        try:
            parts = body["candidates"][0]["content"]["parts"]
        except (KeyError, TypeError, IndexError) as exc:
            raise ProviderUnavailable(
                "Gemini response did not contain candidates[0].content.parts",
                provider=self.config.name,
                model=self.config.model,
                reason="invalid_json",
                latency_ms=latency,
                attempts=attempts,
            ) from exc
        raw_text = "".join(part.get("text", "") for part in parts)
        if not raw_text:
            raise ProviderUnavailable(
                "Gemini response contained no text",
                provider=self.config.name,
                model=self.config.model,
                reason="invalid_json",
                latency_ms=latency,
                attempts=attempts,
            )
        parsed = self._validate(raw_text, schema_model)
        usage_metadata = body.get("usageMetadata") or {}
        usage = {
            "input_tokens": int(usage_metadata.get("promptTokenCount", 0) or 0),
            "cached_input_tokens": int(usage_metadata.get("cachedContentTokenCount", 0) or 0),
            "cache_write_tokens": 0,
            "output_tokens": int(usage_metadata.get("candidatesTokenCount", 0) or 0),
        }
        return ProviderResult(
            provider=self.config.name,
            model=self.config.model,
            response_id=body.get("responseId"),
            raw_text=raw_text,
            parsed=parsed,
            usage=usage,
            estimated_cost_usd=0.0,
            latency_ms=latency,
            attempts=attempts,
            billing_mode="subscription",
        )
