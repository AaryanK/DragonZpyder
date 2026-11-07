"""Deterministic virtual-time comparison of general agent monitoring patterns.

Synthetic, NOT measured Hatchet/Temporal/Windmill execution. No wall-clock
sleep, network access, LLM calls, or real-money transactions.
"""
from __future__ import annotations

from dataclasses import dataclass
from heapq import heappush, heappop
import json
from math import ceil
from time import perf_counter


@dataclass(frozen=True)
class Observation:
    id: str
    published_s: int
    relevant: bool
    push: bool = False


@dataclass(frozen=True)
class Scenario:
    name: str
    duration_s: int
    poll_interval_s: int
    feed_limit: int
    observations: tuple[Observation, ...]
    network_outage: tuple[int, int]
    restart_s: int


STRATEGIES = (
    'periodic_full_agent',
    'stateful_conditional_poll',
    'event_first_with_poll_fallback',
)


def scenarios() -> tuple[Scenario, ...]:
    stream = tuple(
        Observation(f'evt-{i:03d}', 5 * i, i % 5 != 0, i % 6 != 0)
        for i in range(1, 241)
    )
    watch_hours = (4, 16, 35, 71, 106)
    hourly = tuple(
        Observation(f'change-{i}', 3600 * h + 60 * (i % 5 + 1), True)
        for i, h in enumerate(watch_hours)
    )
    research = tuple(
        Observation(f'research-{i:02d}', 600 + i * 17800,
                    relevant=(i % 4 != 0), push=(i % 4 != 1))
        for i in range(24)
    )
    return (
        Scenario('high_frequency_stream', 1260, 60, 8, stream,
                 (450, 540), 610),
        Scenario('hourly_web_watch', 5 * 86400, 3600, 5, hourly,
                 (35 * 3600, 36 * 3600), 57 * 3600),
        Scenario('five_day_research', 5 * 86400, 3600, 5, research,
                 (60 * 3600, 62 * 3600), 72 * 3600),
    )


def percentile(values: list[int], proportion: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, ceil(len(ordered) * proportion) - 1)]


def simulate(scenario: Scenario, strategy: str) -> dict:
    """Run one identical scenario with different wake-up policies.

    Assumptions, not empirical throughput:
    - Synthetic source returns only newest N items (as a bounded search/feed).
    - HTTP outage blocks polling, but push has a separate delivery channel.
    - Every ninth relevant result's portal write fails once and is retried 12s
      later using a durable outbox, without a second LLM call.
    - Source poll latency is 2s, push latency 1s, analysis latency 3s,
      delivery latency 2s. All are virtual.
    - Every strategy has an idempotent outbox preserved across a restart.
    - Relevance is an injected oracle to isolate scheduling quality; it does
      NOT measure actual LLM filtering or factual correctness.
    """
    if strategy not in STRATEGIES:
        raise ValueError('Unknown benchmark strategy')
    by_id = {obs.id: obs for obs in scenario.observations}
    actions = []
    order = 0

    def enqueue(at: int, kind: str, key: str = ''):
        nonlocal order
        if at <= scenario.duration_s:
            heappush(actions, (at, order, kind, key))
            order += 1

    for tick in range(0, scenario.duration_s + 1, scenario.poll_interval_s):
        enqueue(tick, 'poll')
    if strategy == 'event_first_with_poll_fallback':
        for index, obs in enumerate(scenario.observations):
            if obs.push:
                enqueue(obs.published_s + 1, 'push', obs.id)
                if index % 9 == 0:
                    enqueue(obs.published_s + 2, 'push', obs.id)
    enqueue(scenario.restart_s, 'restart')

    seen = set()  # durable across simulated worker restart
    pending = set()  # durable outbox
    delivered = {}
    first_delivery_failure = set()
    last_etag = None
    waiting_for_analysis = set()
    flush_scheduled = False
    model_invocations = polls = http_failures = conditional_304 = 0
    source_bytes = push_events = duplicate_publications = retry_count = 0
    restarts = 0
    stale_duplicates = 0
    while actions:
        now, _, kind, key = heappop(actions)
        if kind == 'restart':
            restarts += 1
            # Durable checkpoint + outbox are intentionally not reset.
            # An ephemeral process state would be lost here.
            continue
        if kind == 'analyze':
            flush_scheduled = False
            if not waiting_for_analysis:
                continue
            model_invocations += 1
            for event_id in sorted(waiting_for_analysis):
                enqueue(now + 5, 'deliver', event_id)
            waiting_for_analysis.clear()
            continue
        if kind == 'deliver':
            if key in delivered:
                duplicate_publications += 1
                continue
            if key not in pending:
                continue
            idx = int(key.split('-')[-1]) if key.startswith('evt-') else (
                int(key.split('-')[-1]) if key.startswith('research-') else 0
            )
            if idx % 9 == 2 and key not in first_delivery_failure:
                first_delivery_failure.add(key)
                retry_count += 1
                enqueue(now + 12, 'deliver', key)
                continue
            pending.discard(key)
            delivered[key] = now
            continue
        batch = []
        if kind == 'push':
            push_events += 1
            batch = [by_id[key]]
        elif kind == 'poll':
            polls += 1
            if scenario.network_outage[0] <= now < scenario.network_outage[1]:
                http_failures += 1
                continue
            current = [x for x in scenario.observations if x.published_s <= now]
            batch = current[-scenario.feed_limit:]
            etag = tuple(x.id for x in batch)
            if strategy != 'periodic_full_agent' and etag == last_etag:
                conditional_304 += 1
                source_bytes += 160
                continue
            last_etag = etag
            source_bytes += 400 + 280 * len(batch)
        novel = []
        for obs in batch:
            if obs.id in seen:
                stale_duplicates += 1
                continue
            seen.add(obs.id)
            if obs.relevant:
                novel.append(obs)
        if strategy == 'event_first_with_poll_fallback':
            if novel:
                waiting_for_analysis.update(obs.id for obs in novel)
                for obs in novel:
                    pending.add(obs.id)
                if not flush_scheduled:
                    enqueue(now + (30 if scenario.name == 'high_frequency_stream' else 15), 'analyze')
                    flush_scheduled = True
            continue
        if kind == 'poll' and strategy == 'periodic_full_agent':
            model_invocations += 1  # expensive model called every tick
        elif novel:
            model_invocations += 1  # once per relevant batch
        for obs in novel:
            pending.add(obs.id)
            # Source fetch 2s, model 3s, publish 2s; push receives in 1s.
            enqueue(now + (7 if kind == 'poll' else 5), 'deliver', obs.id)

    expected = {x.id for x in scenario.observations if x.relevant}
    succeeded = expected.intersection(delivered)
    latencies = [delivered[key] - by_id[key].published_s for key in succeeded]
    return {
        'scenario': scenario.name,
        'strategy': strategy,
        'virtual_duration_h': round(scenario.duration_s / 3600, 3),
        'relevant_updates': len(expected),
        'delivered': len(succeeded),
        'missed': len(expected - succeeded),
        'recall_pct': round(100 * len(succeeded) / len(expected), 1),
        'latency_p50_s': percentile(latencies, .50),
        'latency_p95_s': percentile(latencies, .95),
        'model_invocations': model_invocations,
        'estimated_model_tokens_at_1000_per_call': model_invocations * 1000,
        'source_polls': polls,
        'http_failures': http_failures,
        'conditional_304': conditional_304,
        'source_bytes': source_bytes,
        'push_messages': push_events,
        'delivery_retries': retry_count,
        'duplicate_publications': duplicate_publications,
        'worker_restarts': restarts,
    }


def benchmark() -> dict:
    start = perf_counter()
    rows = [simulate(s, name) for s in scenarios() for name in STRATEGIES]
    return {
        'kind': 'deterministic_virtual_time_simulation_not_real_provider_measurement',
        'assumed_provider_latency_s': {'poll': 2, 'push': 1, 'analysis': 3, 'publish': 2},
        'assumed_tokens_per_model_invocation': 1000,
        'summary': rows,
        'wall_elapsed_ms': round((perf_counter() - start) * 1000, 2),
        'limitations': [
            'Not a live deployment benchmark of Hatchet, Temporal, Windmill, or any provider.',
            'Injected relevance oracle, synthetic sources, bounded feeds, failure patterns, and fixed latencies.',
            'No real LLM inference, brokerage actions, notification delivery, or Internet requests.',
            'Source polling counts are logical invocations; 304 and payload bytes are modeled assumptions.',
        ],
    }


if __name__ == '__main__':
    print(json.dumps(benchmark(), sort_keys=True, indent=2))
