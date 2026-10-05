# Token accounting

## Local source observed

petoken incrementally reads `event_msg` records whose payload is `token_count`. On the local records audited during development, `info.total_token_usage` and `info.last_token_usage` exposed:

- `input_tokens`
- `cached_input_tokens`
- `cache_write_input_tokens`
- `output_tokens`
- `reasoning_output_tokens`
- `total_tokens`
- `model_context_window` beside the usage objects

All audited cache-write values were explicitly reported as `0`; this is different from a missing field. The parser also defensively accepts Responses-style `input_tokens_details.cached_tokens`, `output_tokens_details.reasoning_tokens`, and the alias `cache_write_tokens`. Unknown extra fields remain visible in the raw snapshot but are not silently interpreted.

Metadata used for grouping comes from `session_meta` (session/fork identity), `turn_context` (model, reasoning effort and service tier), the event timestamp, and read-only Codex SQLite task/project metadata. Model names are never guessed from unrelated UI text.

## Official OpenAI usage

The app applies these rules to each exact record:

```text
uncached_input = max(input_tokens - cached_input_tokens, 0)
non_reasoning_output = max(output_tokens - reasoning_output_tokens, 0)
openai_total = source total_tokens
openai_total fallback = input_tokens + output_tokens
```

The fallback is used only when source `total_tokens` is absent and both required fields are known. Cached input is a subset of input. Reasoning is a subset of output. Neither is added to OpenAI total again.

## Derived analytics

```text
new_work = uncached_input + output_tokens
cache_hit_ratio = cached_input_tokens / input_tokens × 100
output_ratio = output_tokens / openai_total × 100
reasoning_share = reasoning_output_tokens / output_tokens × 100
```

Ratios require a positive denominator and all required fields. Invalid/missing inputs return `N/A`, not zero.

For the optional comparison view, cache read and cache write must remain separate and non-overlapping:

```text
comparison_plain_input = max(input - cache_read - cache_write, 0)
Claude-style Raw Processed = comparison_plain_input + cache_read + cache_write + output
```

This calculation is shown only when the actual source provides every component and the input subsets are consistent. It is a visual comparison metric, not the official OpenAI total. When cache-write is unavailable, the app shows `Cache Write: N/A` and `Claude-style: N/A`; the separate supported subtotal uses only known components.

## Aggregation accuracy

- Cumulative counters are converted to increments; identical snapshots are ignored.
- On a counter reset, only a source-provided last-request value is counted. Untraceable carry is excluded and marked partial.
- A first cumulative snapshot containing earlier work retains the carry as undated/unattributed instead of assigning it to the latest model or current day.
- Duplicate session files and inherited ancestor events in forks are removed, while unique child work remains.
- Per-model, per-session and per-day tables all aggregate the same deduplicated event set.
- Calendar ranges use the system local timezone. Empty observed ranges are zero; missing fields within a range remain N/A.

“Local recorded lifetime” includes indexed active and archived local records. It does not claim server-account lifetime and cannot recover deleted or cloud-only sessions.

## Cost estimate

Cost uses the recorded model and service tier, official per-million-token rates, OpenAI's long-context threshold/rates when applicable, and a dated Bank of Canada USD/CAD observation. Reasoning is priced as part of output. An unknown model price, partial token coverage or unavailable cache-write split is labelled as a partial API-equivalent estimate, never a subscription charge.

## Claude Code (V1.5)

Claude Code records Anthropic usage per API response. Anthropic
`input_tokens` exclude cache traffic, so `claude_usage.map_usage` converts
each deduplicated response into the shared categories above:

| Shared field | Claude Code source |
| --- | --- |
| `input_tokens` | `input_tokens + cache_read_input_tokens + cache_creation_input_tokens` |
| `cached_input_tokens` | `cache_read_input_tokens` |
| `cache_write_input_tokens` | `cache_creation_input_tokens` |
| `output_tokens` | `output_tokens` (thinking included) |
| `reasoning_output_tokens` | `output_tokens_details.thinking_tokens`, else unknown |
| `total_tokens` | `input_tokens + output_tokens` (shared field) |

Any missing category leaves the derived input and total unknown instead of
zero. The derived analytics then hold for both providers: uncached input
minus cache writes equals Anthropic's own `input_tokens`.

The cost estimate (`pricing.estimate_claude_usd`) uses Anthropic's
first-party price table: base input, cache hits/refreshes and output per
model, cache writes at 1.25x (5 minutes) or 2x (1 hour) of base input from
the recorded split, 2x for fast mode on Opus 5.5 / Opus 5 / Opus 4.8 and
1.1x for US-only inference on Claude 4.6 and later. Dated snapshot IDs use
their family price; unknown models stay unpriced (`N/A`).
