from __future__ import annotations

import json

from council.schemas import SchemaModel, strict_json_schema

from .base import BaseProvider, ProviderResult, ProviderUnavailable


class DeepSeekProvider(BaseProvider):
    """Local deepseek-r1 provider through Ollama's localhost chat API."""

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_model: type[SchemaModel],
        schema_name: str,
        deterministic: bool,
    ) -> ProviderResult:
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
            "format": schema,
            "stream": False,
            "options": {"temperature": 0 if deterministic else 0.6},
        }
        body, attempts, latency = await self._post(
            self.config.base_url + "/api/chat",
            headers={"content-type": "application/json"},
            payload=payload,
        )
        try:
            raw_text = body["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ProviderUnavailable(
                "Ollama response did not contain message.content",
                provider=self.config.name,
                model=self.config.model,
                reason="invalid_json",
                latency_ms=latency,
                attempts=attempts,
            ) from exc
        parsed = self._validate(raw_text, schema_model)
        usage = {
            "input_tokens": int(body.get("prompt_eval_count", 0) or 0),
            "cached_input_tokens": 0,
            "cache_write_tokens": 0,
            "output_tokens": int(body.get("eval_count", 0) or 0),
        }
        return ProviderResult(
            provider=self.config.name,
            model=str(body.get("model", self.config.model)),
            response_id=None,
            raw_text=raw_text,
            parsed=parsed,
            usage=usage,
            estimated_cost_usd=0.0,
            latency_ms=latency,
            attempts=attempts,
            billing_mode="local",
            exit_code=None,
            stderr="",
        )
