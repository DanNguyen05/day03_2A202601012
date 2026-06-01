import argparse

from src.agent.agent_v2 import ReActAgentV2
from src.core.openai_provider import OpenAIProvider
from src.tools import ECOMMERCE_TOOLS


TEST_CASES = [
    "I want to buy 2 iPhones using coupon WINNER and ship to Hanoi. What is the final total?",
    "Can I buy 5 MacBooks with the STUDENT coupon and ship them to Danang? Include the final cost.",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the personal V2 ReAct agent demo.")
    parser.add_argument("--limit", type=int, default=1, help="Number of test cases to run.")
    args = parser.parse_args()

    llm = OpenAIProvider()
    agent = ReActAgentV2(llm=llm, tools=ECOMMERCE_TOOLS, max_steps=7)

    for index, question in enumerate(TEST_CASES[:args.limit], start=1):
        print(f"\n=== V2 Test Case {index} ===")
        print(f"Question: {question}")
        print("\n--- ReAct Agent V2 ---")
        _print_result(lambda: agent.run(question))


def _print_result(run_callable) -> None:
    try:
        print(run_callable())
    except Exception as exc:
        print("API call failed. This is usually temporary Gemini quota/high-demand, not a code error.")
        print(f"Error summary: {exc}")


if __name__ == "__main__":
    main()
