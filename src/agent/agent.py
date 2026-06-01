import json
import re
from typing import List, Dict, Any, Optional, Tuple
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker

class ReActAgent:
    """
    A ReAct-style Agent that follows the Thought-Action-Observation loop.
    """
    
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []

    def get_system_prompt(self) -> str:
        tool_descriptions = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools])
        return f"""
You are a careful e-commerce ReAct agent.
You can answer only after you have enough evidence from the available tools.

Available tools:
{tool_descriptions}

Rules:
- Use tools for product price, stock, discount, shipping, and arithmetic.
- For a tool call, output exactly:
Thought: short reasoning about the next needed fact.
Action: tool_name({{"arg_name": "value"}})
- Output only one Action per turn.
- Do not invent Observation lines. The system will provide observations.
- Do not output Final Answer in the same turn as an Action.
- When you know the answer, output exactly:
Final Answer: concise answer with the calculation summary.
- If a tool reports missing data, explain the limitation in the final answer.
"""

    def run(self, user_input: str) -> str:
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})

        scratchpad = f"User question: {user_input}\n"
        steps = 0

        while steps < self.max_steps:
            steps += 1
            result = self.llm.generate(scratchpad, system_prompt=self.get_system_prompt())
            content = result.get("content", "").strip()

            tracker.track_request(
                provider=result.get("provider", "unknown"),
                model=self.llm.model_name,
                usage=result.get("usage", {}),
                latency_ms=result.get("latency_ms", 0),
            )
            logger.log_event("AGENT_STEP", {"step": steps, "llm_output": content})

            action = self._parse_action(content)
            if action:
                tool_name, args = action
                observation = self._execute_tool(tool_name, args)
                logger.log_event(
                    "TOOL_CALL",
                    {"step": steps, "tool": tool_name, "args": args, "observation": observation},
                )

                scratchpad += f"\nAssistant output:\n{content}\nObservation: {observation}\n"
                continue

            final_answer = self._parse_final_answer(content)
            if final_answer:
                logger.log_event("AGENT_END", {"steps": steps, "status": "success"})
                return final_answer

            if not action:
                logger.log_event("PARSER_ERROR", {"step": steps, "output": content})
                scratchpad += (
                    f"\nAssistant output:\n{content}\n"
                    "Observation: Parser error. Use exactly Action: tool_name({\"arg\": \"value\"}) "
                    "or Final Answer: ...\n"
                )
                continue

        logger.log_event("AGENT_END", {"steps": steps, "status": "max_steps_exceeded"})
        return "I could not complete the task within the allowed reasoning steps."

    def _parse_final_answer(self, text: str) -> Optional[str]:
        match = re.search(r"Final Answer\s*:\s*(.*)", text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        return match.group(1).strip()

    def _parse_action(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        match = re.search(r"Action\s*:\s*([a-zA-Z_][\w]*)\s*\((\{[^\n]*\})\)", text, flags=re.IGNORECASE)
        if not match:
            return None

        tool_name = match.group(1).strip()
        raw_args = match.group(2).strip()
        raw_args = re.sub(r"^```(?:json)?|```$", "", raw_args, flags=re.IGNORECASE).strip()

        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            logger.log_event("JSON_PARSER_ERROR", {"tool": tool_name, "raw_args": raw_args})
            return None

        if not isinstance(args, dict):
            logger.log_event("JSON_PARSER_ERROR", {"tool": tool_name, "raw_args": raw_args})
            return None

        return tool_name, args

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        """
        Helper method to execute tools by name.
        """
        for tool in self.tools:
            if tool['name'] == tool_name:
                try:
                    result = tool["function"](**args)
                    return json.dumps(result, ensure_ascii=False)
                except TypeError as exc:
                    return json.dumps({"error": "invalid_tool_arguments", "message": str(exc)}, ensure_ascii=False)
                except Exception as exc:
                    return json.dumps({"error": "tool_execution_error", "message": str(exc)}, ensure_ascii=False)

        logger.log_event("HALLUCINATED_TOOL", {"tool": tool_name, "args": args})
        return json.dumps({"error": "tool_not_found", "tool": tool_name}, ensure_ascii=False)
