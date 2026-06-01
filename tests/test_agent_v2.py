import os
import sys
from typing import Iterator, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.agent_v2 import ReActAgentV2
from src.core.llm_provider import LLMProvider
from src.tools import ECOMMERCE_TOOLS


class ScriptedLLM(LLMProvider):
    def __init__(self, outputs):
        super().__init__("scripted-test")
        self.outputs = iter(outputs)

    def generate(self, prompt: str, system_prompt: Optional[str] = None):
        return {
            "content": next(self.outputs),
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "latency_ms": 1,
            "provider": "test",
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Iterator[str]:
        yield ""


def test_v2_recovers_from_missing_tool_argument():
    llm = ScriptedLLM(
        [
            'Thought: Need shipping.\nAction: calc_shipping({"destination": "Hanoi"})',
            'Thought: Correcting missing weight.\nAction: calc_shipping({"weight_kg": 0.44, "destination": "Hanoi"})',
            "Final Answer: Shipping is 6.88 USD after correcting the invalid action.",
        ]
    )
    agent = ReActAgentV2(llm, ECOMMERCE_TOOLS, max_steps=3)

    answer = agent.run("Ship 2 iPhones to Hanoi.")

    assert "6.88" in answer


def test_v2_detects_repeated_action_and_recovers():
    llm = ScriptedLLM(
        [
            'Thought: Need product info.\nAction: get_product_info({"item_name": "iphone"})',
            'Thought: Need product info again.\nAction: get_product_info({"item_name": "iphone"})',
            "Final Answer: The previous observation already gave the iPhone price as 799 USD.",
        ]
    )
    agent = ReActAgentV2(llm, ECOMMERCE_TOOLS, max_steps=3)

    answer = agent.run("What is the iPhone price?")

    assert "799" in answer


def test_v2_recovers_from_unknown_tool():
    llm = ScriptedLLM(
        [
            'Thought: Need price.\nAction: search_price({"item_name": "iphone"})',
            'Thought: Use the available catalog tool.\nAction: get_product_info({"item_name": "iphone"})',
            "Final Answer: The iPhone price is 799 USD.",
        ]
    )
    agent = ReActAgentV2(llm, ECOMMERCE_TOOLS, max_steps=3)

    answer = agent.run("What is the iPhone price?")

    assert "799" in answer


def test_v2_uses_check_stock_tool():
    llm = ScriptedLLM(
        [
            'Thought: Need to verify stock first.\nAction: check_stock({"item_name": "macbook", "quantity": 5})',
            "Final Answer: The order cannot be fulfilled because only 4 MacBooks are in stock.",
        ]
    )
    agent = ReActAgentV2(llm, ECOMMERCE_TOOLS, max_steps=2)

    answer = agent.run("Can I buy 5 MacBooks?")

    assert "only 4" in answer
