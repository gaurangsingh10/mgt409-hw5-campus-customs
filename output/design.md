# Campus Customs Command Bridge: Design Notes

The dashboard (`frontend/`, React + Vite + TypeScript) is the desk where a human sits with the agent team. The brief asked for a Star Wars feel: **Jedi** (light mode, blue accent) and **Sith** (dark mode, red accent). I built the whole desk around one idea:

> **The agents are a council you command from a starship bridge. They investigate and propose. You hold the seal.**

That metaphor isn't decoration. It matches how the system really works. Agents can't move money, so the UI makes approval feel like a deliberate act ("Awaiting Your Seal") instead of a checkbox.

---

## 1. Layout: a three-station bridge

```
+--------------------------------------------------------------------------------------+
| * CAMPUS CUSTOMS  COMMAND BRIDGE    o Uplink   [3 awaiting your seal]   Officer [___]   |
|                                     > Crawl   Reset   JEDI ===[saber]=====          |
+------------------+----------------------------------------+--------------------------+
| MISSION BOARD    | MISSION BRIEFING                       | AWAITING YOUR SEAL       |
|  #101  Open      |  "Needs a tee in size S." - Tauhid     |  * Pay rent    $2,400    |
|  #102  RESOLVED  |                [ DISPATCH THE COUNCIL ]|    Checking after $1,000 |
|  #103  Open      +----------------------------------------+    [Approve & pay][Rej.] |
|                  | [CMD] [QM] [TRS] [HGR] [PRT]  <- seats |  * Customer reply        |
| TREASURY VAULT   +----------------------------------------+    (letter preview)      |
|  $3,400.00       | TRANSMISSIONS                 o Live   +--------------------------+
|  [#######--|--]  |  CMD > QM  check_stock(CC-TEE-WHITE,S) | COUNCIL DEBRIEF          |
|   floor  after   |  Council Master --> Treasury Droid     |  one card per agent      |
|  Ledger          |  Treasury Droid reports ...            |  "Not called: ..."       |
+------------------+----------------------------------------+--------------------------+
```

| Station | What lives there | Why |
|---|---|---|
| **Left: Mission Board + Treasury Vault** | The three tickets as "holocards", plus the checking balance | The two things you glance at all day: *what's open* and *how much money we have*. Both stay pinned (sticky) while the middle scrolls. |
| **Center: Briefing → Council → Transmissions** | The selected ticket, the big **Dispatch the Council** button, five agent "seats", and the live feed | Reads top to bottom like the run itself: the order comes in, the council lights up, the transmissions scroll. Your eyes never leave the center while the run happens. |
| **Right: Awaiting Your Seal + Council Debrief** | Approval cards, then a summary card per agent | Decisions sit on the right-hand side, closest to where your hand already is. The debrief is directly below, so you can read *why* before approving *what*. |

Under 1120px the stations stack (tickets → mission → approvals), so it still works on a laptop split-screen.

---

## 2. How each agent reads differently

Each agent is a character with its own **council title, color and emblem**. I drew the emblems as simple original SVG geometry, so there are no borrowed logos.

| Agent | Council title | Callsign | Color (Jedi / Sith) | Emblem |
|---|---|---|---|---|
| boss | **Council Master** | CMD | gold `#b07d05` / `#f3c64a` | council seal (ring + four rays) |
| inventory | **Quartermaster** | QM | green `#138a5e` / `#3fdb98` | stacked crates |
| accounting | **Treasury Droid** | TRS | violet `#6d43e8` / `#a98cff` | hex credit chip with a $ |
| facilities | **Hangar Chief** | HGR | teal `#0b8ea4` / `#3fd2e3` | hangar arch |
| customer_service | **Protocol Droid** | PRT | rose `#c93a72` / `#ff72a8` | transmission diamond |

The agent colors are deliberately **not** blue or red. Blue and red belong to the theme (Jedi/Sith accent), and the agents keep their own colors in both modes. You learn "gold = boss, violet = money" once, and it holds when you flip sides.

Where the identity shows up:
- **Council seats:** a colored top edge, the emblem in a tinted circle, and a status light that behaves differently per state:
  - *Summoned / Thinking*: slow blink.
  - *Using tools*: the seat lifts, glows in the agent's color and the emblem pulses. The seat shows the actual tool call, e.g. `check_stock(CC-TEE-WHITE, S)`.
  - *Waiting*: dimmed light, plus who they're waiting on ("Waiting on Quartermaster").
  - *Reported*: a steady green light, plus the agent's one-line summary.
  - *Not called*: the seat fades with a dashed edge. This makes routing visible at a glance: on ticket 102 only two seats light up, which is exactly the Problem 6 plan.
- **Transmissions:** every entry has the agent's color bar on the left, the emblem, the title and a **channel label** like `CMD ▸ TRS` showing the delegation path. Delegated work is **indented** by depth, so a nested chain looks like a tree.
  - Tool calls are monospace chips: ⚙ for MCP lookups, ↗ for delegations, ✦ for approval requests.
  - Raw tool results are folded under "N results received" so the feed stays readable, but they're one click away for auditing.
- **Delegations:** these appear as a "hyperspace jump": a glowing vertical line fading from the accent color into the receiving agent's color, labelled `Council Master ⟶ Treasury Droid`, with the task text underneath.
- **Reports:** a card tinted in the agent's color, listing each approval it filed (`✦ #2 Bulk discount · $986`).

---

## 3. Resolved tickets

- **Holocards** show a status pill (*Open → Council in session → Resolved*).
  - While a run is going, a light **scan line** sweeps across that card. You can watch another ticket and still see which one the council is working.
  - When the run finishes, a rotated **"RESOLVED" stamp** slams onto the card: it scales down from 2.6× with a little overshoot. The type label hides under it, and the card's text dims.
- A three-segment **progress bar** at the top of the board fills green per resolved ticket ("2/3 resolved").
- The **Dispatch** button turns into "Mission complete" and is disabled, and the briefing says the ticket is resolved and points you to *Awaiting Your Seal*.
- Resolution rule: the backend marks a ticket resolved **when a run you started finishes**, as the brief asked. That's done by the API, never by an agent. Money still needs your seal: any approvals stay in the queue after the ticket is resolved, so "resolved" means "the council has done its work", not "money moved".

---

## 4. Cash: the Treasury Vault

- **Big balance readout** in Orbitron with tabular numbers, so digits don't jump around.
- When you approve a payment, the number **counts down** to the new balance over about a second (eased), and a **−$2,400.00** flashes beside it and fades upward. Money leaving should *feel* like money leaving.
- **Gauge**: the bar fills with the accent gradient and shrinks with the balance. It has a red tick at the **$500 cash floor** and a hollow amber marker at **cash after all bills** (the $160 squeeze). You can see how close to the edge the shop is without reading a number. Under the floor, the balance turns amber.
- **Ledger** lists each approved payment as it happens ("Pay rent #1 · Gaurang −$2,400.00"), so the drop is always explained.
- **Before you approve**, every money card shows **"Checking after: $X"**. It turns amber below the floor and red with the button disabled if it would overdraw. The backend refuses overdrafts too; the UI just tells you first.

---

## 5. Approvals: "Awaiting Your Seal"

- One card per proposal: the requesting agent (in its color), the kind (*Pay rent, Pay vendor invoice, Restock purchase, Bulk discount, Customer reply*), a big amount, and the agent's reasoning.
  - Price overrides show the math: `20 × $49.30 = $986.00`.
- **Customer replies are shown as a letter** in a serif face, on a paper-white panel, so you read it the way the customer will before you approve it.
- Money cards **breathe**: a slow pulsing outline, because an unpaid decision should feel slightly urgent but not alarming.
- **Desk officer sign-in** in the top bar. Every decision is recorded with a human name (`approved_by` in `payments`). If you try to approve without a name, the field shakes and turns red instead of failing silently. The name persists in localStorage.
- A pill in the top bar counts everything "awaiting your seal" across all tickets, and glows in the accent color when non-zero. A *This ticket / All* toggle switches the queue's scope.

---

## 6. Jedi vs Sith

| | **Jedi** (light) | **Sith** (dark) |
|---|---|---|
| Background | pale holotable blue with a faint blueprint grid and a soft sky-blue glow | deep space: a slowly drifting starfield with a red nebula in the corners |
| Accent | saber blue `#1f7aff` | saber red `#ff2b3d` |
| Panels | frosted white glass | smoked glass |
| Mood | calm, clean, daylight ops | focused, late-night ops |

- **The theme switch is a lightsaber.** A metal hilt and a glowing blade. Clicking it retracts the blade and re-ignites it in the other color (scaleX from the hilt with a slight overshoot), with a gentle hum (brightness pulse). It defaults to your OS light/dark setting and remembers your choice.
- Everything accent-colored follows the side you chose: the Dispatch button, the selected ticket, delegation lines, live tags, approve buttons and the vault gauge.

---

## 7. The small things that make it a desk people enjoy

- **Opening crawl.** The first time you open the desk each session, an original perspective crawl rolls by: *"Not so long ago, on a campus not so far away… Episode 101: THE THREE TICKETS"*. It sets up the real situation ($3,400 in the vault, an overdue invoice, rent in two days, three requests), so you know what's at stake before you click anything. Skip with a click, Esc or Enter, and replay it from **▶ Crawl** in the top bar.
- **Dispatch the Council** has a slow rotating sheen; during a run it spins faster and the briefing gets an accent glow.
- **Hyperdrive bar** while the run is going: animated stripes, plus live T+ elapsed time, model calls and tokens, so waiting 30–60 s feels like watching something happen, not a frozen spinner. Token use is visible on purpose: it's a cost.
- **Typing dots** at the bottom of the feed while agents are working; the feed auto-scrolls during a live run.
- **Uplink light** (green pulse = backend online, plus the model name). If the backend is down, a clear banner tells you the exact command to start it.
- **Toasts** narrate outcomes in plain English: "Paid $2,400.00. Checking $3,400.00 → $1,000.00." Warnings (like dropping under the floor) get their own amber toast.
- **Council Debrief** ends with "Not called: Hangar Chief", which makes the comparison with the Problem 6 plan obvious.
- **Reset** (⟲) asks for confirmation and says what it wipes; the audit trail is always kept.
- **Respectful motion:** everything animated turns off under `prefers-reduced-motion`. The crawl becomes static text and the balance updates instantly.
- **Fonts:** Orbitron for headings and numbers (sci-fi, but readable), Inter for body text, JetBrains Mono for tool calls. All are free Google Fonts, with system fonts as fallback.

---

## 8. How it talks to the backend

- Base URL `http://localhost:8000` (`frontend/.env` → `VITE_API_BASE`). The backend's CORS allows `http://localhost:5173` (and other localhost ports in case Vite picks another).
- Every 4 s the board refreshes `/api/tickets`, `/api/cash`, `/api/approvals?status=all` and `/api/health`.
- **Dispatch** → `POST /api/tickets/{id}/run`. While it runs, the board polls `/api/events?ticket_id={id}&since={ts}` every 1.2 s and rebuilds the seats, feed and debrief from the audit trail.
- If you reload mid-run, the board sees `running_ticket` and reconnects to the live feed.
- **Approve / Reject** → `POST /api/approvals/{id}/approve|reject` with the desk officer's name, then refreshes cash.
- **Reset** → `POST /api/reset`.

Verified end-to-end in the browser:
- Ran 102: only the Council Master and Hangar Chief lit up, and the ticket was stamped RESOLVED.
- Approved the $2,400 rent: the vault counted down $3,400 → $1,000, and the ledger and gauge updated.
- Ran 103 and captured it mid-run: the live feed showed seat states changing and proposals arriving in the queue before the run finished.
- No console errors.
