from __future__ import annotations

import argparse
import json

from . import __version__
from .config import ConfigError, DragonZpyderConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dragonzpyder",
        description="DragonZpyder personal client shell. Legacy desktop automation is disabled.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "config-check",
        help="Validate the configured Operly endpoint without making a request.",
    )
    return parser


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

    parser.error(f"unsupported command: {args.command}")
    return 2
