import json
import re
from typing import Any, Dict, List, Optional, Tuple

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker


REQUIRED_TOOL_ARGS = {
    "get_product_info": ["item_name"],
    "get_discount": ["coupon_code"],
    "check_stock": ["item_name", "quantity"],
    "calc_shipping": ["weight_kg", "destination"],
    "calculator": ["expression"],
}


class ReActAgentV2:
    """
    Personal V2 agent.

    Improvements over V1:
    - validates tool names and required arguments before execution
    - detects repeated identical tool calls
    - handles JSON fenced in markdown code blocks
    - logs explicit recovery events for the individual debugging report
    """

    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 7):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.seen_actions: Dict[str, int] = {}

    def get_system_prompt(self) -> str:
        tool_descriptions = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools])
        return f"""
You are a careful e-commerce ReAct agent with strict tool-call discipline.
You must solve tasks by using the available tools, not by guessing catalog data.

Available tools:
{tool_descriptions}

Required output format:
- If you need a tool, output exactly one action:
Thought: short reason for the next needed fact.
Action: tool_name({{"arg_name": "value"}})
- If you are done, output:
Final Answer: concise answer with calculation summary.

Rules:
- Output only one Action per turn.
- Never invent Observation lines.
- Never output Final Answer in the same turn as an Action.
- Use valid JSON inside the parentheses.
- If the system reports an invalid action, correct the next tool call.
- If the system reports a repeated action, use previous observations instead of repeating it.
"""

    def run(self, user_input: str) -> str:
        logger.log_event("AGENT_V2_START", {"input": user_input, "model": self.llm.model_name})

        self.seen_actions = {}
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
            logger.log_event("AGENT_V2_STEP", {"step": steps, "llm_output": content})

            action = self._parse_action(content)
            if action:
                tool_name, args = action

                validation_error = self._validate_action(tool_name, args)
                if validation_error:
                    logger.log_event(
                        "TOOL_VALIDATION_ERROR",
                        {"step": steps, "tool": tool_name, "args": args, "error": validation_error},
                    )
                    logger.log_event("V2_RECOVERY", {"step": steps, "reason": "invalid_action"})
                    scratchpad += (
                        f"\nAssistant output:\n{content}\n"
                        f"Observation: Invalid action. {validation_error}. "
                        "Correct the tool call using the exact tool schema.\n"
                    )
                    continue

                if self._is_repeated_action(tool_name, args):
                    logger.log_event("LOOP_DETECTED", {"step": steps, "tool": tool_name, "args": args})
                    logger.log_event("V2_RECOVERY", {"step": steps, "reason": "repeated_action"})
                    scratchpad += (
                        f"\nAssistant output:\n{content}\n"
                        "Observation: Loop detected. This exact tool call was already used. "
                        "Use prior observations to continue or give the Final Answer.\n"
                    )
                    continue

                observation = self._execute_tool(tool_name, args)
                logger.log_event(
                    "TOOL_CALL",
                    {"version": "v2", "step": steps, "tool": tool_name, "args": args, "observation": observation},
                )
                scratchpad += f"\nAssistant output:\n{content}\nObservation: {observation}\n"
                continue

            final_answer = self._parse_final_answer(content)
            if final_answer:
                logger.log_event("AGENT_V2_END", {"steps": steps, "status": "success"})
                return final_answer

            logger.log_event("PARSER_ERROR", {"version": "v2", "step": steps, "output": content})
            logger.log_event("V2_RECOVERY", {"step": steps, "reason": "parser_error"})
            scratchpad += (
                f"\nAssistant output:\n{content}\n"
                "Observation: Parser error. Use exactly Action: tool_name({\"arg\": \"value\"}) "
                "or Final Answer: ...\n"
            )

        logger.log_event("AGENT_V2_END", {"steps": steps, "status": "max_steps_exceeded"})
        return "I could not complete the task within the allowed reasoning steps."

    def _parse_final_answer(self, text: str) -> Optional[str]:
        match = re.search(r"Final Answer\s*:\s*(.*)", text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        return match.group(1).strip()

    def _parse_action(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        match = re.search(r"Action\s*:\s*([a-zA-Z_][\w]*)\s*\((.*?)\)", text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None

        tool_name = match.group(1).strip()
        raw_args = self._clean_json_text(match.group(2))

        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            logger.log_event("JSON_PARSER_ERROR", {"version": "v2", "tool": tool_name, "raw_args": raw_args})
            return None

        if not isinstance(args, dict):
            logger.log_event("JSON_PARSER_ERROR", {"version": "v2", "tool": tool_name, "raw_args": raw_args})
            return None

        return tool_name, args

    def _clean_json_text(self, raw_args: str) -> str:
        text = raw_args.strip()
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
        return text

    def _validate_action(self, tool_name: str, args: Dict[str, Any]) -> Optional[str]:
        tool_names = {tool["name"] for tool in self.tools}
        if tool_name not in tool_names:
            return f"Tool '{tool_name}' does not exist. Available tools: {sorted(tool_names)}."

        required_args = REQUIRED_TOOL_ARGS.get(tool_name, [])
        missing = [arg for arg in required_args if arg not in args or args[arg] in ("", None)]
        if missing:
            return f"Missing required argument(s) for {tool_name}: {missing}."

        return None

    def _is_repeated_action(self, tool_name: str, args: Dict[str, Any]) -> bool:
        action_key = json.dumps({"tool": tool_name, "args": args}, sort_keys=True)
        self.seen_actions[action_key] = self.seen_actions.get(action_key, 0) + 1
        return self.seen_actions[action_key] >= 2

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        for tool in self.tools:
            if tool["name"] == tool_name:
                try:
                    result = tool["function"](**args)
                    return json.dumps(result, ensure_ascii=False)
                except TypeError as exc:
                    return json.dumps({"error": "invalid_tool_arguments", "message": str(exc)}, ensure_ascii=False)
                except Exception as exc:
                    return json.dumps({"error": "tool_execution_error", "message": str(exc)}, ensure_ascii=False)

        logger.log_event("HALLUCINATED_TOOL", {"version": "v2", "tool": tool_name, "args": args})
        return json.dumps({"error": "tool_not_found", "tool": tool_name}, ensure_ascii=False)
