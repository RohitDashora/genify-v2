# UI design notes

The UI is part of a **demo / reference** application (see the persistent **Demo banner** in [`AppShell.jsx`](../src/genify/frontend/src/components/layout/AppShell.jsx)). Visual treatment is optimized for clarity in workshops and forks, not a full production design system.

Genify’s frontend is a **Vite + React** SPA under [`src/genify/frontend/`](../src/genify/frontend/). This page summarizes **design intent**; the component map and SSE behavior live in [architecture.md §5](architecture.md#5-agent-session-sequence-simplified).

## Screenshots (Home and Library)

![Home — catalog pickers, template tabs, session list; table comments previewed (clamped); types as compact pills (recapture after table list UX change if the image predates clamped comments + type pill)](images/screenshot-home.png)

![Library — saved metadata list and YAML editor](images/screenshot-library.png)

### Home — Select Tables list

- Each table **name** is on the first line; **Unity Catalog comment** is a **two-line max** preview (`line-clamp`) with **full text on hover** (`title`), since comments can be very long.
- **Table type** is a **compact pill** (two lines when the type contains `_`, e.g. `MATERIALIZED_VIEW`), freeing width for the comment preview. Styling uses the same **gray / border** neutrals as the Home card (`border-border-subtle`, `shadow-card` on the parent **Select Tables** card).

See also [product-overview.md](product-overview.md#screenshots) and the root [README.md](../README.md#screenshots).

## Session page (agent loop, MCP trace, modes)

- **Two columns:** conversation / progress / **Activity trace** (collapsible, terminal-style) on the left; **Generated YAML** on the right with show/hide and copy.
- **Status pill** — e.g. Created, Executing, Waiting For User, Complete — encodes lifecycle and pairs with header text (`Table Comment | hands off | Step k`).
- **Hands-off** — Users watch gather → plan → section execution; trace proves **which MCP tools** ran (`GATHER Calling …`, `Using cached MCP context` on later phases).
- **Interactive** — Same gather/plan, then **question** pauses with composer + optional YAML preview; see [architecture.md — Hands-off vs interactive design](architecture.md#hands-off-vs-interactive-design).
- **Question composer (interactive pause)** — **Transcript-first:** the full question text appears only in the **Conversation** transcript (assistant message), not repeated in the composer. The composer card matches the Conversation panel (`rounded-xl`, `border-border-subtle`, `shadow-card`). It shows an optional **Answering · section · field** context line, a read-only **Suggested reply** block (slate panel, scrollable when long) when the server sends `suggested_answer`, then **Use suggestion** / **Send suggestion** and an empty textarea for a custom answer (or after copying the suggestion). Theme tokens align with [`tailwind.config.js`](../src/genify/frontend/tailwind.config.js) (`brand`, `slate`, `surface`).

![Session — hands-off MCP gather](images/screenshot-session-hands-off-gather.png)

![Session — hands-off execute + YAML](images/screenshot-session-hands-off-execute.png)

![Session — interactive question (recapture after composer changes if the image predates the suggested-reply panel layout)](images/screenshot-session-interactive-waiting-user.png)

## Transcript first, trace second

- The **session** page is built around a **conversation transcript** (assistant / user / system), not a raw operational log.
- Verbose diagnostics use SSE **`trace`** events and appear in the **Activity trace** panel, **collapsed by default** so casual users are not overwhelmed. Operators can expand and copy traces for support.
- Rationale: [ADR-9 — Transcript-first session UI](design-decisions.md#adr-9-transcript-first-session-ui).

## Responsive shell and navigation

- **Desktop:** Persistent **left sidebar** (~240px) with **Home** and **Library**; main content is **full width** (`flex-1 min-w-0`) without a narrow `max-w-*` workspace cap.
- **Small screens:** **Hamburger** opens a **drawer** with backdrop; drawer closes on route change.
- Session header **Back** is **hidden from `md` up** because the sidebar already provides navigation.

## Progressive disclosure and feedback

- **`HelpHint`** (`?`) offers short explanations on dense surfaces (section titles, etc.).
- **Plan** payloads from the server are **humanized** in the UI (strategies shown as readable copy, not raw enums).
- **Connection state:** After a **`question`** event, the client **closes** `EventSource` intentionally; the UI **suppresses** scary “connection lost” messaging while the user is composing an answer, so pauses feel intentional rather than broken.

## Icons and density

- Session chrome uses **Lucide** icons for a consistent, neutral look (avoid emoji in production session UI).

## Library and editing

- **Library** lists **completed** metadata cards showing **`table_fqn`** or **Combined** for multi-table sessions.
- Detail view supports **YAML** and **Markdown** toggles, **CodeMirror** editing, **js-yaml** validation, **Save / Revert**, and copy actions.
- **Deep links:** `complete` SSE may include **`completed_id`** so the client can open the right Library row and save edits to **`PUT /api/completed/{id}`** without guessing.

## Related files

| Concern | Entry points |
|---------|----------------|
| Layout | `layout/AppShell.jsx`, `layout/AppSidebar.jsx` |
| Session flow | `SessionView.jsx`, `SessionTranscript.jsx`, `TracePanel.jsx`, `QuestionComposer.jsx` |
| SSE client | `api.js` — `connectSSE`, `fetchJSON` |
