"""Incremental API wrapper for `financial_statement` scraper.

This file provides a small, stable public surface so we can gradually
modularize the large `financial_statement.py` without breaking callers.
"""

from __future__ import annotations

from typing import Any, Dict

from app.scrapers.financial_statement import (
    scrape_financial_statement as _scrape_financial_statement,
    scrape_income_statement as _scrape_income_statement,
)


def scrape_financial_statement(symbol: str, year: int) -> Dict[str, Any]:
    """Public wrapper for the full financial statement scraper.

    Keeps behaviour identical to the original function in
    `financial_statement.py` but provides a stable import target for
    incremental refactors.
    """
    return _scrape_financial_statement(symbol, year)


def scrape_income_statement(symbol: str, year: int) -> Dict[str, Any]:
    """Backward-compatible alias for scraping income statements."""
    return _scrape_income_statement(symbol, year)


__all__ = ["scrape_financial_statement", "scrape_income_statement"]
