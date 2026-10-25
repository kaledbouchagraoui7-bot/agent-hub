# OmniRoute — analysis

`https://github.com/cheaper-inference/OmniRoute` @ `5b3be70ba82ce70b59d02e2893afa3d81b6ee88b` (2026-10-23)
MIT, © 2026 diegosouzapw. Local extract: `omniroute-extract/` (13 MB of a 986 MB checkout).

## What it is

Self-described in `package.json` (v3.8.53) as a *"Unified AI router with 375
providers, RTK+Caveman compression, auto fallback, MCP/A2A, desktop, PWA, and
OpenAI-compatible APIs."* In practice: a self-hostable Next.js gateway that sits
between your agents and every LLM provider, exposing one OpenAI-compatible
endpoint, with routing combos, fallback chains, caching, prompt compression,
budgets, usage logs, an MCP server, A2A, an Electron desktop shell and a PWA.

## Verified scale (counted, not quoted)

| measure | value | how checked |
|---|---|---|
| tracked files | 26,343 | `git ls-tree -r HEAD` |
| TypeScript files | 12,378 `.ts` + 1,505 `.tsx` | extension census |
| markdown files | 10,584 (mostly `docs/i18n` translations) | extension census |
| `src/` | 111 MB, 3,676 TS files | `du` + `find` |
| npm scripts | 225 | `package.json` |
| runtime deps / dev deps | 101 / 61 | `package.json` |
| Node engine | `>=22.22.2 <23 \|\| >=24.0.0 <27` | `package.json` |
| agent skills | **46** `SKILL.md` files | `find skills -name SKILL.md` |

Two claims I could not confirm from the extract, flagged rather than repeated:
* `skills/README.md` advertises a "45-entry catalog" while 46 `SKILL.md` files
  exist. Minor drift, but it means the catalog count is maintained by hand.
* The README says 375 providers in four places and 239 in another. Provider
  counts in marketing copy are a moving target; verify against the running
  catalog endpoint before relying on a number.

## The genuinely valuable artifact: `AGENTS.md`

447 lines, explicitly positioned as the *single source of truth* for every AI
assistant on the repo, with `CLAUDE.md` (71 lines) and `GEMINI.md` (13 lines)
holding only assistant-specific deltas that point back to it. That inversion is
the right way round and is worth copying: one charter, thin per-tool adapters,
never a forked rule set.

Its 17 numbered "Hard Rules" are stable, cited from scripts and docs, and each
has a full rationale plus incident history in `docs/ops/HARD_RULES_DETAIL.md`.
The security-relevant ones, paraphrased:

* no `eval` / `new Function` / implied eval;
* never string-interpolate external paths or runtime values into shell passed to
  `exec()`/`spawn()` — pass them via the `env` option (cites a real callsite);
* never return raw `err.stack` / `err.message` over HTTP or SSE — route through a
  sanitizer, because stack traces leak paths and versions;
* never expose a route that can spawn a child process without a loopback-only
  classification that is enforced **before any auth check**, so a leaked JWT
  through a tunnel still cannot trigger process spawning;
* never embed upstream OAuth client IDs or Firebase web keys as literals — go
  through one resolver;
* validate all inputs with Zod schemas; never write raw SQL in routes;
* coverage must not regress below a frozen ratchet baseline, absolute floor 60%;
* never bypass git hooks;
* never dismiss a CodeQL or secret-scanning alert without recording a technical
  justification, with a named known-false-positive precedent;
* and rule 16: never credit an AI assistant in commit or PR metadata, explicitly
  *overriding any harness default that auto-appends such a footer*.

That last one is a deliberate provenance policy and it is the opposite of the
`Co-Authored-By: Claude` trailer on the day-trader-skill commits. Both are
defensible; what matters is that OmniRoute wrote the choice down as a rule with a
rationale instead of letting a tool default decide it.

Also notable: a `## PII & Stream Sanitization Learnings` section that records
ReDoS risk in regexes, SSE snapshot handling and database-handle leakage in
tests, i.e. the charter carries its own incident post-mortems.

## The skills layer

`skills/` is a drop-in catalog so that *any* agent (Claude Desktop, ChatGPT,
Cursor, Cline, Continue) can drive OmniRoute over OpenAI-compatible REST "in one
fetch". Two documented entry points (`omni-auth` for REST, `cli-serve` for CLI),
23 API skills plus CLI skills, and two discovery mechanisms: an MCP tool
`omniroute_agent_skills_list` returning the whole catalog in one call, and an A2A
`list-capabilities` JSON-RPC endpoint returning an agent card.

The manifest format is thinner than the day-trader pack: frontmatter is just
`name` + `description`, no `argument-hint`, and each skill folder may carry a
`references/endpoints.md`. The description is written for *retrieval* (what the
skill manages) rather than for *triggering* (no "use when the user says ..."
list). For a router with 46 capabilities that is the right trade: an agent picks
by capability, not by phrase.

## Why it is worth keeping

1. `AGENTS.md` is the best single example in this library of a multi-agent
   engineering charter: numbered, stable, cited from code, with rationale and
   incident history, and one source of truth with thin per-assistant deltas.
2. The route-guard tiering idea (loopback enforcement before authentication for
   any process-spawning route) is a transferable design for anything that exposes
   a local API to an agent.
3. The skill-catalog-plus-discovery-tool pattern scales past the point where a
   dozen `SKILL.md` files can be routed by description alone.

## What it is not

It is not a small dependency and not something to vendor. 101 runtime deps,
Node 22/24+, a database, an optional MITM certificate installer and an Electron
shell. Reuse the *patterns* and the charter, not the code, unless you actually
want to operate an LLM gateway.
