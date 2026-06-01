import argparse

from chatbot_baseline import ChatbotBaseline
from src.agent.agent import ReActAgent
from src.core.openai_provider import OpenAIProvider
from src.tools import ECOMMERCE_TOOLS


TEST_CASES = [
    "I want to buy 2 iPhones using coupon WINNER and ship to Hanoi. What is the final total?",
    "Can I buy 5 MacBooks with the STUDENT coupon and ship them to Danang? Include the final cost.",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the V1 chatbot vs ReAct agent demo.")
    parser.add_argument("--limit", type=int, default=1, help="Number of test cases to run.")
    parser.add_argument("--agent-only", action="store_true", help="Skip chatbot baseline to save API quota.")
    args = parser.parse_args()

    llm = OpenAIProvider()
    chatbot = ChatbotBaseline(llm)
    agent = ReActAgent(llm=llm, tools=ECOMMERCE_TOOLS, max_steps=6)

    for index, question in enumerate(TEST_CASES[:args.limit], start=1):
        print(f"\n=== Test Case {index} ===")
        print(f"Question: {question}")

        if not args.agent_only:
            print("\n--- Chatbot Baseline ---")
            _print_result(lambda: chatbot.run(question))

        print("\n--- ReAct Agent V1 ---")
        _print_result(lambda: agent.run(question))


def _print_result(run_callable) -> None:
    try:
        print(run_callable())
    except Exception as exc:
        print("API call failed. This is usually temporary Gemini quota/high-demand, not a code error.")
        print(f"Error summary: {exc}")


if __name__ == "__main__":
    main()
