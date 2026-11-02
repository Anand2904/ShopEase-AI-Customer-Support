import csv
from pathlib import Path
from datetime import datetime
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = BASE_DIR / "ticket_logs.csv"

FIELDNAMES = [
    "ticket_id",
    "timestamp",
    "customer_name",
    "order_id",
    "complaint",
    "category",
    "urgency",
    "sentiment",
    "kb_sources",
    "response",
    "status",
    "escalation_reason",
]


def decide_escalation(
    urgency: str,
    sentiment: str,
    knowledge_found: bool,
    confidence: str,
    complaint: str,
) -> tuple[str, str]:
    """
    Decide whether a ticket should be escalated.
    Returns the ticket status and escalation reason.
    """

    reasons = []
    complaint_lower = complaint.lower()

    if urgency == "High":
        reasons.append("High urgency")

    if sentiment == "Angry":
        reasons.append("Customer is angry")

    if not knowledge_found:
        reasons.append("No matching knowledge-base information")

    if confidence == "Low":
        reasons.append("Low resolution confidence")

    escalation_keywords = [
        "lawyer",
        "legal action",
        "court",
        "fraud",
        "payment dispute",
        "unauthorized payment",
    ]

    if any(keyword in complaint_lower for keyword in escalation_keywords):
        reasons.append("Legal threat, fraud, or payment dispute")

    if reasons:
        return "Escalated", "; ".join(reasons)

    return "Resolved", ""


def save_ticket(
    customer_name: str,
    order_id: str,
    complaint: str,
    category: str,
    urgency: str,
    sentiment: str,
    kb_sources: str,
    response: str,
    status: str,
    escalation_reason: str,
) -> dict:
    """Save a customer ticket as a new row in the CSV log."""

    ticket = {
        "ticket_id": str(uuid4())[:8].upper(),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "customer_name": customer_name,
        "order_id": order_id,
        "complaint": complaint,
        "category": category,
        "urgency": urgency,
        "sentiment": sentiment,
        "kb_sources": kb_sources,
        "response": response,
        "status": status,
        "escalation_reason": escalation_reason,
    }

    file_exists = LOG_FILE.exists()

    with LOG_FILE.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)

        if not file_exists or LOG_FILE.stat().st_size == 0:
            writer.writeheader()

        writer.writerow(ticket)

    return ticket