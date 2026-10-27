from datetime import datetime, timedelta, timezone
from fastapi import FastAPI
from typing import Any
import random


app = FastAPI(title="Mock Orders API", version="2.0")

original_fields = {
    "order_id": {
        "type": "integer",
        "names": ["orderId", "OrderID", "orderID", "order_number", "order_key", "id_order", "purchase_id", "transaction_id", "id"],
        "types": ["string", "float"],
        "recipe": {"kind": "sequence", "start": 100000},
    },
    "store_id": {
        "type": "integer",
        "names": ["storeId", "StoreID", "storeID", "shop_id", "branch_id", "location_id", "store_number", "id_store", "retail_id"],
        "types": ["string", "float"],
        "recipe": {"kind": "integer", "min": 1, "max": 30},
    },
    "customer_id": {
        "type": "integer",
        "names": ["customerId", "CustomerID", "customerID", "client_id", "user_id", "buyer_id", "customer_number", "id_customer", "account_id"],
        "types": ["string", "float"],
        "recipe": {"kind": "integer", "min": 1000, "max": 99999},
    },
    "product_id": {
        "type": "integer",
        "names": ["productId", "ProductID", "productID", "item_id", "sku", "article_id", "product_code", "id_product", "inventory_id"],
        "types": ["string", "float"],
        "recipe": {"kind": "integer", "min": 100, "max": 999},
    },
    "quantity": {
        "type": "integer",
        "names": ["qty", "Quantity", "order_quantity", "item_quantity", "units", "units_sold", "amount", "count", "total_units"],
        "types": ["float", "string"],
        "recipe": {"kind": "integer", "min": 1, "max": 10},
    },
    "price": {
        "type": "float",
        "names": ["Price", "unit_price", "item_price", "sale_price", "product_price", "cost", "amount", "unit_cost", "price_usd"],
        "types": ["integer", "string"],
        "recipe": {"kind": "decimal", "min": 5.0, "max": 500.0, "digits": 2},
    },
    "payment_method": {
        "type": "string",
        "names": ["paymentMethod", "PaymentMethod", "payment_type", "payment_mode", "pay_method", "payment_channel", "method_of_payment", "payment_option", "tender_type"],
        "types": ["integer"],
        "recipe": {"kind": "choice", "values": ["card", "cash", "bank_transfer", "wallet"]},
    },
    "status": {
        "type": "string",
        "names": ["Status", "order_status", "payment_status", "transaction_status", "state", "order_state", "status_code", "current_status", "processing_status"],
        "types": ["integer", "boolean"],
        "recipe": {"kind": "choice", "values": ["pending", "paid", "shipped", "delivered", "cancelled", "refunded"]},
    },
    "created_at": {
        "type": "timestamp",
        "names": ["createdAt", "CreatedAt", "creation_date", "created_date", "order_date", "order_timestamp", "timestamp", "date_created", "created_on", "transaction_date"],
        "types": ["integer"],
        "recipe": {"kind": "datetime", "days_back": 365},
    },
}

new_fields = {
    "discount": {
        "type": "float",
        "names": ["Discount", "discount_amount", "discount_value", "discount_rate", "discount_pct", "discount_percentage", "promo_discount", "rebate", "price_reduction"],
        "types": ["integer", "string"],
        "recipe": {"kind": "decimal", "min": 0.0, "max": 20.0, "digits": 2},
    },
    "shipping_address": {
        "type": "string",
        "names": ["shippingAddress", "ShippingAddress", "delivery_address", "ship_to", "address", "destination_address", "shipping_location", "recipient_address", "delivery_location"],
        "types": ["json"],
        "recipe": {"kind": "choice", "values": ["12 Main St, Springfield", "84 Oak Ave, Denver", "42 Pine Rd, Austin", "19 Market St, Seattle"]},
    },
    "is_refunded": {
        "type": "boolean",
        "names": ["isRefunded", "IsRefunded", "refunded", "refund_status", "has_refund", "was_refunded", "is_returned", "refund_flag", "refunded_flag"],
        "types": ["integer", "string"],
        "recipe": {"kind": "derived", "field": "status", "equals": "refunded"},
    },
    "updated_at": {
        "type": "timestamp",
        "names": ["updatedAt", "UpdatedAt", "modified_at", "last_updated", "last_modified", "update_timestamp", "modification_date", "updated_on", "last_update_date"],
        "types": ["integer"],
        "recipe": {"kind": "after", "field": "created_at", "max_days": 14},
    },
}

def make_variation(schema: dict[str, dict[str, str]], rng: random.Random, probability: float = 0.15) -> dict[str, dict[str, str]]:
    """Rename, retype, or omit fields without colliding with existing names."""
    result = {}
    used_names = {item["name"] for item in schema.values()}
    specs = original_fields | new_fields
    for canonical, field in schema.items():
        updated = field.copy()
        if rng.random() < probability:
            spec = specs[canonical]
            action = rng.choice(("rename", "type", "missing"))
            if action == "missing":
                continue
            if action == "rename":
                choices = [name for name in spec["names"] if name not in used_names]
                if choices:
                    name = rng.choice(choices)
                    used_names.discard(updated["name"])
                    used_names.add(name)
                    updated["name"] = name
            else:
                updated["type"] = rng.choice(spec["types"])
        result[canonical] = updated
    return result


def make_new_column(schema: dict[str, dict[str, str]], rng: random.Random, probability: float = 0.05) -> dict[str, dict[str, str]]:
    """Add at most one new field, retaining all existing fields."""
    available = [name for name in new_fields if name not in schema]
    if not available or rng.random() >= probability:
        return schema
    name = rng.choice(available)
    return schema | {name: {"name": name, "type": new_fields[name]["type"]}}


def make_value(recipe: dict[str, Any], context: dict[str, Any], index: int, rng: random.Random, now: datetime) -> Any:
    kind = recipe["kind"]
    if kind == "sequence":
        return recipe["start"] + index
    if kind == "integer":
        return rng.randint(recipe["min"], recipe["max"])
    if kind == "decimal":
        return round(rng.uniform(recipe["min"], recipe["max"]), recipe["digits"])
    if kind == "choice":
        return rng.choice(recipe["values"])
    if kind == "datetime":
        return now - timedelta(seconds=rng.randint(0, recipe["days_back"] * 86400))
    if kind == "derived":
        return context[recipe["field"]] == recipe["equals"]
    if kind == "after":
        base = context[recipe["field"]]
        seconds = min(int((now - base).total_seconds()), recipe["max_days"] * 86400)
        return base + timedelta(seconds=rng.randint(0, max(0, seconds)))
    raise ValueError(f"Unknown recipe kind: {kind}")


def cast_value(value: Any, dtype: str, recipe: dict[str, Any]) -> Any:
    """Convert values to JSON-safe representations matching the mock dtype."""
    if isinstance(value, datetime) and dtype in {"timestamp", "string"}:
        return value.isoformat()
    if dtype == "integer":
        if isinstance(value, datetime):
            value = value.timestamp()
        elif recipe["kind"] == "choice":
            value = recipe["values"].index(value)
    if dtype == "boolean" and recipe["kind"] == "choice":
        value = value == "refunded"
    if dtype == "json":
        return {"address": value}
    if dtype == "string" and isinstance(value, bool):
        value = str(value).lower()
    return {"integer": int, "float": float, "boolean": bool, "string": str}[dtype](value)


def generate_payload(rows: int = 10, drift: bool | None = None, seed: int | None = None, extra_column_probability: float = 0.2) -> dict[str, Any]:
    """Randomize each request; an explicit seed replays the same payload."""
    if rows < 1:
        raise ValueError("rows must be positive")
    seed = random.getrandbits(64) if seed is None else seed
    rng = random.Random(seed)
    drift = rng.random() < 0.1 if drift is None else drift
    now = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
    baseline = {name: {"name": name, "type": spec["type"]} for name, spec in original_fields.items()}
    schema = baseline
    if drift:
        schema = make_new_column(schema, rng, extra_column_probability)
        schema = make_variation(schema, rng)

    specs = original_fields | new_fields
    output = []
    for index in range(rows):
        canonical = {}
        # Generate dependencies before omitting or renaming their output fields.
        for name, spec in specs.items():
            canonical[name] = make_value(spec["recipe"], canonical, index, rng, now)
        output.append({field["name"]: cast_value(canonical[name], field["type"], specs[name]["recipe"])
                       for name, field in schema.items()})

    row_drift = drift and bool(schema) and rng.random() < 0.3
    if row_drift:
        row = rng.choice(output)
        name = rng.choice(list(row))
        if rng.random() < 1 / 3:
            row.pop(name)
        else:
            different_type = 0 if isinstance(row[name], str) else str(row[name])
            row[name] = rng.choice((None, different_type))

    return {
        "metadata": {"count": len(output), "seed": seed, "drift": schema != baseline or bool(row_drift)},
        "data": output,
    }


@app.get("/")
def get_orders() -> dict[str, Any]:
    return generate_payload()
