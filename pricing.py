"""Internal API-equivalent cost estimation and display-currency conversion.

Cost semantics: every displayed amount is an API-equivalent *estimate* derived
from recorded Token usage and the internal model price table below. It is never
a subscription charge, invoice, or amount actually billed.

USD is the canonical internal currency: Token usage is first estimated in USD,
then converted once into the selected display currency. No per-currency pricing
tables exist. Unknown models never borrow another model's price; missing data
stays unknown (``None``) so callers can show honest partial/unavailable states.
"""
from __future__ import annotations

import math

# USD / million tokens, verified 2026-09-16:
# https://developers.openai.com/api/docs/pricing
# Order: uncached input, cached input, cache writes, output.
MODEL_PRICES = {
    'gpt-6-astra': (10, 1, 12.5, 50),
    'gpt-5.6-sol': (4, .4, 5, 20),
    'gpt-5.6-terra': (2, .2, 2.5, 12),
    'gpt-5.6-luna': (.2, .02, .25, 1.2),
}

SUPPORTED_CURRENCIES = ("USD", "CAD", "EUR", "CNY")
DEFAULT_CURRENCY = "CAD"

_CURRENCY_SYMBOLS = {"USD": "$", "CAD": "CA$", "EUR": "\u20ac", "CNY": "\u00a5"}


def estimate_usd(tokens, model, tier=None, request_input=None):
    """Estimate API-equivalent USD for one Token delta; ``None`` if unknown."""
    rates = MODEL_PRICES.get(model)
    if rates is None:
        return None
    if any(tokens.get(k) is None for k in ('input_tokens', 'cached_input_tokens', 'output_tokens')):
        return None
    inp, cached, writes, out = rates
    if (request_input if request_input is not None else tokens.get('input_tokens', 0)) > 272000:
        inp, cached, writes, out = inp * 2, cached * 2, writes * 2, out * 1.5
    cache = max(0, tokens.get('cached_input_tokens') or 0)
    write = max(0, tokens.get('cache_write_input_tokens') or 0)
    plain = max(0, tokens.get('input_tokens', 0) - cache - write)
    # Reasoning is already included in output_tokens.
    try:
        cost = (plain * inp + cache * cached + write * writes + tokens.get('output_tokens', 0) * out) / 1_000_000
        cost *= 2 if tier in ('priority', 'fast') else .5 if tier in ('flex', 'batch') else 1
        return cost if math.isfinite(cost) else None
    except OverflowError:
        return None


def normalize_currency(value):
    return value if value in SUPPORTED_CURRENCIES else DEFAULT_CURRENCY


def normalize_rates(cache):
    """Accept the current ``{date, source, rates}`` cache or the legacy CAD-only
    ``{rate, date, source}`` shape; always return ``{date, source, rates}``."""
    cache = dict(cache) if isinstance(cache, dict) else {}
    rates = cache.get("rates")
    if isinstance(rates, dict):
        return {"date": cache.get("date"), "source": cache.get("source"),
                "rates": {k: v for k, v in rates.items() if isinstance(v, (int, float))}}
    legacy = cache.get("rate")
    return {"date": cache.get("date"), "source": cache.get("source"),
            "rates": {"CAD": legacy} if isinstance(legacy, (int, float)) else {}}


def convert_usd(usd, currency, rates):
    """Convert a USD estimate into ``currency``; ``None`` when no rate exists."""
    if usd is None:
        return None
    if currency == "USD":
        return usd
    rate = (rates or {}).get(currency)
    return usd * rate if isinstance(rate, (int, float)) else None


def format_cost(value, currency):
    """Format a converted cost with its currency symbol; ``N/A`` if unknown."""
    if value is None:
        return "N/A"
    return f"{_CURRENCY_SYMBOLS.get(currency, '')}{value:,.2f}"
