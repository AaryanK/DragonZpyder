from __future__ import annotations

import argparse
from getpass import getpass
import json
from uuid import uuid4

from . import __version__
from .client import (
    DragonZpyderAuthError,
    DragonZpyderClient,
    DragonZpyderClientError,
)
from .config import ConfigError, DragonZpyderConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dragonzpyder",
        description=(
            "DragonZpyder Personal client for Operly's governed runtime. "
            "Legacy desktop automation is disabled."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "config-check",
        help="Validate the configured Operly endpoint without making a request.",
    )

    login = subparsers.add_parser("login", help="Sign in and obtain a Personal-only Operly session.")
    login.add_argument("--email", help="Operly account email. Prompted when omitted.")

    subparsers.add_parser("logout", help="Revoke the current Operly session and delete local cookies.")
    subparsers.add_parser("status", help="Show the current Personal session status.")

    submit = subparsers.add_parser("submit", help="Submit a retry-safe Personal task.")
    submit.add_argument("message", nargs="+", help="Task text.")
    submit.add_argument("--conversation", help="Continue an existing Personal conversation.")
    submit.add_argument(
        "--request-id",
        help="Stable retry ID. Reuse this exact value after a timeout or lost response.",
    )

    approvals = subparsers.add_parser("approvals", help="Show pending Personal approvals.")
    approvals.set_defaults(command="approvals")

    approve = subparsers.add_parser(
        "approve",
        help="Approve and immediately execute the exact reviewed Personal action.",
    )
    approve.add_argument("approval_id")

    reject = subparsers.add_parser("reject", help="Reject one pending Personal action.")
    reject.add_argument("approval_id")

    resume = subparsers.add_parser(
        "resume",
        help="Resume an already-approved action after a client/network interruption.",
    )
    resume.add_argument("approval_id")

    return parser


def _client() -> DragonZpyderClient:
    return DragonZpyderClient(DragonZpyderConfig.from_env())


def _print_status(status: dict) -> None:
    print("Signed in to Operly Personal")
    if status.get("device"):
        print(f"Device: {status['device']}")
    if status.get("expires_at"):
        print(f"Session expires: {status['expires_at']}")


def _print_submission(result: dict) -> None:
    approval_id = result.get("approval_id")
    blocker = result.get("error_code")
    if approval_id:
        print("Status: waiting for approval")
    elif blocker:
        print("Status: blocked")
    else:
        print("Status: complete")

    message = str(result.get("message") or "").strip()
    if message:
        print(f"Result: {message}")
    if blocker:
        print(f"Blocker: {blocker}")
    if approval_id:
        print(f"Approval ID: {approval_id}")
        print(f"Next: dragonzpyder approvals")
    if result.get("conversation_id"):
        print(f"Conversation: {result['conversation_id']}")
    if result.get("client_request_id"):
        print(f"Request ID: {result['client_request_id']}")
    if result.get("replayed"):
        print("Safe retry replay: yes")


def _print_execution(result: dict) -> None:
    print("Status: complete")
    payload = result.get("result") if isinstance(result.get("result"), dict) else {}
    if payload.get("verification_status"):
        print(f"Verification: {payload['verification_status']}")
    if payload.get("message_id"):
        print(f"Provider message ID: {payload['message_id']}")
    if payload.get("rfc822_message_id"):
        print(f"Stable message identity: {payload['rfc822_message_id']}")


def _approval_arguments(row: dict) -> dict:
    raw = row.get("arguments")
    return dict(raw) if isinstance(raw, dict) else {}


def _print_approvals(rows: tuple[dict, ...]) -> None:
    if not rows:
        print("No pending Personal approvals.")
        return
    for row in rows:
        print(f"Approval ID: {row.get('id', '<unknown>')}")
        arguments = _approval_arguments(row)
        if arguments:
            print("Proposed action (exact reviewed content):")
            for key, value in sorted(arguments.items()):
                rendered = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
                print(f"  {key}: {rendered}")
        if row.get("arguments_hash"):
            print(f"Review hash: {row['arguments_hash']}")
        if row.get("expires_at"):
            print(f"Approval expires: {row['expires_at']}")
        print(f"Decision: {row.get('status') or 'pending'}")
        print()


def _error(exc: DragonZpyderClientError, *, request_id: str | None = None) -> int:
    if isinstance(exc, DragonZpyderAuthError):
        print(f"Authentication required: {exc}")
        print("Run: dragonzpyder login")
        return 3
    print(f"DragonZpyder stopped: {exc}")
    if exc.code:
        print(f"Blocker: {exc.code}")
    if exc.code == "execution_outcome_uncertain":
        stable_id = str(exc.details.get("rfc822_message_id") or "").strip()
        if stable_id:
            print(f"Stable message identity: {stable_id}")
        print("Delivery may already have happened. Do not send again until this identity is reconciled.")
        recovery = str(exc.details.get("recovery") or "").strip()
        if recovery:
            print(f"Recovery: {recovery}")
        return 5
    if request_id and exc.retryable:
        print(f"Retry with the same request ID: {request_id}")
    return 4 if exc.retryable else 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "config-check":
        try:
            config = DragonZpyderConfig.from_env()
        except ConfigError as exc:
            parser.exit(2, f"configuration error: {exc}\n")
        print(json.dumps({"configured": True, "operly_base_url": config.operly_base_url}))
        return 0

    try:
        client = _client()
    except ConfigError as exc:
        parser.exit(2, f"configuration error: {exc}\n")

    try:
        if args.command == "login":
            email = (args.email or input("Operly email: ")).strip()
            password = getpass("Operly password: ")
            status = dict(client.login(email=email, password=password))
            _print_status(status)
            return 0

        if args.command == "logout":
            client.logout()
            print("Signed out. The Operly session was revoked and local cookies were removed.")
            return 0

        if args.command == "status":
            _print_status(dict(client.status()))
            return 0

        if args.command == "submit":
            request_id = str(args.request_id or uuid4())
            # Print the stable identity before crossing the network boundary. If the
            # response is lost, the user still has the exact ID required for a safe retry.
            print(f"Request ID: {request_id}")
            try:
                result = dict(
                    client.submit(
                        " ".join(args.message),
                        conversation_id=args.conversation,
                        request_id=request_id,
                    )
                )
            except DragonZpyderClientError as exc:
                return _error(exc, request_id=request_id)
            _print_submission(result)
            return 0

        if args.command == "approvals":
            rows = tuple(dict(row) for row in client.pending_approvals())
            _print_approvals(rows)
            return 0

        if args.command == "approve":
            approved, result = client.approve_and_execute(args.approval_id)
            print(f"Approval {approved.get('id') or args.approval_id}: approved")
            _print_execution(dict(result))
            return 0

        if args.command == "reject":
            row = dict(client.decide_approval(args.approval_id, approved=False))
            print(f"Approval {args.approval_id}: {row.get('status') or 'denied'}")
            return 0

        if args.command == "resume":
            result = dict(client.resume_approved(args.approval_id))
            _print_execution(result)
            return 0

    except DragonZpyderClientError as exc:
        return _error(exc)

    parser.error(f"unsupported command: {args.command}")
    return 2
