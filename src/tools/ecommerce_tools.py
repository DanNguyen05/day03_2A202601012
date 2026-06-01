import ast
import json
import operator
from pathlib import Path
from typing import Any, Dict, List


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"

PRODUCTS = json.loads((DATA_DIR / "products.json").read_text(encoding="utf-8"))
COUPONS = json.loads((DATA_DIR / "coupons.json").read_text(encoding="utf-8"))
SHIPPING_RATES = json.loads((DATA_DIR / "shipping_rates.json").read_text(encoding="utf-8"))

ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
}


def get_product_info(item_name: str) -> Dict[str, Any]:
    """Return price, stock, and weight for a supported product."""
    key = _normalize_product_key(item_name)
    if key not in PRODUCTS:
        return {"found": False, "message": f"Product '{item_name}' is not in the catalog."}
    return {"found": True, "item_name": key, **PRODUCTS[key]}


def get_discount(coupon_code: str) -> Dict[str, Any]:
    """Return discount percent for a coupon code."""
    code = coupon_code.strip().upper()
    coupon = COUPONS.get(code)
    if not coupon:
        return {"valid": False, "coupon_code": code, "percent": 0, "message": "Unknown coupon code."}
    return {"coupon_code": code, **coupon}


def check_stock(item_name: str, quantity: int) -> Dict[str, Any]:
    """Check whether the requested quantity is available."""
    product = get_product_info(item_name)
    requested = int(quantity)

    if not product.get("found"):
        return {
            "available": False,
            "item_name": item_name,
            "requested": requested,
            "stock": 0,
            "message": product.get("message", "Product was not found."),
        }

    stock = int(product["stock"])
    available = stock >= requested
    return {
        "available": available,
        "item_name": product["item_name"],
        "requested": requested,
        "stock": stock,
        "message": (
            f"Enough stock: requested {requested}, available {stock}."
            if available
            else f"Not enough stock: requested {requested}, available {stock}."
        ),
    }


def calc_shipping(weight_kg: float, destination: str) -> Dict[str, Any]:
    """Calculate shipping cost from total package weight and destination city."""
    city = destination.strip().lower()
    rate = SHIPPING_RATES.get(city)
    if not rate:
        return {"supported": False, "destination": destination, "shipping_usd": None}

    shipping = rate["base_usd"] + (float(weight_kg) * rate["per_kg_usd"])
    return {
        "supported": True,
        "destination": destination,
        "weight_kg": float(weight_kg),
        "shipping_usd": round(shipping, 2),
    }


def calculator(expression: str) -> Dict[str, Any]:
    """Safely evaluate a simple arithmetic expression."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_math_node(tree.body)
        return {"expression": expression, "result": round(float(result), 2)}
    except Exception as exc:
        return {"expression": expression, "error": str(exc)}


def _eval_math_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_OPERATORS:
        return ALLOWED_OPERATORS[type(node.op)](_eval_math_node(node.left), _eval_math_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_OPERATORS:
        return ALLOWED_OPERATORS[type(node.op)](_eval_math_node(node.operand))
    raise ValueError("Only simple arithmetic expressions are allowed.")


def _normalize_product_key(item_name: str) -> str:
    return item_name.strip().lower().replace("-", "_").replace(" ", "_")


ECOMMERCE_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "get_product_info",
        "description": (
            "Get product price_usd, weight_kg, and stock. "
            "Input JSON: {\"item_name\": \"iphone|airpods|macbook|external_ssd|...\"}."
        ),
        "function": get_product_info,
    },
    {
        "name": "get_discount",
        "description": (
            "Check a coupon and return its discount percent. "
            "Input JSON: {\"coupon_code\": \"WINNER|STUDENT|WELCOME|VIP|EXPIRED\"}."
        ),
        "function": get_discount,
    },
    {
        "name": "check_stock",
        "description": (
            "Check if requested quantity is available before purchase. "
            "Input JSON: {\"item_name\": \"iphone|airpods|macbook|external_ssd|...\", \"quantity\": number}."
        ),
        "function": check_stock,
    },
    {
        "name": "calc_shipping",
        "description": (
            "Calculate shipping cost. "
            "Input JSON: {\"weight_kg\": number, \"destination\": \"Hanoi|Ho Chi Minh|Danang|Hue|Can Tho\"}."
        ),
        "function": calc_shipping,
    },
    {
        "name": "calculator",
        "description": (
            "Evaluate simple arithmetic for totals, discounts, and taxes. "
            "Input JSON: {\"expression\": \"799*2*0.9+6.88\"}."
        ),
        "function": calculator,
    },
]
