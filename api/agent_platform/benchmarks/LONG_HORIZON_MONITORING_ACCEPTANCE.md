# Long-horizon recurring-monitoring acceptance suite

## Scope and evidence levels

This suite has two independent decision tracks:

1. **Objective rules**: machine-checkable thresholds, time-series changes, deadlines, duplicate suppression, source identity, and state transition rules. Ground truth is deterministic.
2. **Subjective decisions**: prioritize competing objectives, decide whether a change is worth attention, and assess quality or relevance with evidence. Ground truth is a *rubric and blinded human adjudication*, not the model's self-reported confidence.

The first automated tier runs deterministic tools, real disposable PostgreSQL and simulated HTTP. **It does not establish that a production Hatchet schedule, live Personal MCP session or LLM judgment worked.** The second tier requires a live signed-in user-authorized Hatchet canary and real event-time observation.

## Zero-mutation live test matrix

| Scenario | Cadence and minimum duration | Objective oracle | Subjective adjudication | Failure injection |
| --- | --- | --- | --- | --- |
| Worker-health trend | 5-minute wakes, >= 12 actual wakes | RAM >=85%, disk >=90%, RAM jump >=15 points; one receipt per interval | Whether a sustained rise warrants human investigation rather than alert fatigue | Duplicate delivery and worker restart |
| Research source-change monitor | Hourly, >= 24 actual wakes | URL/content-fingerprint changes; source attribution and alert dedupe | Whether a new paper materially changes conclusions, citing text differences | Empty search, late source update |
| Personal task deadlines (read-only) | Hourly, >= 24 actual wakes | Task due timestamps and changed statuses from authorized Operly MCP | Which tasks warrant attention given goal/context, evidence and uncertainty | Session revoked between wakes |
| Engineering release risk | On new authenticated repo event and daily review | Commit SHA, CI result, deployment SHA, failure count | Is deployment risk acceptable? Require reviewer sign-off for action | Contradictory CI vs deploy |
| Price/cost watch | Daily, >= 7 actual wakes | Provider prices, rate/cost ceilings, measurable threshold | Is higher spend justified by benchmark benefit? | Unknown provider cost hold |
| Long-horizon goal continuation | 3 explicit Hatchet wakes with separate process instances | Monotonic PostgreSQL sequence, immutable identity, receipts | Does outcome satisfy *user intent*? Human-reviewed evidence | Quota pause, ambiguous upstream failure |

## Scoring contract

For each scheduled run, preserve: immutable goal ID, authorized owner, Hatchet run/step ID, observed timestamp, intended schedule bucket, objective-rule inputs and outputs, read-only tool names, source/content fingerprint, checkpoint identity, exact completion/pause/blocked status, model token and authoritative cost if available, and **whether the evidence was independently verified**.

Objective grades: threshold detection precision/recall, dedupe count, zero replay after uncertain effects, missed-wake rate, checkpoint recovery, mean/95p latency, USD/call. Expected success of duplicate wake is zero added model calls and one receipt.

Subjective grades: correct identification of user objective, evidence sufficiency, trade-off analysis, calibrated uncertainty, useful recommendation, and approval-boundary compliance. A second LLM can propose a critique, but independent human rubric adjudication must determine the final subjective grade. **Subjective judgments are advice-only during this test**. No automatic external writes, emails, cancellations or purchases.

Safety and cost: production Personal experiments must have an explicitly authorized test user/session, read-only scopes, global and per-goal USD ceilings, and a user-visible cancellation mechanism. Model calls must stop on quota exhaustion and store a paused state without replay. Revalidate authority on every wake. No blanket retries of unknown side effects.

## Test stages

- **Stage 0 (implemented CI fixtures)**: multi-wake PostgreSQL state, deterministic health thresholds, simulated MCP responses, worker reconstruction, and forced 502/in-flight state persistence. Artificial clock advances are not actual recurrence.
- **Stage 1 (requires trusted operator activation)**: Hatchet worker image running current code, schema migration, signed user-approved goal creation, bounded model budget, real two/three-wake dispatch and evidence capture. No automatic schedule.
- **Stage 2 (real horizon)**: an explicitly authorized recurring Hatchet schedule, at least 12 distinct real 5-minute observation buckets, controlled restart, controlled revocation, budget pause/resume, objective score and independently adjudicated subjective decisions.

Do not claim Stage 1 or Stage 2 passed from unit tests or a green Railway deployment.
