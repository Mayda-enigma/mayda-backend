import argparse
import asyncio
import sys
from typing import Sequence

from app.cli.create_admin import run_create_admin


async def run_cli(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("create-admin", help="Create an admin user")

    parsed, remainder = parser.parse_known_args(args_list)
    if parsed.command == "create-admin":
        return await run_create_admin(remainder)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_cli()))
