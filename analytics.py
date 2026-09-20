"""Nullable, schema-aware token accounting shared by every analytics view."""
from collections import defaultdict
from datetime import date, datetime, timedelta

TOKEN_KEYS = ('input_tokens','cached_input_tokens','cache_write_input_tokens',
              'output_tokens','reasoning_output_tokens','total_tokens')


def count(value):
    return value if isinstance(value,int) and not isinstance(value,bool) and value >= 0 else None


def normalize_usage(raw):
    raw = raw if isinstance(raw,dict) else {}
    result = {k:count(raw.get(k)) for k in TOKEN_KEYS}
    for key, nested, leaf in [('cached_input_tokens','input_tokens_details','cached_tokens'),
                               ('reasoning_output_tokens','output_tokens_details','reasoning_tokens')]:
        if key not in raw and isinstance(raw.get(nested),dict):
            result[key] = count(raw[nested].get(leaf))
    if 'cache_write_input_tokens' not in raw and 'cache_write_tokens' in raw:
        result['cache_write_input_tokens'] = count(raw['cache_write_tokens'])
    if 'total_tokens' not in raw and all(result[k] is not None for k in ('input_tokens','output_tokens')):
        result['total_tokens'] = result['input_tokens']+result['output_tokens']
    return result


def derive(t):
    i,c,w,o,r,total = (t.get(k) for k in TOKEN_KEYS)
    uncached = max(0,i-c) if i is not None and c is not None else None
    nonreasoning = max(0,o-r) if o is not None and r is not None else None
    # OpenAI cache writes, when exposed, are part of input. Make comparison
    # components disjoint before adding them, not an inflated headline total.
    plain = max(0,uncached-w) if uncached is not None and w is not None and c+w <= i else None
    return dict(uncached_input_tokens=uncached,non_reasoning_output_tokens=nonreasoning,
        new_work=uncached+o if uncached is not None and o is not None else None,
        cache_hit_ratio=c/i*100 if i and c is not None and c <= i else None,
        output_ratio=o/total*100 if total and o is not None else None,
        reasoning_ratio=r/o*100 if o and r is not None and r <= o else None,
        comparison_uncached=plain,
        claude_raw=plain+c+w+o if plain is not None and o is not None else None,
        known_processed=uncached+c+o if uncached is not None and o is not None else None)


def summarize(records):
    known = {k:sum(r['tokens'].get(k) or 0 for r in records) for k in TOKEN_KEYS}
    coverage = {k:sum(r['tokens'].get(k) is not None for r in records) for k in TOKEN_KEYS}
    tokens = {k:known[k] if records and coverage[k] == len(records) else None for k in TOKEN_KEYS}
    return dict(tokens=tokens,known=known,coverage=coverage,events=len(records),derived=derive(tokens))


def aggregate(records, tz=None):
    unique = {}
    for r in records:
        # Session metadata ID survives duplicated files and archive moves.
        key = (r.get('origin') or r['session'], r['event_id'])
        unique.setdefault(key,r)
    records = list(unique.values())
    result = summarize(records)
    by_model,by_day,by_session = defaultdict(list),defaultdict(list),defaultdict(list)
    undated = []
    for r in records:
        by_model[r.get('model') or 'unknown_model'].append(r)
        by_session[r['session']].append(r)
        try:
            stamp = datetime.fromisoformat(r['timestamp'].replace('Z','+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('timestamp without timezone')
            day = stamp.astimezone(tz).date().isoformat()
            by_day[day].append(r)
        except (ValueError,TypeError,AttributeError,KeyError):
            undated.append(r)
    result['models'] = [dict(name=k,**summarize(v)) for k,v in sorted(by_model.items())]
    result['daily'] = [dict(name=k,**summarize(v)) for k,v in sorted(by_day.items(),reverse=True)]
    result['sessions'] = [dict(name=k,**summarize(v)) for k,v in by_session.items()]
    result['undated'] = summarize(undated)
    result['ranges'] = history_ranges(result['daily'])
    return result


def history_ranges(daily,today=None):
    today = today or date.today()
    result = {}
    for key,days in [('today',1),('last7',7),('last30',30)]:
        start = (today-timedelta(days=days-1)).isoformat()
        selected = [d for d in daily if start <= d['name'] <= today.isoformat()]
        known = {k:sum(d['known'][k] for d in selected) for k in TOKEN_KEYS}
        n = sum(d['events'] for d in selected)
        coverage = {k:sum(d['coverage'][k] for d in selected) for k in TOKEN_KEYS}
        # Empty range is an observed zero within loaded local records, not an
        # assertion that deleted/cloud-only records never existed.
        tokens = {k:known[k] if coverage[k] == n else None for k in TOKEN_KEYS}
        result[key] = dict(tokens=tokens,known=known,coverage=coverage,events=n,derived=derive(tokens))
    return result
