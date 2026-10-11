"""Run the agent team on tickets from the command line.

    .venv/bin/python backend/run_team.py 101          # one ticket
    .venv/bin/python backend/run_team.py 101 102 103  # several, in order
    .venv/bin/python backend/run_team.py --all        # every open ticket
"""

import argparse
import asyncio
import json

from team import Team


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team.")
    parser.add_argument("tickets", nargs="*", type=int)
    parser.add_argument("--all", action="store_true", help="work every open ticket")
    args = parser.parse_args()

    async with Team() as team:
        ids = args.tickets
        if args.all:
            listing = await team.mcp.direct_call_tool("list_open_tickets", {})
            ids = [t["id"] for t in listing["tickets"]]
        if not ids:
            parser.error("give ticket ids or --all")
        for ticket_id in ids:
            result = await team.run_ticket(ticket_id)
            print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
