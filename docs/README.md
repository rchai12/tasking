# Tasks App Docs

Started Nov 9, 2026 · @Richard · split into separate docs Nov 14, 2026

The tasks app (the Python package `docket`) is the single source of truth for tasks, reminders and calendar sync. A task exists only after you approve it: in the email service, in Conductor, or on one of the app's own proposal cards. It runs on the home Mac, holds no model, and reaches you through the shared Discord service.

## Documents

| Doc | What it covers |
| --- | --- |
| [Purpose and scope](purpose-and-scope.md) | What the app is for, and what v1 includes and leaves out |
| [Decisions](decisions.md) | Every major decision, with the reason and the option rejected |
| [Architecture](architecture.md) | Components, data model, intake, the reminder engine, Discord, calendars, MCP tools, failures, the privacy boundary |
| [Roadmap](roadmap.md) | Build order, acceptance tests, work in the other projects, deferred items |
| [Open questions](open-questions.md) | Decisions still to make |
| [Testing](testing.md) | Test layers, rules and critical modules |
| [Audit](audit.md) | Maintainability and risk review of the code as of Phase 2e (Nov 15, 2026) |
| [Later audits](audit/) | Later reviews, newest first: [Nov 21, 2026](audit/2026-11-21-codebase-audit.md), at Phase 6a's spec |
| [Handoffs](handoffs/) | What the [email service](handoffs/emails.md), [Conductor](handoffs/langgraph.md) and [finances](handoffs/finances.md) need to know from these decisions |
| [Phase conventions](phase-conventions.md) | What every phase spec and verification guide assume: starting checks, rules, acceptance, the progress entry, the verdict |
| [phases/](phases/) | Detailed specs, one per phase |
| `verification/` | One guide per phase (and its probe), for the second agent that checks the implementation |
| [progress.md](progress.md) | The coder's log, one entry per phase |
| [Coder token use](coder-token-use.md) | Where the coding agent's context went on Phases 1c through 2d, and what to shorten |
| `reviews/` | The verifier's report for each phase, with its verdict |
| [Verification process](verification-process.md) | Where phase verification spends its tokens, and what to script |

The original single document is kept in [archive/](archive/Tasks,%20Scheduling%20and%20Calendar%20Feature%20Decisions.md) for reference. These docs replace it.

## Where it fits

| Project | Role | How it reaches the tasks app |
| --- | --- | --- |
| `emails` (mailroom) | Reads mail, runs its own Discord approvals | `POST /tasks` and `POST /tasks/<id>/links` with tasks you already approved |
| `langgraph` (Conductor) | The supervisor agent | Launches `docket mcp serve` over stdio; write tools run only after you approve the step in Conductor |
| `switchboard` (planned) | The shared Discord service | Posts the app's cards and forwards your button presses to it |
| `finances` | Personal finance | None; the source of the shared conventions |

## Workflow

1. Commit the spec, its verification guide and its given files, so `git status` is clean. Then give the coding agent one phase at a time:

   > /phase-coder NN

   The `phase-coder` skill (`.claude/skills/phase-coder/`) says what to read, how to keep output small, and how to report.

2. Give a second agent the matching guide in `verification/`:

   > /phase-verifier NN

   The `phase-verifier` skill (`.claude/skills/phase-verifier/`) does the same for the verifier.

   The verifier writes its report to `reviews/`, named as the spec is. A FAIL goes back to the coding agent with the verifier's findings.
3. Commit.
4. The architect writes or adjusts the next phase spec and its verification guide based on what was actually built.

The roles are skills in `.claude/skills/`: `phase-architect` (the architect's whole procedure, its tools and `history.md`) and `phase-implementer-verifier` (one agent that implements a named phase, then verifies it), modeled on the `finances` project's.
