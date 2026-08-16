from __future__ import annotations

import json

from council.schemas import SchemaModel, strict_json_schema

from .base import BaseProvider, ProviderResult, ProviderUnavailable


class DeepSeekApiProvider(BaseProvider):
    """Hosted DeepSeek provider via the OpenAI-compatible chat/completions API.

    Distinct from DeepSeekProvider, which drives a local Ollama model. This one
    needs no local runtime, so the council still has an independent voice when
    Ollama is not running.
    """

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
                "Missing DEEPSEEK_API_KEY",
                provider=self.config.name,
                model=self.config.model,
                reason="login_expired",
            )
        schema = strict_json_schema(schema_model)
        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                    + "\nJSON Schema: "
                    + json.dumps(schema, ensure_ascii=False, sort_keys=True),
                },
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0 if deterministic else 0.6,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        body, attempts, latency = await self._post(
            self.config.base_url + "/chat/completions",
            headers={
                "authorization": f"Bearer {self.config.api_key}",
                "content-type": "application/json",
            },
            payload=payload,
        )
        try:
            raw_text = body["choices"][0]["message"]["content"]
        except (KeyError, TypeError, IndexError) as exc:
            raise ProviderUnavailable(
                "DeepSeek response did not contain choices[0].message.content",
                provider=self.config.name,
                model=self.config.model,
                reason="invalid_json",
                latency_ms=latency,
                attempts=attempts,
            ) from exc
        if not raw_text:
            raise ProviderUnavailable(
                "DeepSeek response contained no content",
                provider=self.config.name,
                model=self.config.model,
                reason="invalid_json",
                latency_ms=latency,
                attempts=attempts,
            )
        parsed = self._validate(raw_text, schema_model)
        source_usage = body.get("usage") or {}
        usage = {
            "input_tokens": int(source_usage.get("prompt_tokens", 0) or 0),
            "cached_input_tokens": int(
                (source_usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
            ),
            "cache_write_tokens": 0,
            "output_tokens": int(source_usage.get("completion_tokens", 0) or 0),
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
