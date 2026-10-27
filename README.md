# Odoo AI Modules

Two Odoo 19 modules that call AI models at runtime: a two-tier AI triage system for helpdesk tickets, and a reusable semantic search component built on PostgreSQL and pgvector. I built them while training in AI-integrated Odoo development, using demo data only.

| Module | What it does |
| --- | --- |
| [`helpdesk_ai_sorting`](helpdesk_ai_sorting) | Triages every new ticket with a structured LLM call, and on complex tickets produces a full AI review that a person approves. |
| [`semantic_record_search`](semantic_record_search) | Adds meaning-based search to any Odoo model, backed by embeddings stored in pgvector. |

## Helpdesk AI Sorting

Sorts incoming tickets so the expensive AI work only happens where it's worth it.

**Tier 1, on every ticket.** A single structured LLM call (`request_llm` with a JSON schema) sets a triage level (routine, needs attention, or urgent/complex), suggests a team, and writes a short summary with its reasoning. It runs through a batched cron that re-triggers itself, so creating a ticket never waits on the model.

**Tier 2, only when a person asks for it.** On complex tickets, an agent action (a `state='ai'` server action) reviews the ticket and produces a breakdown of the issue, a suggested reply to the customer, a suggested reviewer and deadline, a suggested next action, and a step-by-step plan. Reviewer suggestions are based on the team's real `hr_skills` data. Nothing is applied automatically: a person reviews the suggestion and decides.

**Working around a framework limitation.** In Odoo 19, a tool call made by an agent action ends the run before the model ever sees the tool's result, so "look something up, then reason about it" can't be done with tools. Instead, the read-only lookups (customer history, similar past tickets, available team members) are computed up front and injected into the prompt as context fields. The only real tool call left is the write, which doesn't need a result back.

## Semantic Record Search

Meaning-based search for Odoo records, so a query like "customer says checkout breaks after a discount code" finds "Checkout returns 500 error after promo code applied" without sharing keywords.

**The idea.** An embedding model turns a piece of text into a long list of numbers that captures its meaning, so texts that mean similar things end up close together. Comparing those numbers finds related records even when they share no words, and a similarity cutoff decides how close counts as a match.

- **Reusable mixin.** Any model that inherits `semantic.search.mixin` gets an embedding field, re-embedding only when its relevant text actually changes, a batched background cron for embedding, and `_find_similar()` for lookups.
- **Storage and speed.** Embeddings come from OpenAI `text-embedding-3-small` and are stored with OCA's `field_vector` in a pgvector column, with an ivfflat index for fast cosine-similarity search.
- **Tuned threshold.** The similarity cutoff (0.42) was set by testing 100 queries against the demo tickets: 38 reworded queries with a known correct match and 62 designed to match nothing.
- **Access rules respected.** Results from the raw SQL query are filtered back through a normal `search()`, so Odoo's record rules still apply to the current user.
- **Ready to use.** It has its own app menu and search wizard, and `helpdesk.ticket` is the first model using it.

## How they work together

Tier 2's "similar past tickets" lookup tries semantic search first, reusing each ticket's stored embedding. It separates similar resolved tickets from similar open ones, and falls back to the original keyword search if anything fails, leaving a note in the ticket's chatter when it does.

## Requirements

- Odoo 19 Enterprise (`helpdesk`, `ai`, `hr_skills`)
- PostgreSQL with the pgvector extension
- `field_vector` from [OCA/server-tools](https://github.com/OCA/server-tools)
- `numpy` in Odoo's Python environment
- An OpenAI API key set in Odoo's AI settings

Installing `helpdesk_ai_sorting` also installs `semantic_record_search`. Both include demo data.
