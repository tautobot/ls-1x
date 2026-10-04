# PIPELINE.md

> **Provenance:** No PIPELINE.md existed when pyrx-fullstack-dev began the live-match sync subsystem
> task (2026-08-19). This pipeline was created from the global template, trimmed to match ls-1x's
> actual scope (a small single-repo Streamlit tool with an in-process match-sync backend, no public
> API, no native client, no marketing surface, no AI). Review and adjust as the project grows.
>
> **Conflict rule:** When this file conflicts with an individual agent's instructions, **this file wins**.

---

## Agent Roster

| Agent | Scope | Status |
|-------|-------|--------|
| **pyrx-fullstack-dev** | Backend/service + Streamlit implementation + tests + DevOps | Active |
| **pyrx-qa** | QA — manual + automated testing, bug investigation, quality gate | Active |
| **pyrx-em** | Orchestrator/planning | Optional (activate for larger multi-phase work) |
| **pyrx-docs** | Technical writer | Optional (only if a public API/SDK is added) |
| **pyrx-designer** | UI/UX designer | Not used (Streamlit defaults; no custom design) |
| **pyrx-content** | Content/marketing | Not used (no marketing surface) |
| **pyrx-native-dev** | Native client dev | Not used (no native client) |

---

## Work Type Flows

### Flow A: Backend / Service change (this task's class)

**Trigger:** Change to the sync subsystem, store, or any non-UI backend/service code.

```
1. pyrx-fullstack-dev — implement + tests (unit + integration) + gates
2. feature-dev:code-reviewer — mandatory review (dev auto-dispatches)
3. pyrx-fullstack-dev — prepare test data (seed script / stubbed-provider tests)
4. pyrx-qa — verify → APPROVED / NEEDS-REVISION
5. (downstream) — NONE by default: no public API contract, no user-facing copy,
   no custom design. README is maintained inline by dev. So the pipeline ends at QA.
```

**Downstream routing decision for this change class:**
- `pyrx-docs`: SKIP — the sync subsystem exposes no public HTTP/GraphQL/webhook contract; it's an
  internal in-process service. README was updated inline by the dev.
- `pyrx-content`: SKIP — no user-facing copy changed.
- `pyrx-designer`: SKIP — no custom design (app is unchanged; renders via Streamlit defaults).
- `pyrx-native-dev`: SKIP — no native client.

### Flow B: UI change (Streamlit app)

```
1. pyrx-fullstack-dev — implement + visual verify (Playwright)
2. feature-dev:code-reviewer — mandatory review
3. pyrx-qa — verify (render, filters, states, no console errors) → APPROVED
4. (downstream) — NONE by default (no marketing/docs surface).
```

### Flow C: Bug fix

```
1. pyrx-fullstack-dev — reproduce + fix + regression test
2. feature-dev:code-reviewer — mandatory review
3. pyrx-qa — verify fix + regression → APPROVED
```

---

## Handoff Standard

Every cross-agent handoff includes: what changed (files), how to test (commands, ports, URLs),
test data (seed script path + summary), quality-gate results, and the specific verdict requested.
See pyrx-fullstack-dev's handoff templates.

## Deliverables Contract

Every dispatched agent ends its work with a `## Deliverables` report (shared
7-section core + its role block). Canonical structure, field rules, closed
vocabularies, and length limits: **`~/.claude/DELIVERABLES.md`**. The enforcement
block is appended to every `pyrx-*` agent file.

- **A handoff is NOT complete until the receiving agent's `## Deliverables` report
  is received.** Dispatchers route on it — Verdict, Artifacts, Coverage, Next hop
  sit in fixed places regardless of who wrote it.
- **Closed vocabularies** (no synonyms): Verdict ∈ {`DONE`, `PARTIAL`, `BLOCKED`,
  `FAILED`, `OUT_OF_BUDGET`}; evidence label ∈ {`[VERIFIED:run]`,
  `[VERIFIED:code]`, `[SPEC]`, `[UNVERIFIED]`}. `DONE` requires every Change `done`
  AND every DoD-required Verification row `pass [VERIFIED:run]`.
- **A dispatched agent that returns NO report** (died mid-task / hit its budget) is
  treated as `OUT_OF_BUDGET`: the dispatcher re-dispatches a NARROWER finish-only
  task — it never trusts un-reported partial work.
- **pyrx-em spot-check:** before accepting a `DONE` from a dispatched agent, re-run
  ≥1 of its `[VERIFIED:run]` evidence items and re-label in its own report.

---

## Refusal / Escalation Rules

- QA owns the Definition of Done; nothing is "done" until QA says APPROVED.
- code-reviewer runs on every real code change before QA (dev auto-dispatches).
- After 3 review rounds with the same agent on the same finding, escalate to the user.
- Do NOT commit or push unless the user explicitly asks; leave changes in the working tree.

## Last Reviewed

| Field | Value |
|-------|-------|
| **Last reviewed** | 2026-08-19 |
| **Reviewed by** | pyrx-fullstack-dev (auto-created; unverified by human) |
