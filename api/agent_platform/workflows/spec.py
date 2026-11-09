"""Universal workflow DSL and schedule calendar, owned by DragonZpyder.

Migrated from Operly`s domain-neutral workflow language, kept behavior compatible
while existing business workflows remain readable. Independent of Operly models.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo


MAX_STEPS = 100
MAX_SPEC_BYTES = 512_000
MAX_WAIT_SECONDS = 31 * 24 * 60 * 60
_TEMPLATE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_STEP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


class WorkflowSpecError(ValueError):
    pass


def _json_size(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":"), default=str).encode("utf-8"))


def validate_workflow_spec(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowSpecError("Workflow spec must be an object")
    if _json_size(value) > MAX_SPEC_BYTES:
        raise WorkflowSpecError("Workflow spec is too large")
    raw_steps = value.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise WorkflowSpecError("Workflow needs at least one step")
    if len(raw_steps) > MAX_STEPS:
        raise WorkflowSpecError(f"Workflow supports at most {MAX_STEPS} steps")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            raise WorkflowSpecError(f"Step {index + 1} must be an object")
        step_id = str(raw.get("id") or f"step_{index + 1}").strip()
        if not _STEP_ID.fullmatch(step_id):
            raise WorkflowSpecError(f"Invalid step id: {step_id}")
        if step_id in seen:
            raise WorkflowSpecError(f"Duplicate step id: {step_id}")

        # Dependency edges are deliberately backward-only. This makes the graph a
        # deterministic DAG without needing a separate topological-sort phase and
        # rejects self-dependency before the current id is added to ``seen``.
        depends = raw.get("depends_on") or []
        if not isinstance(depends, list):
            raise WorkflowSpecError(f"Step {step_id} depends_on must be an array")
        normalized_depends = [str(item) for item in depends]
        if any(item not in seen for item in normalized_depends):
            raise WorkflowSpecError(f"Step {step_id} may only depend on earlier step ids")
        if len(set(normalized_depends)) != len(normalized_depends):
            raise WorkflowSpecError(f"Step {step_id} contains duplicate dependencies")

        kind = str(raw.get("kind") or "action").strip().lower()
        if kind not in {"action", "wait"}:
            raise WorkflowSpecError(f"Unsupported step kind: {kind}")
        on_error = str(raw.get("on_error") or "stop").strip().lower()
        if on_error not in {"stop", "continue"}:
            raise WorkflowSpecError(f"Step {step_id} on_error must be stop or continue")

        step: dict[str, Any] = {
            "id": step_id,
            "kind": kind,
            "depends_on": normalized_depends,
            "on_error": on_error,
        }
        if "when" in raw:
            validate_condition(raw["when"])
            step["when"] = raw["when"]

        if kind == "action":
            capability_id = str(raw.get("capability_id") or "").strip().lower()
            if not capability_id:
                raise WorkflowSpecError(f"Step {step_id} requires capability_id")
            if capability_id.startswith("workflow."):
                raise WorkflowSpecError("Workflow recursion/self-modification is not enabled")
            arguments = raw.get("arguments") or {}
            if not isinstance(arguments, dict):
                raise WorkflowSpecError(f"Step {step_id} arguments must be an object")
            step["capability_id"] = capability_id
            step["arguments"] = arguments
        else:
            has_seconds = "seconds" in raw
            has_until = "until" in raw
            if has_seconds == has_until:
                raise WorkflowSpecError(
                    f"Wait step {step_id} needs exactly one of seconds or until"
                )
            if has_seconds:
                try:
                    seconds = int(raw["seconds"])
                except (TypeError, ValueError) as error:
                    raise WorkflowSpecError(
                        f"Wait step {step_id} seconds must be an integer"
                    ) from error
                if seconds < 1 or seconds > MAX_WAIT_SECONDS:
                    raise WorkflowSpecError(f"Wait step {step_id} seconds is outside policy")
                step["seconds"] = seconds
            else:
                until = raw["until"]
                if not isinstance(until, str) or not until.strip():
                    raise WorkflowSpecError(
                        f"Wait step {step_id} until must be an ISO time or template"
                    )
                step["until"] = until.strip()

        normalized.append(step)
        seen.add(step_id)
    return {"steps": normalized}


def validate_condition(value: Any) -> None:
    if not isinstance(value, dict):
        raise WorkflowSpecError("Step condition must be an object")
    has_all = "all" in value
    has_any = "any" in value
    if has_all and has_any:
        raise WorkflowSpecError("Condition cannot contain both all and any")
    if has_all or has_any:
        key = "all" if has_all else "any"
        children = value.get(key)
        if not isinstance(children, list) or not children:
            raise WorkflowSpecError(f"Condition {key} must contain conditions")
        for child in children:
            validate_condition(child)
        return
    ref = str(value.get("ref") or "").strip()
    op = str(value.get("op") or "truthy").strip().lower()
    if not ref:
        raise WorkflowSpecError("Condition ref is required")
    if op not in {
        "truthy",
        "exists",
        "eq",
        "ne",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "not_in",
    }:
        raise WorkflowSpecError(f"Unsupported condition operator: {op}")


def _path_value(context: Any, reference: str) -> Any:
    current = context
    for part in str(reference).split("."):
        if isinstance(current, dict):
            if part not in current:
                raise WorkflowSpecError(f"Template reference is unavailable: {reference}")
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                raise WorkflowSpecError(f"Template index is unavailable: {reference}")
            current = current[index]
        else:
            raise WorkflowSpecError(f"Template reference is unavailable: {reference}")
    return current


def render_value(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {str(key): render_value(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [render_value(item, context) for item in value]
    if not isinstance(value, str):
        return value
    full = _TEMPLATE.fullmatch(value)
    if full:
        return _path_value(context, full.group(1))

    def substitute(match: re.Match[str]) -> str:
        resolved = _path_value(context, match.group(1))
        if isinstance(resolved, (dict, list)):
            return json.dumps(resolved, separators=(",", ":"), default=str)
        return "" if resolved is None else str(resolved)

    return _TEMPLATE.sub(substitute, value)


def evaluate_condition(condition: Any, context: dict[str, Any]) -> bool:
    if not isinstance(condition, dict):
        return bool(condition)
    if "all" in condition:
        return all(evaluate_condition(item, context) for item in condition["all"])
    if "any" in condition:
        return any(evaluate_condition(item, context) for item in condition["any"])
    try:
        actual = _path_value(context, str(condition.get("ref") or ""))
        exists = True
    except WorkflowSpecError:
        actual = None
        exists = False
    op = str(condition.get("op") or "truthy").lower()
    expected = render_value(condition.get("value"), context)
    if op == "exists":
        return exists
    if op == "truthy":
        return bool(actual) if exists else False
    if not exists:
        return op == "ne"
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    try:
        if op == "gt":
            return actual > expected
        if op == "gte":
            return actual >= expected
        if op == "lt":
            return actual < expected
        if op == "lte":
            return actual <= expected
        if op == "in":
            return actual in expected if isinstance(expected, (list, tuple, set, str)) else False
        if op == "not_in":
            return actual not in expected if isinstance(expected, (list, tuple, set, str)) else True
    except TypeError as error:
        raise WorkflowSpecError("Condition values cannot be compared") from error
    return False


def validate_schedule(value: Any) -> dict[str, Any] | None:
    if value in (None, {}, ""):
        return None
    if not isinstance(value, dict):
        raise WorkflowSpecError("Schedule must be an object")
    schedule_type = str(value.get("type") or "manual").strip().lower()
    if schedule_type == "manual":
        return None
    timezone_name = str(value.get("timezone") or "UTC").strip()
    try:
        ZoneInfo(timezone_name)
    except Exception as error:
        raise WorkflowSpecError("Unknown schedule timezone") from error
    result: dict[str, Any] = {"type": schedule_type, "timezone": timezone_name}
    if schedule_type == "once":
        result["at"] = _iso_datetime(value.get("at")).isoformat()
    elif schedule_type == "interval":
        try:
            every = int(value.get("every_seconds") or 0)
        except (TypeError, ValueError) as error:
            raise WorkflowSpecError("Interval seconds must be an integer") from error
        if every < 60 or every > 365 * 24 * 60 * 60:
            raise WorkflowSpecError("Interval must be between 60 seconds and one year")
        result["every_seconds"] = every
        if value.get("start_at"):
            result["start_at"] = _iso_datetime(value["start_at"]).isoformat()
    elif schedule_type == "daily":
        result["time"] = _clock(value.get("time"))
    elif schedule_type == "weekly":
        days = value.get("days")
        if not isinstance(days, list) or not days:
            raise WorkflowSpecError("Weekly schedule needs days")
        try:
            normalized_days = sorted({int(day) for day in days})
        except (TypeError, ValueError) as error:
            raise WorkflowSpecError("Weekly days must be integers") from error
        if any(day < 0 or day > 6 for day in normalized_days):
            raise WorkflowSpecError("Weekly days use 0=Monday through 6=Sunday")
        result["days"] = normalized_days
        result["time"] = _clock(value.get("time"))
    elif schedule_type == "cron":
        expression = str(value.get("expression") or "").strip()
        _parse_cron(expression)
        result["expression"] = expression
    else:
        raise WorkflowSpecError(
            "Schedule type must be once, interval, daily, weekly, cron, or manual"
        )
    return result


def _iso_datetime(value: Any) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise WorkflowSpecError("Schedule date/time is required")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise WorkflowSpecError("Schedule date/time must be ISO 8601") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _clock(value: Any) -> str:
    raw = str(value or "").strip()
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", raw):
        raise WorkflowSpecError("Schedule time must be HH:MM")
    return raw


def next_schedule_time(schedule: dict[str, Any], *, after: datetime) -> datetime | None:
    schedule = validate_schedule(schedule) or {}
    schedule_type = schedule.get("type")
    if not schedule_type:
        return None
    after = after.replace(tzinfo=None)
    if schedule_type == "once":
        at = _iso_datetime(schedule["at"])
        return at if at > after else None
    if schedule_type == "interval":
        every = int(schedule["every_seconds"])
        start = _iso_datetime(schedule["start_at"]) if schedule.get("start_at") else after
        if start > after:
            return start
        elapsed = max(0, int((after - start).total_seconds()))
        return start + timedelta(seconds=((elapsed // every) + 1) * every)

    zone = ZoneInfo(str(schedule.get("timezone") or "UTC"))
    local_after = after.replace(tzinfo=timezone.utc).astimezone(zone)
    if schedule_type in {"daily", "weekly"}:
        hour, minute = [int(part) for part in str(schedule["time"]).split(":")]
        days = set(schedule.get("days") or range(7))
        for offset in range(0, 9):
            candidate_date = (local_after + timedelta(days=offset)).date()
            if candidate_date.weekday() not in days:
                continue
            candidate = datetime(
                candidate_date.year,
                candidate_date.month,
                candidate_date.day,
                hour,
                minute,
                tzinfo=zone,
            )
            if candidate > local_after:
                return candidate.astimezone(timezone.utc).replace(tzinfo=None)
        return None

    fields = _parse_cron(str(schedule["expression"]))
    candidate = local_after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(527_040):
        if _cron_matches(candidate, fields):
            return candidate.astimezone(timezone.utc).replace(tzinfo=None)
        candidate += timedelta(minutes=1)
    raise WorkflowSpecError("Cron schedule did not produce a time within one year")


def _parse_cron(
    expression: str,
) -> tuple[set[int], set[int], set[int], set[int], set[int], bool, bool]:
    parts = expression.split()
    if len(parts) != 5:
        raise WorkflowSpecError(
            "Cron expression must have 5 fields: minute hour day month weekday"
        )
    minute = _cron_values(parts[0], 0, 59)
    hour = _cron_values(parts[1], 0, 23)
    day = _cron_values(parts[2], 1, 31)
    month = _cron_values(parts[3], 1, 12)
    weekday_raw = _cron_values(parts[4], 0, 7)
    weekday = {0 if item == 7 else item for item in weekday_raw}
    return minute, hour, day, month, weekday, parts[2] == "*", parts[4] == "*"


def _cron_values(token: str, minimum: int, maximum: int) -> set[int]:
    values: set[int] = set()
    try:
        for segment in token.split(","):
            step = 1
            base = segment
            if "/" in segment:
                base, raw_step = segment.split("/", 1)
                step = int(raw_step)
                if step < 1:
                    raise WorkflowSpecError("Cron step must be positive")
            if base == "*":
                start, end = minimum, maximum
            elif "-" in base:
                raw_start, raw_end = base.split("-", 1)
                start, end = int(raw_start), int(raw_end)
            else:
                start = end = int(base)
            if start < minimum or end > maximum or start > end:
                raise WorkflowSpecError("Cron field is outside its allowed range")
            values.update(range(start, end + 1, step))
    except ValueError as error:
        raise WorkflowSpecError("Cron field must contain integers, ranges, *, or steps") from error
    return values


def _cron_matches(
    candidate: datetime,
    fields: tuple[set[int], set[int], set[int], set[int], set[int], bool, bool],
) -> bool:
    minute, hour, day, month, weekday, day_any, weekday_any = fields
    cron_weekday = (candidate.weekday() + 1) % 7
    if candidate.minute not in minute or candidate.hour not in hour or candidate.month not in month:
        return False
    day_match = candidate.day in day
    weekday_match = cron_weekday in weekday
    if not day_any and not weekday_any:
        return day_match or weekday_match
    return day_match and weekday_match
