"""Synthetic distractor tools to stress-test routing as the catalog grows (37 -> 100 -> 217 tools)."""
from __future__ import annotations

from .world import Out, Param, Tool

# (domain, plural, singular, domain-specific field)
NOUNS = [
    ("support", "tickets", "ticket", "priority"), ("support", "ticket comments", "ticket comment", "visibility"),
    ("support", "support agents", "support agent", "queue"), ("support", "macros", "macro", "category"),
    ("support", "satisfaction surveys", "satisfaction survey", "score"),
    ("billing", "invoices", "invoice", "amount"), ("billing", "billing customers", "billing customer", "plan"),
    ("billing", "subscriptions", "subscription", "amount"), ("billing", "refunds", "refund", "amount"),
    ("billing", "payment methods", "payment method", "brand"),
    ("ops", "incident records", "incident record", "severity"), ("ops", "alerts", "alert", "severity"),
    ("ops", "services", "service", "tier"), ("ops", "on call schedules", "on call schedule", "rotation"),
    ("ops", "escalation policies", "escalation policy", "levels"),
    ("hr", "employees", "employee", "department"), ("hr", "leave requests", "leave request", "days"),
    ("hr", "payslips", "payslip", "amount"), ("hr", "job openings", "job opening", "department"),
    ("hr", "candidates", "candidate", "stage"),
    ("inventory", "products", "product", "quantity"), ("inventory", "orders", "order", "amount"),
    ("inventory", "warehouses", "warehouse", "capacity"), ("inventory", "shipments", "shipment", "carrier"),
    ("inventory", "suppliers", "supplier", "region"),
    ("marketing", "campaigns", "campaign", "audience size"), ("marketing", "marketing leads", "marketing lead", "source"),
    ("marketing", "newsletters", "newsletter", "audience size"), ("marketing", "landing pages", "landing page", "conversion rate"),
    ("marketing", "audiences", "audience", "audience size"),
    ("analytics", "dashboards", "dashboard", "views"), ("analytics", "funnels", "funnel", "conversion rate"),
    ("analytics", "cohorts", "cohort", "size"), ("analytics", "experiments", "experiment", "variant"),
    ("analytics", "saved reports", "saved report", "schedule"),
    ("devops", "deployments", "deployment", "branch"), ("devops", "pipelines", "pipeline", "branch"),
    ("devops", "builds", "build", "branch"), ("devops", "environments", "environment", "region"),
    ("devops", "releases", "release", "version"),
    ("wiki", "wiki pages", "wiki page", "space"), ("wiki", "wiki comments", "wiki comment", "space"),
    ("wiki", "wiki spaces", "wiki space", "visibility"), ("wiki", "page templates", "page template", "category"),
    ("wiki", "attachments", "attachment", "size"),
    ("security", "vulnerabilities", "vulnerability", "severity"), ("security", "access reviews", "access review", "scope"),
    ("security", "audit logs", "audit log", "actor"), ("security", "stored secrets", "stored secret", "rotation"),
    ("security", "security policies", "security policy", "scope"),
    ("finance", "expenses", "expense", "amount"), ("finance", "budgets", "budget", "amount"),
    ("finance", "purchase orders", "purchase order", "amount"), ("finance", "vendors", "vendor", "region"),
    ("finance", "journal entries", "journal entry", "amount"),
    ("legal", "contracts", "contract", "counterparty"), ("legal", "contract clauses", "contract clause", "category"),
    ("legal", "approvals", "approval", "approver"), ("legal", "signatures", "signature", "signer"),
    ("legal", "compliance tasks", "compliance task", "framework"),
]


def _snake(s: str) -> str:
    return s.replace(" ", "_")


def make_distractors(n: int) -> list[Tool]:
    """Return up to n distractor tools (3 per noun: list/get/search)."""
    out: list[Tool] = []
    for dom, plural, sing, extra in NOUNS:
        if len(out) >= n:
            break
        idf = f"{_snake(sing)}_id"
        base = [Out(idf, f"{sing} id"), Out("name", f"{sing} name"), Out("status", f"{sing} status"),
                Out("owner_email", f"email address of the {sing} owner"), Out(_snake(extra), f"{sing} {extra}"),
                Out("created_at", "creation date"), Out("updated_at", "last update date")]
        out.append(Tool(dom, f"list_{_snake(plural)}", f"List {plural} in the {dom} system, optionally filtered by status or owner.",
                        [Param("status", f"{sing} status"), Param("owner_email", f"email address of the {sing} owner"),
                         Param("limit", "maximum number of results", False, "integer")], base, "list", lambda a: []))
        out.append(Tool(dom, f"get_{_snake(sing)}", f"Get one {sing} from the {dom} system by id.",
                        [Param(idf, f"{sing} id", True)], base + [Out("notes", f"{sing} notes")], "object", lambda a: {}))
        out.append(Tool(dom, f"search_{_snake(plural)}", f"Search {plural} in the {dom} system by keyword.",
                        [Param("query", f"keyword to search {plural} for", True)], base[:5], "list", lambda a: []))
    return out[:n]
