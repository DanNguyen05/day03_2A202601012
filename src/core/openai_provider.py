import os
import time
from typing import Dict, Any, Optional, Generator
from dotenv import load_dotenv
from openai import APIStatusError, OpenAI
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger

class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 2,
    ):
        load_dotenv()
        model_name = model_name or os.getenv("MODEL") or os.getenv("DEFAULT_MODEL") or "gpt-4o"
        api_key = api_key or os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = base_url or os.getenv("LLM_ENDPOINT") or None

        super().__init__(model_name, api_key)
        self.client = OpenAI(api_key=self.api_key, base_url=base_url)
        self.max_retries = max_retries

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                )
                break
            except APIStatusError as exc:
                status_code = getattr(exc, "status_code", None)
                should_retry = status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries
                logger.log_event(
                    "LLM_API_ERROR",
                    {
                        "model": self.model_name,
                        "status_code": status_code,
                        "attempt": attempt + 1,
                        "will_retry": should_retry,
                    },
                )
                if not should_retry:
                    raise
                time.sleep(2 * (attempt + 1))

        if response is None:
            raise RuntimeError("LLM request failed before receiving a response.")

        end_time = time.time()
        latency_ms = int((end_time - start_time) * 1000)

        # Extraction from OpenAI response
        content = response.choices[0].message.content
        usage_data = response.usage
        usage = {
            "prompt_tokens": getattr(usage_data, "prompt_tokens", 0),
            "completion_tokens": getattr(usage_data, "completion_tokens", 0),
            "total_tokens": getattr(usage_data, "total_tokens", 0)
        }

        return {
            "content": content,
            "usage": usage,
            "latency_ms": latency_ms,
            "provider": "openai"
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=True
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
