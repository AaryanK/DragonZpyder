# Three-scenario virtual-time benchmark — November 7, 2026

> **Classification: synthetic benchmark of execution patterns.** NOT a
> head-to-head benchmark of Hatchet, Temporal, Windmill, live search engines,
> real LLMs, live user actions, or real processing latency.

## Reproduce

Run from `api/` using Python 3.12; standard library only:

```bash
python -m agent_platform.ops_benchmark
pytest -q tests/test_ops_benchmark.py
```

The JSON output includes all nine scenario/strategy observations and
limits. GitHub Actions runs it in the `agent-stack-imports` job.

## Virtual-time results

| Scenario | Scheduling pattern | Relevant updates delivered | Model wakes | p95 time-to-delivery |
| --- | --- | ---: | ---: | ---: |
| High-frequency stream | Periodic full-agent poll | 122/192 (63.5%) | 21 | 42 s |
| High-frequency stream | Stateful conditional poll | 122/192 (63.5%) | 19 | 42 s |
| High-frequency stream | Event-first + polling fallback | **191/192 (99.5%)** | 33 | 48 s |
| Hourly web watch | Periodic full-agent poll | 5/5 (100%) | 120 | 3547 s |
| Hourly web watch | Stateful conditional poll | 5/5 (100%) | **5** | 3547 s |
| Hourly web watch | Event-first + polling fallback | 5/5 (100%) | 5 | 3560 s |
| Five-day research | Periodic full-agent poll | 18/18 (100%) | 119 | 3419 s |
| Five-day research | Stateful conditional poll | 18/18 (100%) | **18** | 3419 s |
| Five-day research | Event-first + polling fallback | **18/18 (100%)** | 18 | 3220 s |

**Simulation design and constraints**

- High-frequency: 240 messages at 5-second spacing (192 relevant); 21-minute
  virtual time; 1-minute polling; feed exposes only eight newest items. This
  intentionally shows why finite search-result pages miss fast updates.
- Hourly web watch: five changes across five days, 121 scheduled hourly polls.
- Five-day research: 24 observations, 18 relevant, across 120 virtual hours.
- All scenarios inject HTTP outages, one worker restart, duplicate push
  messages where applicable, transient portal-delivery failures and retries.
  All strategies receive equal idempotent, persisted-outbox semantics.
- Push-first mode batches fast events for up to 30 seconds before model
  processing. Other scenarios batch for 15 seconds.
- The agent's relevance decision is a synthetic **oracle**. That is not a
  model evaluation and does not measure factual correctness or false negatives.
- Assumed transport latencies and 1,000 tokens per agent invocation are
  purely illustrative. No inference or HTTP usage is charged by this run.
- Conditional 304 responses are **modeled only for hypothetical ETag-capable
  source endpoints**. Neither a Wikipedia search API query nor a Brave search
  query should be assumed to support conditional revalidation or free 304s.
- The scripts use a virtual clock (no sleep). They do not exercise actual
  Hatchet recovery after worker process crashes.

**Design conclusion**

Use Hatchet for actual durable events, schedules and retries. Prefer push
from source systems, a stateful conditional pull fallback for sources without
push, bounded batching to prevent one LLM call per message, and an idempotent
outbox for authorized delivery. Do not spin up a long-running LLM to check
sources on a timer. For five-day watches, enforce actual expiration and
notification permissions before exposing user-defined schedules.

## Real internet search validation (separate from simulation)

The staging Agent Test Lab performed one operator-gated live Wikipedia search
and logged `Staging no-model public-web search smoke result=verified source_count=1`.
This was a real Internet request and zero LLM inference; the one-time test
flag was switched back off afterward.

The research tool supports Wikipedia and optional Brave API, plus a separately
configured operator-hosted SearXNG metasearch backend, with fixed HTTPS/private
Railway origins and no agent-controlled destination URLs. Only Wikipedia was
verified live; Brave and SearXNG have mocked integration tests but have not
been provisioned for live general web searching.

## Open-source basis

- Hatchet run, schedule, cron and event APIs:
  https://docs.hatchet.run/v1/running-your-task
- Windmill stateful polling triggers:
  https://www.windmill.dev/docs/flows/flow_trigger
- Temporal time-skipping testing patterns:
  https://docs.temporal.io/develop/python/best-practices/testing-suite
- SearXNG general search API:
  https://docs.searxng.org/dev/search_api.html

## Production acceptance still required

1. Benchmark actual Hatchet event-to-action latency, missed triggers and
   restart recovery under load.
2. Add rate-limited, authorized general web search and fetch (with safe
   egress and dated evidence); validate source coverage with live queries.
3. Compare relevance-extraction accuracy and per-task cost across LLM models.
4. Add authenticated user-owned monitors, cancellation, expiry, notification
   destinations and atomic idempotent action/portal delivery.
5. Keep production services untouched until these gates pass.
