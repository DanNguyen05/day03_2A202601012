from src.core.openai_provider import OpenAIProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker


BASELINE_SYSTEM_PROMPT = """
You are a helpful e-commerce chatbot.
Answer directly from your general knowledge.
Do not use tools.
If exact catalog data is unavailable, make your best estimate and say it is an estimate.
"""


class ChatbotBaseline:
    def __init__(self, llm: OpenAIProvider):
        self.llm = llm

    def run(self, user_input: str) -> str:
        logger.log_event("CHATBOT_START", {"input": user_input, "model": self.llm.model_name})
        result = self.llm.generate(user_input, system_prompt=BASELINE_SYSTEM_PROMPT)
        tracker.track_request(
            provider=result.get("provider", "unknown"),
            model=self.llm.model_name,
            usage=result.get("usage", {}),
            latency_ms=result.get("latency_ms", 0),
        )
        content = result.get("content", "").strip()
        logger.log_event("CHATBOT_END", {"output": content})
        return content
