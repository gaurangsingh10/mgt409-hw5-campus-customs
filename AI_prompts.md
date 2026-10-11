# AI Prompts Log — HW5 (Campus Customs Multi-Agent Operations)

A record of the prompts I sent to Claude Code while working on this assignment.

---

## Problem 1 — Unzip the data & set up the AI prompt log

**Prompts:**
1. "Alright we will be working in the HW5 folder today. the goal is to create campus customs multi-agent operations - an agentic team that run the shop. We will build a MCP server, a FastAPI backend with a multi-agent team, and a React dashboard so a human can wathc the agents at work and approve requests. We will build a  boss agent, an inventory agent, accounting , facilities, and customer service. Look at the zip file in HW5 folder and unzip it to get the data. Create AI_prompts.md and keep it updated as we work. It is a log of what i have typed into ths chat. Put one section for each problem, and each section must contain the problem number and title, at least one prompt you types and one-follow up prompt (if needed). - this is. problem 1"

**Follow-up needed:** None.

---

## Problem 2 — Explore the database, make a working copy & start the harness

**Prompts:**
1. "let's start problem 2. open data/campus_customs.db and look through every table and it's fields. Copy the original file to data/campus_customs_new.db - later problems update that working copy. Study the three open tickets so you can see how they link to other tables Start the output/harness.md and for each table list the fields and one short line on why that table matters for the agents. You will keep growing this harness file in later problems"

**Follow-up needed:** None.

---

## Problem 3 — Build the MCP server with three ticket tools

**Prompts:**
1. "let's start problem 3 write an MCP server in mcp_server/ using FastMCP . It will talk to data/campus_customs_new.db and you do not need to connect or run it in this problem. Every agent in this HW uses the tools in this MCP server. You will add more tools to it later, for now write three tools that we will need for tickets in the database. Keep names clear and never invent any data, only use information in the database. In output/harness.md list each of the three mcp tools. For every tool include the table it reads , which ticket it helps unlock (101, 102 or 103) and one sentence on why that tool i the right one for the ticket. don't write vague lines like \"reads inventory\" - try to tie the tool to the ticket. Also add a short mcp_server/README.md file that explains what the MCP server is for, which database file it uses, and the three tools it has"

**Follow-up needed:** None.

---

## Problem 4 — Connect the MCP server & smoke-test the tools

**Prompts:**
1. "let's start problem 4 - now add the MCP server to this project so that this chat can call the tools. Save the connection JSON text in .mcp.json at the project root (or however your vibe coder saves local MCP server lists). With this connected, test each of the three MCP tools. Save the evidence in output/mcp_smoke.json . for every tool include 1. the prompt 2. the tool name 3. the tool output (must match value in data/campus_customs_new.db)"

**Follow-up needed:** None.

---

## Problem 5 — Build the multi-agent team (pydanticAI) + MCP tools + audit trail

**Prompts:**
1. "Problem 5 - build the agentic team for campus customs using pydanticAI: boss, inventory, accounting, facilities, and customer service.  Include prompts, models, and agents loops so they can delegae work to each other with full connectivity. Put the agent prompts in backend/prompts/ - one file per agent. Put data types in backend/models.py and the agent files under backend/ (your layout can vary as long as the five roles are clear). Use the PORTKEY_API_KEy and only gpt-6-luna for every agent. (get my portkey from lecture 7 folder).  write each prompts in my words with the shop rules that agent needs. These will be detailed prompts that cover all aspects of an agent's work and scope score higher than a short generic prompt. Add any tools the agents need to the MCP server so they can work on the open tickets. Shop facts come from the MCP server over data/campus_customs_new.db - do no invent a second shop-tools layer that bypasses MCP.  Wire the agents so they append to output/audit_trail.json as they run: for each agent-loop step, record enough to audit later. Append to this file - do not wipe it each run. In output/harness.md , list each agent and each MCP tool (including ones you add in this problem) along with which table the tool uses. Also add a short safety section: the guardrails a real business would want when agents touch real customers and real money, plus limits that keep token use in check. Update mcp_server/README.md so the tool list matches what you have now.
why is the request failing ?"

**Follow-up needed:** The question "why is the request failing?" was part of the same message. The first live run failed with a 400 from Azure via Portkey, because gpt-6-luna doesn't allow function tools on `/v1/chat/completions`. Switching the agents to the Responses API (`/v1/responses`) fixed it.

---

## Problem 6 — Write the expected plan per ticket (desk_tickets.html)

**Prompts:**
1. "Problem 6: Now write down the expectations for the team , in terms of what they should do on each ticket. build output/desk_tickets.html - a page that can be double-click with one tab per ticket (101, 102 and 103). Also add empty cash and reflection tab for later problems (leave them blank or with a short \"coming later\" note for now). On each ticker tab, fill an expected section only (leave room for an Actual section you will fill after you run the agents). For each ticket's expected section, write in my words: 1. Who the boss should call first , and why 2. All the agent delegations expected (not that the \"boss calls everyone\") 3. which MCP tools you expect that run to use. Make sure the plan does not send every ticket to every specialist. We will also compare the plan to the actual way the agents resolve the three tickets."

**Follow-up needed:** None.

---

## Problem 7 — FastAPI backend for the dashboard (backend/main.py)

**Prompts:**
1. "Problem 7: now the reach frontend dashboard (next problem) needs a backend it can call in. In backend/main.py, use FastAPI and add routes that do the following: 1. Return the three tickets and whether each is open or resolved 2. Take a ticket id and run your agent team on that ticket 3. Return recent agent events. - what each agent said and which tools they used - so the board can refresh 4. Approve a payment or purchase after a human clicks approve (agents only prepare the pay; this route is what actually changes cash) 5. Return the current checking balance from cash_accounts 6. Reset the database to the original values when you want to try a fresh run . From the backend/ folder, start the server with: uvicorn main:app --reload --port 8000 . This turns on your backend at http://localhost:8000 so the frontend dashboard can call those routes. in output/harness.md , list each route in one line (what URL / what it does)."

**Follow-up needed:** None.

---

## Problem 8 — React dashboard (Star Wars command bridge) + design.md

**Prompts:**
1. "Problem 8: build the React frontend dashboard in frontend/ with React + Vite + TypeScript . the page should call the routes you built in problem 7. At minimum the board should 1. List all three tickets 2. Let you pick one ticket and start the agent team on it 3. Show each agent and what they are saying / doing while the ticket runs 4. mark a ticket resolved when the run finishes 5. show a short summary of what each agent did on that ticket 6. let a human approve a pay or purchase when asked 7. Show the checking balance (it should drop after an approved pay). Make the dashboard along star wars theme (light mode with blue accent for jedi and dark mode with red accent for sith) - be creative with layout and feel as this is a real desk people would want to sit at, therefor be thorough with it. Tell the front end to talk to your backend at http://localhost:8000. on the backend, allow the vite page origin (usually http://localhost:5173) so the browser is allowed to call those routes. Start the board with: npm run dev . This should opens the react desk in my browser so that i can pick tickets and watch the agents. Write output/design.md with what you chose for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up), and why - including the creative choices that make it feel special and something humans would actually enjoy using."

**Follow-up needed:** None.

---

## Problem 9 — Full run on all three tickets, actual vs expected, cash, resolved board

**Prompts:**
1. "Problem 9: before testing the agents on a full run over the three tickets, reset the working database data/campus_customs_new.db again so you start clean. Note the starting checking balance. Then run all three tickets on the board (101, 102, 103) until each is resolved. Open output/desh_tickets.html from problem 6. On each ticket tab, fill the actual section from this run: which agents worked, what they delegated, and which tools they used. Keep the expected section so we can compare the two. On the cash tab of the same output/desk_tickets.html , itemize the money: 1. Starting checking balance (after the reset) 2. For each ticket: how cash changed when that ticket resolved, and why (which pay / purchase, dollar amount) 3. ending checking balance - it must match cash_accounts in the working database. wrong cash math loses points even if the board shows every ticket resolved. Also save: 1. output/resolved_tickets.json - for each ticket: id, final status, short outcome, what each agent contributed, and any human approvals 2. output/resolved_board.html - a page you can double-click with a screenshot of your React board for each resolved ticket (101, 102 and 103). Append real runs to output/audit_trail.json, Finish output/harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard and safety rules."

**Follow-up needed:** None.

---

## Problem 10 — Reflection tab in desk_tickets.html

**Prompts:**
1. "Problem 10: open the output/desk_tickets.html and fill the reflection tab. Answer in my words and tone, be detailed and thorough: 1. How would you evaluate the performance of the agents on each ticket and why? 2. For each ticket, how did actual compare to the expected plan we wrote earlier? 3. What would have been simpler as one agent with tools - and why? 4. Describe three new problems campus customs might face that this agent team could solve with the tools you built 5. Describe three new problems campus customs might face that this agent team could not solve with the tools you built, and explain the tools and agents you would need to solve them. Each answer should be tied to the app and the three tickets we ran - use the ticket tab and cash tab on the same page as your evidence. Do not make it a generic AI essay"

**Follow-up needed:** None.

---

## Problem 11 — Submit to GitHub (public repo, README, github_url.txt)

**Prompts:**
1. "Ok now we need to push the code to a public Github repository so graders can clone it. Submit the repo URL to canvas , and also put it in output/github_url.txt . do not push the real .env to the Github repo. Do include both database files under data/ (the original and your working copy) so graders can run your app easily. README should explain: copy original DB to the working copy when you need a clean run, start MCP server, start FastAPI backend, start the React board, and reset the DB before a full three-ticket run"

**Follow-up needed:** None. (Submitting the URL on Canvas is done by me.)

---
