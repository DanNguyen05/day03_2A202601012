import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from chatbot_baseline import ChatbotBaseline
from src.agent.agent import ReActAgent
from src.agent.agent_v2 import ReActAgentV2
from src.core.llm_provider import LLMProvider
from src.core.openai_provider import OpenAIProvider
from src.tools import ECOMMERCE_TOOLS
from src.tools.ecommerce_tools import COUPONS, PRODUCTS, SHIPPING_RATES


ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"

MOCK_TRACE = [
    {
        "step": 1,
        "thought": "Need product price, weight, and stock.",
        "action": 'get_product_info({"item_name": "iphone"})',
        "observation": "iPhone 15 price is 799 USD, weight is 0.22 kg, stock is 8.",
    },
    {
        "step": 2,
        "thought": "Need to verify requested quantity.",
        "action": 'check_stock({"item_name": "iphone", "quantity": 2})',
        "observation": "Enough stock: requested 2, available 8.",
    },
    {
        "step": 3,
        "thought": "Need coupon discount.",
        "action": 'get_discount({"coupon_code": "WINNER"})',
        "observation": "WINNER is valid with 10% discount.",
    },
    {
        "step": 4,
        "thought": "Need package weight.",
        "action": 'calculator({"expression": "0.22*2"})',
        "observation": "Total weight is 0.44 kg.",
    },
    {
        "step": 5,
        "thought": "Need shipping cost.",
        "action": 'calc_shipping({"weight_kg": 0.44, "destination": "Hanoi"})',
        "observation": "Shipping to Hanoi is 6.88 USD.",
    },
    {
        "step": 6,
        "thought": "Need final total.",
        "action": 'calculator({"expression": "799*2*(1-0.10)+6.88"})',
        "observation": "Final total is 1445.08 USD.",
    },
]


class MockReActLLM(LLMProvider):
    def __init__(self):
        super().__init__("mock-ui")
        self.outputs = iter(
            [
                'Thought: Need product info.\nAction: get_product_info({"item_name": "iphone"})',
                'Thought: Need stock.\nAction: check_stock({"item_name": "iphone", "quantity": 2})',
                'Thought: Need discount.\nAction: get_discount({"coupon_code": "WINNER"})',
                'Thought: Need total weight.\nAction: calculator({"expression": "0.22*2"})',
                'Thought: Need shipping.\nAction: calc_shipping({"weight_kg": 0.44, "destination": "Hanoi"})',
                'Thought: Need final total.\nAction: calculator({"expression": "799*2*(1-0.10)+6.88"})',
                "Final Answer: The final total is 1445.08 USD. Stock is available for 2 iPhones.",
            ]
        )

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        return {
            "content": next(self.outputs),
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "latency_ms": 1,
            "provider": "mock",
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Iterator[str]:
        yield ""


class DemoHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/dataset":
            self._send_json(get_dataset_payload())
            return

        if self.path in {"/", "/index.html"}:
            self._serve_file(WEB_DIR / "index.html")
            return

        requested = self.path.lstrip("/")
        file_path = WEB_DIR / requested
        if file_path.exists() and file_path.is_file():
            self._serve_file(file_path)
            return

        self._send_json({"error": "not_found"}, status=404)

    def do_POST(self) -> None:
        if self.path != "/api/ask":
            self._send_json({"error": "not_found"}, status=404)
            return

        try:
            payload = self._read_json()
            question = str(payload.get("question", "")).strip()
            mode = str(payload.get("mode", "agent_v2")).strip()

            if not question:
                self._send_json({"error": "Question is required."}, status=400)
                return

            result = run_mode(mode, question)
            self._send_json(result)
        except Exception as exc:
            self._send_json(
                {
                    "error": "request_failed",
                    "message": (
                        "The model call failed. If this is a 429 or 503, Gemini quota/high-demand "
                        "is the likely cause. Use Mock Demo for an offline demonstration."
                    ),
                    "detail": str(exc),
                },
                status=500,
            )

    def _read_json(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def _serve_file(self, file_path: Path) -> None:
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        return


def run_mode(mode: str, question: str) -> Dict[str, Any]:
    if mode == "chatbot":
        return {
            "answer": ChatbotBaseline(OpenAIProvider()).run(question),
            "mode": mode,
            "trace": [
                {
                    "step": 1,
                    "thought": "Direct model response.",
                    "action": "No tool call",
                    "observation": "The chatbot baseline does not use external tools.",
                }
            ],
        }

    if mode == "agent_v1":
        return {
            "answer": ReActAgent(OpenAIProvider(), ECOMMERCE_TOOLS, max_steps=6).run(question),
            "mode": mode,
            "trace": [
                {
                    "step": 1,
                    "thought": "Live V1 trace is written to logs/ as AGENT_STEP and TOOL_CALL events.",
                    "action": "See logs/YYYY-MM-DD.log",
                    "observation": "Use Mock Demo for an always-available visual trace.",
                }
            ],
        }

    if mode == "mock":
        return {
            "answer": ReActAgentV2(MockReActLLM(), ECOMMERCE_TOOLS, max_steps=7).run(question),
            "mode": mode,
            "trace": MOCK_TRACE,
        }

    return {
        "answer": ReActAgentV2(OpenAIProvider(), ECOMMERCE_TOOLS, max_steps=7).run(question),
        "mode": mode,
        "trace": [
            {
                "step": 1,
                "thought": "Live V2 trace is written to logs/ as AGENT_V2_STEP, TOOL_CALL, and V2_RECOVERY events.",
                "action": "See logs/YYYY-MM-DD.log",
                "observation": "Use Mock Demo for quota-free trace playback.",
            }
        ],
    }


def get_dataset_payload() -> Dict[str, Any]:
    product_items = [
        {"key": key, **value}
        for key, value in sorted(PRODUCTS.items(), key=lambda item: item[0])
    ]
    return {
        "counts": {
            "products": len(PRODUCTS),
            "coupons": len(COUPONS),
            "shipping_cities": len(SHIPPING_RATES),
            "tools": len(ECOMMERCE_TOOLS),
        },
        "products": product_items[:12],
        "coupons": sorted(COUPONS.keys()),
        "shipping_cities": sorted(SHIPPING_RATES.keys()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Lab 3 web demo.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    print(f"Web demo running at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
