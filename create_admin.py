import asyncio
from app.cli.create_admin import run_create_admin


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(run_create_admin()))
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
