from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Query
from typing import Any
import random


app = FastAPI(title="Mock Orders API", version="2.0")

original_fields = {
    "order_id": {
        "type": "integer",
        "names": ["orderId", "OrderID", "orderID", "order_number", "order_key", "id_order", "purchase_id", "transaction_id", "id"],
        "types": ["integer", "int", "int32", "int64", "bigint", "string", "varchar", "float"],
        "recipe": {"kind": "sequence", "start": 100000},
    },
    "store_id": {
        "type": "integer",
        "names": ["storeId", "StoreID", "storeID", "shop_id", "branch_id", "location_id", "store_number", "id_store", "retail_id"],
        "types": ["integer", "int", "int32", "int64", "bigint", "string", "varchar", "float"],
        "recipe": {"kind": "integer", "min": 1, "max": 30},
    },
    "customer_id": {
        "type": "integer",
        "names": ["customerId", "CustomerID", "customerID", "client_id", "user_id", "buyer_id", "customer_number", "id_customer", "account_id"],
        "types": ["integer", "int", "int32", "int64", "bigint", "string", "varchar", "float"],
        "recipe": {"kind": "integer", "min": 1000, "max": 99999},
    },
    "product_id": {
        "type": "integer",
        "names": ["productId", "ProductID", "productID", "item_id", "sku", "article_id", "product_code", "id_product", "inventory_id"],
        "types": ["integer", "int", "int32", "int64", "bigint", "string", "varchar", "float"],
        "recipe": {"kind": "integer", "min": 100, "max": 999},
    },
    "quantity": {
        "type": "integer",
        "names": ["qty", "Quantity", "order_quantity", "item_quantity", "units", "units_sold", "amount", "count", "total_units"],
        "types": ["integer", "int", "int32", "int64", "bigint", "float", "double", "decimal", "string"],
        "recipe": {"kind": "integer", "min": 1, "max": 10},
    },
    "price": {
        "type": "float",
        "names": ["Price", "unit_price", "item_price", "sale_price", "product_price", "cost", "amount", "unit_cost", "price_usd"],
        "types": ["float", "float32", "float64", "double", "decimal", "numeric", "integer", "string"],
        "recipe": {"kind": "decimal", "min": 5.0, "max": 500.0, "digits": 2},
    },
    "payment_method": {
        "type": "string",
        "names": ["paymentMethod", "PaymentMethod", "payment_type", "payment_mode", "pay_method", "payment_channel", "method_of_payment", "payment_option", "tender_type"],
        "types": ["string", "str", "varchar", "text", "char", "enum", "integer", "category"],
        "recipe": {"kind": "choice", "values": ["card", "cash", "bank_transfer", "wallet"]},
    },
    "status": {
        "type": "string",
        "names": ["Status", "order_status", "payment_status", "transaction_status", "state", "order_state", "status_code", "current_status", "processing_status"],
        "types": ["string", "str", "varchar", "text", "enum", "integer", "boolean", "category"],
        "recipe": {"kind": "choice", "values": ["pending", "paid", "shipped", "delivered", "cancelled", "refunded"]},
    },
    "created_at": {
        "type": "timestamp",
        "names": ["createdAt", "CreatedAt", "creation_date", "created_date", "order_date", "order_timestamp", "timestamp", "date_created", "created_on", "transaction_date"],
        "types": ["timestamp", "datetime", "datetime64", "date", "string", "varchar", "integer", "bigint", "timestamptz"],
        "recipe": {"kind": "datetime", "days_back": 365},
    },
}

new_fields = {
    "discount": {
        "type": "float",
        "names": ["Discount", "discount_amount", "discount_value", "discount_rate", "discount_pct", "discount_percentage", "promo_discount", "rebate", "price_reduction"],
        "types": ["float", "float32", "float64", "double", "decimal", "numeric", "integer", "string"],
        "recipe": {"kind": "decimal", "min": 0.0, "max": 20.0, "digits": 2},
    },
    "shipping_address": {
        "type": "string",
        "names": ["shippingAddress", "ShippingAddress", "delivery_address", "ship_to", "address", "destination_address", "shipping_location", "recipient_address", "delivery_location"],
        "types": ["string", "str", "varchar", "text", "char", "json", "jsonb", "category"],
        "recipe": {"kind": "choice", "values": ["12 Main St, Springfield", "84 Oak Ave, Denver", "42 Pine Rd, Austin", "19 Market St, Seattle"]},
    },
    "is_refunded": {
        "type": "boolean",
        "names": ["isRefunded", "IsRefunded", "refunded", "refund_status", "has_refund", "was_refunded", "is_returned", "refund_flag", "refunded_flag"],
        "types": ["boolean", "bool", "integer", "int", "tinyint", "string", "varchar", "bit"],
        "recipe": {"kind": "derived", "field": "status", "equals": "refunded"},
    },
    "updated_at": {
        "type": "timestamp",
        "names": ["updatedAt", "UpdatedAt", "modified_at", "last_updated", "last_modified", "update_timestamp", "modification_date", "updated_on", "last_update_date"],
        "types": ["timestamp", "datetime", "datetime64", "date", "string", "varchar", "integer", "bigint", "timestamptz"],
        "recipe": {"kind": "after", "field": "created_at", "max_days": 14},
    },
}

original_schema = {name: spec["type"] for name, spec in original_fields.items()}
new_schema = {name: spec["type"] for name, spec in new_fields.items()}
variations = {name: {"names": spec["names"], "types": spec["types"], "recipe": spec["recipe"]} for name, spec in original_fields.items()}
new_variations = {name: {"names": spec["names"], "types": spec["types"], "recipe": spec["recipe"]} for name, spec in new_fields.items()}


def make_variation(schema: dict[str, dict[str, str]], rng: random.Random, probability: float = 0.15) -> dict[str, dict[str, str]]:
    """Alter a field's name OR type; canonical identities never get lost."""
    result = {}
    used_names = {item["name"] for item in schema.values()}
    specs = original_fields | new_fields
    for canonical, field in schema.items():
        updated = field.copy()
        if rng.random() < probability:
            spec = specs[canonical]
            if rng.random() < 0.5:
                choices = [name for name in spec["names"] if name == updated["name"] or name not in used_names]
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
    result = {key: value.copy() for key, value in schema.items()}
    available = [name for name in new_fields if name not in result]
    if available and rng.random() < probability:
        name = rng.choice(available)
        result[name] = {"name": name, "type": new_fields[name]["type"]}
    return result


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
    if dtype in {"timestamp", "datetime", "datetime64", "timestamptz"}:
        return value.isoformat()
    if dtype == "date":
        return value.date().isoformat()
    if dtype in {"integer", "int", "int32", "int64", "bigint", "tinyint", "bit"}:
        if isinstance(value, datetime):
            return int(value.timestamp())
        if isinstance(value, str) and recipe["kind"] == "choice":
            return recipe["values"].index(value)
        return int(value)
    if dtype in {"float", "float32", "float64", "double", "decimal", "numeric"}:
        # JSON has no decimal type: decimal/numeric represented as JSON numbers.
        return float(value)
    if dtype in {"boolean", "bool"}:
        if isinstance(value, str) and recipe["kind"] == "choice":
            return value == "refunded"  # Boolean encoding for order status.
        return bool(value)
    if dtype in {"json", "jsonb"}:
        return {"address": value}
    if dtype in {"string", "str", "varchar", "text", "char", "enum", "category"}:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, bool):
            return str(value).lower()
        return str(value)
    raise ValueError(f"Unsupported mock dtype: {dtype}")


def generate_payload(rows: int, drift: bool, seed: int, extra_column_probability: float = 0.05) -> dict[str, Any]:
    rng = random.Random(seed)
    now = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
    schema = {name: {"name": name, "type": spec["type"]} for name, spec in original_fields.items()}
    if drift:
        schema = make_new_column(schema, rng, extra_column_probability)
        schema = make_variation(schema, rng)

    specs = original_fields | new_fields
    output = []
    for index in range(rows):
        canonical = {}
        for name in schema:
            canonical[name] = make_value(specs[name]["recipe"], canonical, index, rng, now)
        output.append({field["name"]: cast_value(canonical[name], field["type"], specs[name]["recipe"])
                       for name, field in schema.items()})

    return {
        "metadata": {"count": len(output), "seed": seed, "drift": drift},
        "data": output,
    }


@app.get("/")
def get_orders(
    rows: int = Query(default=10, ge=1, le=1000),
    drift: bool = Query(default=True),
    seed: int = Query(default=67),
    extra_column_probability: float = Query(default=0.05, ge=0, le=1),
) -> dict[str, Any]:
    """Return one complete JSON object containing schema, records, and metadata."""
    return generate_payload(rows, drift, seed, extra_column_probability)
