"""Read-only dashboard view model shared by the new GUI clients."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from core.accounting_logic import AccountingEngine


def _number(value: Any) -> float:
    """Convert SQL Server decimal values to JSON/UI-friendly floats."""
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


def load_dashboard(klient_id: int = 1) -> dict[str, Any]:
    """Return dashboard data without tying the callers to a UI framework.

    The current accounting engine owns the data rules.  This adapter keeps the
    desktop and web presentation layers read-only and presents a helpful state
    if the local SQL Server database is not available yet.
    """
    today = date.today()
    start = date(today.year, 1, 1)

    try:
        engine = AccountingEngine(klient_id=klient_id)
        metrics = engine.get_working_capital_metrics(today)
        movements = engine.get_dashboard_data(start, today)
        trend = engine.get_income_expense_trend(start, today)

        invoices = [
            {
                "date": str(row[0]),
                "due_date": str(row[1] or "—"),
                "partner": row[2] or "—",
                "kind": row[5] or "—",
                "amount": _number(row[6]),
                "description": row[7] or "",
            }
            for row in movements[:8]
        ]
        return {
            "available": True,
            "message": None,
            "period": f"{start:%d.%m.%Y} – {today:%d.%m.%Y}",
            "metrics": {key: _number(value) for key, value in metrics.items()},
            "invoices": invoices,
            "trend": [
                {"month": str(row[0]), "income": _number(row[1]), "expense": _number(row[2])}
                for row in trend
            ],
        }
    except Exception as exc:  # the UI must still start without a configured DB
        return {
            "available": False,
            "message": f"Databázi se nepodařilo načíst: {exc}",
            "period": f"{start:%d.%m.%Y} – {today:%d.%m.%Y}",
            "metrics": {"gross_wc": 0, "net_wc": 0, "liquid_wc": 0},
            "invoices": [],
            "trend": [],
        }
