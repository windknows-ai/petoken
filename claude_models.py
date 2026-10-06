"""Claude Code's own model list, for quick launch (V1.7).

Claude Code keeps the catalog its model picker shows in
``~/.claude/cache/model-catalog/*.json`` and refreshes it by itself (each
file has ``fetchedAt`` / ``staleAt``). Reading it means new models appear
and retired ones disappear without a Petoken update, with the same names,
order and per-model effort levels as Claude's picker. ``cc`` is the CLI
surface (what quick launch starts); the desktop app's ``ccd`` copy is the
fallback. Without any catalog, ``FALLBACK`` (checked with the CLI on
2026-10-06) is used.

Only model metadata is read; nothing is written or sent.
"""
from __future__ import annotations

import json
from pathlib import Path

GENERIC_EFFORTS = (('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('xhigh', 'Extra'), ('max', 'Max'))
FALLBACK = (
    dict(id='claude-opus-5-5', name='Opus 5.5', section='main', efforts=GENERIC_EFFORTS, badge=''),
    dict(id='claude-sonnet-5-5', name='Sonnet 5.5', section='main', efforts=GENERIC_EFFORTS, badge=''),
    dict(id='claude-fable-5-1', name='Fable 5.1', section='main', efforts=GENERIC_EFFORTS,
         badge='Requires usage credits'),
    dict(id='claude-haiku-4-5', name='Haiku 4.5', section='main', efforts=(), badge=''),
    dict(id='claude-opus-5', name='Opus 5', section='overflow', efforts=GENERIC_EFFORTS, badge=''),
    dict(id='claude-sonnet-5', name='Sonnet 5', section='overflow', efforts=GENERIC_EFFORTS, badge=''),
)


def _text(value, limit=120):
    return value.strip()[:limit] if isinstance(value, str) else ''


def _model(entry):
    if not isinstance(entry, dict) or not _text(entry.get('id')) or not _text(entry.get('name')):
        return None
    thinking = entry.get('thinking') if isinstance(entry.get('thinking'), dict) else {}
    efforts = tuple((_text(option.get('id'), 20), _text(option.get('name'), 40) or _text(option.get('id'), 20))
                    for option in thinking.get('effort_options') or []
                    if isinstance(option, dict) and _text(option.get('id'), 20))
    badge = entry.get('badge') if isinstance(entry.get('badge'), dict) else {}
    return dict(id=_text(entry['id']), name=_text(entry['name']), section=_text(entry.get('section'), 20) or 'main',
                efforts=efforts, badge=_text(badge.get('message')))


def catalog(home=None):
    """Models newest-catalog-first: [dict(id, name, section, efforts, badge)].

    ``efforts`` are (id, name) pairs; an empty tuple means the model takes
    no effort setting (Haiku 4.5 today).
    """
    if home is None:
        from claude_usage import default_home
        home = default_home()
    folder = Path(home) / 'cache' / 'model-catalog'
    best = {}
    try:
        paths = list(folder.glob('*.json'))
    except OSError:
        paths = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            config = data['catalog']['config']
            surface = data['catalog'].get('surface') or config.get('id')
            fetched = float(data.get('fetchedAt') or 0)
            models = [m for m in (_model(entry) for entry in config['models']) if m]
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        if models and surface in ('cc', 'ccd') and fetched >= best.get(surface, (0, None))[0]:
            best[surface] = (fetched, models)
    for surface in ('cc', 'ccd'):
        if surface in best:
            models = best[surface][1]
            # Claude's picker order: the main section, then "more models".
            return ([m for m in models if m['section'] == 'main']
                    + [m for m in models if m['section'] != 'main'])
    return [dict(model) for model in FALLBACK]


def find(model_id, models=None):
    models = catalog() if models is None else models
    return next((m for m in models if m['id'] == model_id), None)


def efforts_for(model_id, models=None):
    """Effort (id, name) pairs a model accepts; no model chosen: the generic set."""
    if not model_id:
        return GENERIC_EFFORTS
    model = find(model_id, models)
    return model['efforts'] if model else ()
