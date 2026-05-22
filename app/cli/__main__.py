import asyncio
import sys
from typing import Sequence

from app.cli.create_admin import run_create_admin


def print_help() -> None:
    print("usage: python -m app.cli create-admin [options]")
    print("commands:")
    print("  create-admin  --email <email> --password <password> [--phone ...]")


async def run_cli(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list or args_list[0] in {"-h", "--help"}:
        print_help()
        return 0

    if args_list and args_list[0] == "create-admin":
        return await run_create_admin(args_list[1:])

    print(f"Unknown command: {args_list[0]}")
    print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_cli()))
