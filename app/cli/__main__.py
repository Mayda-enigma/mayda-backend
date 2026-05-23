"""Entry point for `python -m app.cli <command>`."""

import argparse
import asyncio
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Mayda backend administration CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-admin sub-command
    ca = subparsers.add_parser("create-admin", help="Create an admin user")
    ca.add_argument("--email", required=True, help="Admin email address")
    ca.add_argument("--phone", required=True, type=int, help="Admin phone number")
    ca.add_argument("--first-name", default="Admin", help="First name (default: Admin)")
    ca.add_argument("--last-name", default="User", help="Last name (default: User)")
    ca.add_argument("--password", required=True, help="Password (min 6 chars)")

    args = parser.parse_args()

    if args.command == "create-admin":
        if len(args.password) < 6:
            print("Error: Password must be at least 6 characters long.")
            sys.exit(1)

        from app.cli.create_admin import create_admin_user

        success = asyncio.run(
            create_admin_user(
                email=args.email,
                phone=args.phone,
                first_name=args.first_name,
                last_name=args.last_name,
                password=args.password,
            )
        )
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
