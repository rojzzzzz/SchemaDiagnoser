from email.message import EmailMessage
from typing import Any
import logging
import smtplib
import ssl

from SchemaDiagnoser.fn import check_schema
from use_example.config import (
    API_KEY, RECEIVER_EMAIL, SENDER_EMAIL, SMTP_HOST, SMTP_PORT, SMTP_PASSWORD,
)

logger = logging.getLogger(__name__)


def send_email(subject: str, body: str) -> bool:
    """Send through the configured SMTP server; delivery failure is nonfatal."""
    try:
        message = EmailMessage()
        message["From"] = SENDER_EMAIL
        message["To"] = RECEIVER_EMAIL
        message["Subject"] = subject
        message.set_content(body)
        connection = (smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=2,
                                      context=ssl.create_default_context())
                      if SMTP_PORT == 465 else smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=2))
        with connection as smtp:
            if SMTP_PASSWORD:
                if SMTP_PORT != 465:
                    smtp.starttls(context=ssl.create_default_context())
                smtp.login(SENDER_EMAIL, SMTP_PASSWORD)
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException, ValueError):
        logger.exception("Could not send schema advisory email")
        return False


def validate_order(order_data: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """Report acceptance and alert on drift; invalid orders do not raise or get repaired."""

    diagnosis = check_schema(contract, [order_data], ai_review=True, allow_extra=True, api_key=API_KEY)
    changes, review = diagnosis["changes"], diagnosis["review"]
    if not changes:
        return diagnosis

    lines = [
        f"{c['column']}: {', '.join(c['issues'])} "
        f"(expected={c['expected']}, received={c['received']})"
        for c in changes
    ]

    if review["status"] == "completed":
        explanation = review["diagnosis"]
        lines.extend([
            f"Likely cause: {explanation['category']} "
            f"(probability={explanation['probability']:.1%}).",
            f"Next check: {explanation['check']}",
        ])
        for rename in review.get("renames", []):
            if rename["category"] == "possible_rename":
                missing, added = (changes[i]["column"] for i in rename["change_indices"])
                ambiguity = "; competing matches" if rename["competing_changes"] else ""
                lines.append(f"Possible rename: {added} -> {missing} "
                             f"({rename['probability']:.1%}{ambiguity}).")

        for name, counts in review.get("coverage", {}).items():
            lines.append(f"Partial AI review: {counts['reviewed']}/{counts['total']} {name}.")
    elif review["status"] == "failed":
        lines.append(f"AI review unavailable: {review['error']}")

    summary = "\n".join(lines)
    if not diagnosis["valid"]:
        logger.error(f"Order rejected:\n{summary}")
        send_email("Order rejected — schema mismatch", summary)
    else:
        logger.warning(f"Order accepted with schema advisories:\n{summary}")
        send_email("Order schema advisory — processing continues", summary)
    return diagnosis
