# Individual Report: Lab 3 - ReAct Agent V2

- **Student Name**: Nguyễn Trung Dân
- **Student ID**: 2A202601012
- **Date**: 2026-06-01
- **Personal Version**: V2 - Robust Tool Guardrails

---

## I. Technical Contribution

My V2 contribution improves the group V1 ReAct agent by adding reliability guardrails around tool calling.

### Modules Implemented

| File | Contribution |
| :--- | :--- |
| `src/agent/agent_v2.py` | Added `ReActAgentV2` with tool validation, repeated-action detection, parser cleanup, and recovery logging. |
| `run_v2_demo.py` | Added a separate runner for personal V2 evaluation. |
| `tests/test_agent_v2.py` | Added mock LLM tests for invalid tool call recovery, repeated action recovery, and hallucinated tool recovery. |

### Code Highlights

V2 adds required-argument validation before tool execution:

```python
REQUIRED_TOOL_ARGS = {
    "get_product_info": ["item_name"],
    "get_discount": ["coupon_code"],
    "check_stock": ["item_name", "quantity"],
    "calc_shipping": ["weight_kg", "destination"],
    "calculator": ["expression"],
}
```

V2 logs new debugging events:

```text
TOOL_VALIDATION_ERROR
LOOP_DETECTED
V2_RECOVERY
AGENT_V2_START
AGENT_V2_STEP
AGENT_V2_END
```

---

## II. Debugging Case Study

### Problem Description

In V1, the model could generate an invalid action such as:

```text
Action: calc_shipping({"destination": "Hanoi"})
```

This call is missing the required `weight_kg` argument. Without validation, the agent may waste steps or pass a bad call into the tool execution layer.

### Diagnosis

This is an agent-specific failure. A chatbot usually fails by hallucinating the final answer. A ReAct agent can fail through bad actions:

- wrong tool name
- missing tool argument
- repeated tool call
- invalid JSON format

The logs showed that tool-call quality is as important as answer quality.

### Solution

I implemented `ReActAgentV2` with:

- `_validate_action()` to check tool names and required arguments.
- `_is_repeated_action()` to detect repeated identical tool calls.
- `_clean_json_text()` to handle JSON wrapped in markdown code fences.
- `V2_RECOVERY` observations that tell the model how to correct the next step.

### Evidence

The V2 mock test suite passed:

```text
python -m pytest tests/test_agent_v2.py -q
4 passed
```

The test suite verifies that V2 can recover from:

- missing `weight_kg` in `calc_shipping`
- repeated `get_product_info({"item_name": "iphone"})`
- hallucinated tool `search_price`
- stock checking through `check_stock({"item_name": "macbook", "quantity": 5})`

---

## III. Personal Insights: Chatbot vs ReAct

### Reasoning

The chatbot produces a direct answer from model memory, so it often estimates prices, shipping, and discounts. The ReAct agent separates reasoning from action: it asks for product data, observes the result, then continues.

### Reliability

The ReAct agent is more reliable for multi-step tasks, but only if tool calls are valid. V1 showed that agent failures are more operational: parser errors, invalid arguments, repeated actions, and API quota errors.

### Observation

Observation is the key difference. After the agent receives tool output, its next step can be grounded in real data instead of guessed data. However, the system must prevent the model from inventing observations or repeating useless actions.

---

## IV. Future Improvements

- **Scalability**: Add provider fallback so the agent can switch models when Gemini quota is exhausted.
- **Safety**: Add strict Pydantic schemas for each tool's input.
- **Performance**: Cache repeated tool observations to reduce LLM calls and cost.
- **Evaluation**: Build an automated benchmark that scores final answers against expected totals.
- **Production Path**: Move from a simple loop to LangGraph or another state-machine framework for clearer branching and recovery.
