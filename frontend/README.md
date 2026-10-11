# Campus Customs · Command Bridge (React + Vite + TypeScript)

The human desk for the Campus Customs agent team. Pick a ticket, dispatch the agent council, watch each agent work live, approve or reject what they propose, and see the checking balance move.

```bash
npm install        # first time only
npm run dev        # opens http://localhost:5173 in your browser
```

The backend must be running first (from `../backend`: `../.venv/bin/uvicorn main:app --reload --port 8000`).
The API address is set in `.env` (`VITE_API_BASE=http://localhost:8000`).

- `src/api.ts`: typed client for every backend route
- `src/derive.ts`: turns audit events into agent status, the feed and the debrief
- `src/agents.tsx`: agent identities (council titles, colors, emblems)
- `src/components/`: TopBar, SaberToggle, TicketBoard, MissionBriefing, CouncilRoster, TransmissionFeed, ApprovalQueue, Debrief, CashPanel, Crawl
- `src/index.css`: Jedi (light/blue) and Sith (dark/red) themes

Design notes: `../output/design.md`.
