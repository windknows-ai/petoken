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

# USD / million tokens, verified 2026-09-16 (GPT-6 Sol/Luna and GPT-5.5
# added 2026-10-06): https://developers.openai.com/api/docs/pricing
# Order: uncached input, cached input, cache writes, output. ``None`` cache
# writes: the model has no separate write price (GPT-5.5's older caching),
# so a record that reports cache writes for it stays unknown.
# Sol, Luna and Astra are separate models: never strip suffixes.
# codex-auto-review has no published price and stays unknown.
MODEL_PRICES = {
    'gpt-6.1-sol': (2, .1, 2.5, 10),
    'gpt-6-sol': (2, .2, 2.5, 10),
    'gpt-6-luna': (.1, .01, .125, .5),
    'gpt-6-astra': (10, 1, 12.5, 50),
    'gpt-5.5': (5, .5, None, 30),
    'gpt-5.6-sol': (4, .4, 5, 20),
    'gpt-5.6-terra': (2, .2, 2.5, 12),
    'gpt-5.6-luna': (.2, .02, .25, 1.2),
}

# Claude Code (Anthropic first-party API) USD / million tokens, verified
# 2026-10-05: https://platform.claude.com/docs/en/about-claude/pricing
# Order: base input, cache hits/refreshes, output. Cache writes derive from
# base input (5-minute 1.25x, 1-hour 2x); dated snapshot IDs share their
# family price. Unknown models stay unknown and never borrow a price.
CLAUDE_PRICES = {
    'claude-fable-5-1': (10, .25, 50),
    'claude-mythos-5-1': (10, .25, 50),
    'claude-fable-5': (10, 1, 50),
    'claude-mythos-5': (10, 1, 50),
    'claude-opus-5-5': (4, .2, 20),
    'claude-opus-5': (5, .5, 25),
    'claude-opus-4-8': (5, .5, 25),
    'claude-opus-4-7': (5, .5, 25),
    'claude-opus-4-6': (5, .5, 25),
    'claude-opus-4-5': (5, .5, 25),
    'claude-opus-4-1': (15, 1.5, 75),
    'claude-opus-4': (15, 1.5, 75),
    'claude-sonnet-5-5': (2, .2, 10),
    'claude-sonnet-5': (2, .2, 10),
    'claude-sonnet-4-6': (3, .3, 15),
    'claude-sonnet-4-5': (3, .3, 15),
    'claude-sonnet-4': (3, .3, 15),
    'claude-haiku-4-5': (1, .1, 5),
    'claude-haiku-3-5': (.8, .08, 4),
}
# Fast mode doubles every rate (caching multipliers stack on top) only on
# these models; elsewhere a fast request runs and bills at standard rates.
CLAUDE_FAST_MODELS = frozenset({'claude-opus-5-5', 'claude-opus-5',
                                'claude-opus-4-8'})
# US-only inference (inference_geo "us") is 1.1x on Claude 4.6 and later.
_CLAUDE_PRE_GEO = frozenset({'claude-opus-4-5', 'claude-opus-4-1',
                             'claude-opus-4', 'claude-sonnet-4-5',
                             'claude-sonnet-4', 'claude-haiku-4-5',
                             'claude-haiku-3-5'})


def claude_price_model(model):
    """Price-table key for a recorded Claude model ID, or ``None``."""
    if not isinstance(model, str):
        return None
    name = model.strip().lower()
    head, _, tail = name.rpartition('-')
    if head and len(tail) == 8 and tail.isdigit():
        name = head  # Dated snapshot: claude-haiku-4-5-20251001.
    return name if name in CLAUDE_PRICES else None


def estimate_claude_usd(usage, model):
    """API-equivalent USD for one Claude response ``usage``; ``None`` if unknown.

    Anthropic ``input_tokens`` already exclude cache reads and writes, so the
    four categories are disjoint. A cache write without its 5m/1h split is
    priced as 5-minute writes (the API default), the cheaper reading.
    """
    key = claude_price_model(model)
    if key is None or not isinstance(usage, dict):
        return None
    def tokens(name):
        value = usage.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
    plain, read, write, out = (tokens('input_tokens'), tokens('cache_read_input_tokens'),
                               tokens('cache_creation_input_tokens'), tokens('output_tokens'))
    if plain is None or out is None:
        return None
    read, write = read or 0, write or 0
    base, hit, output = CLAUDE_PRICES[key]
    split = usage.get('cache_creation')
    long_write = 0
    if isinstance(split, dict):
        value = split.get('ephemeral_1h_input_tokens')
        long_write = min(write, value) if isinstance(value, int) and value > 0 else 0
    cost = (plain * base + read * hit + (write - long_write) * base * 1.25
            + long_write * base * 2 + out * output) / 1_000_000
    if usage.get('speed') == 'fast' and key in CLAUDE_FAST_MODELS:
        cost *= 2
    if usage.get('inference_geo') == 'us' and key not in _CLAUDE_PRE_GEO:
        cost *= 1.1
    return cost if math.isfinite(cost) else None


SUPPORTED_CURRENCIES = ("USD", "CAD", "EUR", "CNY")
DEFAULT_CURRENCY = "CAD"

_CURRENCY_SYMBOLS = {"USD": "$", "CAD": "CA$", "EUR": "\u20ac", "CNY": "\u00a5"}


# Priority/fast multiplier where it differs from the usual 2x.
FAST_MULTIPLIERS = {'gpt-5.5': 2.5}
# Models with no published fast price for long-context requests.
NO_LONG_FAST = frozenset({'gpt-5.5'})


def estimate_usd(tokens, model, tier=None, request_input=None):
    """Estimate API-equivalent USD for one Token delta; ``None`` if unknown."""
    rates = MODEL_PRICES.get(model)
    if rates is None:
        return None
    if any(tokens.get(k) is None for k in ('input_tokens', 'cached_input_tokens', 'output_tokens')):
        return None
    inp, cached, writes, out = rates
    write = max(0, tokens.get('cache_write_input_tokens') or 0)
    if writes is None:
        if write:
            return None   # Cache writes on a model without a write price: unknown.
        writes = 0
    fast = tier in ('priority', 'fast')
    if (request_input if request_input is not None else tokens.get('input_tokens', 0)) > 272000:
        if fast and model in NO_LONG_FAST:
            return None
        inp, cached, writes, out = inp * 2, cached * 2, writes * 2, out * 1.5
    cache = max(0, tokens.get('cached_input_tokens') or 0)
    plain = max(0, tokens.get('input_tokens', 0) - cache - write)
    # Reasoning is already included in output_tokens.
    try:
        cost = (plain * inp + cache * cached + write * writes + tokens.get('output_tokens', 0) * out) / 1_000_000
        cost *= FAST_MULTIPLIERS.get(model, 2) if fast else .5 if tier in ('flex', 'batch') else 1
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
