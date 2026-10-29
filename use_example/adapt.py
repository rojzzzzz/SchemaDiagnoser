from typing import Any


def adapt_order(
    order_data: dict[str, Any], diagnosis: dict[str, Any]
) -> dict[str, Any]:
    """Adapt the same, unmodified order already accepted by validate_order().

    Schema expansion drops extra fields. Naming or mixed changes drop only
    redundant scalar aliases (case/underscore variants with identical values).
    Other high-confidence categories still drop reported extra fields so the
    returned order does not preserve known non-contract additions.
    Require a complete review with probability >= 0.9; otherwise keep the copy.
    Contract fields and the original order are never modified.
    """

    adapted = order_data.copy()
    review = diagnosis["review"]
    explanation = review["diagnosis"] or {}
    category = explanation.get("category")
    added = {c["column"] for c in diagnosis["changes"] if c["issues"] == ["added"]}

    if (review["status"] != "completed" or review.get("coverage")
            or not explanation.get("probability", 0) >= 0.9):
        return adapted

    original = order_data.keys() - added
    for column in added:
        if category not in {"naming_change", "mixed_changes"}:
            adapted.pop(column, None)
            continue

        matches = [name for name in original
                   if name.replace("_", "").casefold() == column.replace("_", "").casefold()]
        if len(matches) == 1:
            
            value, original_value = adapted.get(column), adapted[matches[0]]
            if ((value is None or isinstance(value, (str, int, float, bool)))
                    and type(value) is type(original_value) and value == original_value):
                adapted.pop(column)
    return adapted
