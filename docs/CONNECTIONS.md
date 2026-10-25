# What I need access to, and exactly how to connect me to it

Every status in this file was **measured from the sandbox on 2026-10-25**, not assumed.
Probe method: `urllib` request per endpoint, plus my `fetch_page`/`web_search` tools
where raw HTTP was refused. The two paths behave differently, which matters.

## How my sandbox works (the constraint everything else follows from)

| property | status |
|---|---|
| Outbound HTTPS to the public internet | **works** |
| Read/write `/home/user`, persists across messages | **works** |
| `git`, `python3` 3.11, `pip`, `node` v20 | present (`curl` is not; use `python3 -m urllib`) |
| Inbound connections to me | **impossible** — no public endpoint |
| Reaching `127.0.0.1` on *your* machine | **impossible** — that's your loopback, not mine |
| A real browser, GUI, or click-through login | **none** |
| Workspace snapshot | ~128 MB / 10,000 files; excludes `.git/config`, `.git/credentials`, `.git-credentials`, `.netrc` |

Consequence: **anything that lives on your computer or behind an interactive login
cannot be connected to this chat.** It can only be connected to a *local* agent
(Qwen Code / Qwen Chat Desktop with MCP), or handed to me as a file.

---

## Group 1 — Already connected. You do nothing.

Verified HTTP 200 from the sandbox, no key, no account:

| source | what I use it for | verified |
|---|---|---|
| Yahoo Finance chart API (`query2/query1.finance.yahoo.com/v8/finance/chart`) | 5m/1m/daily bars: scanner, entry, timemachine, labs | **200** |
| Yahoo spark API (`/v7/finance/spark`) | bulk daily closes for wide scans | **200** |
| Yahoo news RSS (`feeds.finance.yahoo.com/rss/2.0/headline`) | headlines per ticker (`trader-news`) | **200** |
| SEC EDGAR JSON API (`data.sec.gov/submissions`, `/files/company_tickers.json`, XBRL companyfacts) | 13Fs, 8-Ks, filings, earnings (`trader-copycat`, `trader-analyst`) | **200** |
| Nasdaq Trader SymDir (`nasdaqtrader.com/dynamic/SymDir/{nasdaqlisted,otherlisted}.txt`) | the ~5,900-symbol universe (`trader-scanner universe`) | **200 both** |
| GitHub (clone, API, raw) | repos, manifests | **200** (4 clones this session, incl. 986 MB) |
| PyPI, npm registry | tooling | **200 both** |
| `impots.gouv.fr`, `service-public.gouv.fr`, `entreprendre.service-public.gouv.fr` | French tax/status facts | **200** |

**Caveat that matters:** `data.sec.gov` (the machine API) answers 200 to any
User-Agent, but `www.sec.gov/cgi-bin/browse-edgar` (the human pages) returns **403** to
a generic one. SEC *policy* requires a UA containing your name and email. Heavy use
with a generic UA gets your IP blocked. See Group 3.

---

## Group 2 — Reachable through my research tools only

Raw HTTP is refused; my `fetch_page`/`web_search` tools get through. So I can read
these, but the *agents'* Python tools cannot fetch them unaided.

| source | raw HTTP | via my tools | effect |
|---|---|---|---|
| SSRN (`papers.ssrn.com`) | **403** | **works** — I pulled both abstracts this session | I can read research; a script cannot |
| Malt (`malt.fr`) | **403** | **works** via search | I can quote TJM benchmarks |
| Obsidian Help (`help.obsidian.md`) | page shell only (JS-rendered) | partly | forum/plugin READMEs are the better source |

If a workflow needs these inside a *script*, the fix is: I fetch it, save it to the
workspace, and the script reads the saved copy (`--offline`).

---

## Group 3 — Needs one small thing from you (not a password)

### 3a. `SEC_USER_AGENT` — your name and email, so EDGAR tools work fully

`trader-copycat copy` **refused to run** without it, and I did not invent an identity
for a government endpoint. It is not a secret and grants no access; SEC just wants to
know who is querying.

```bash
# easiest: an env var in the shell where you run the tools
export SEC_USER_AGENT="Your Name you@example.com"
python3 /home/user/_research/trader-skill/trader-copycat/edgar13f.py copy berkshire --top 10

# or persist it for the agents
mkdir -p trader && echo '{"sec_user_agent":"Your Name you@example.com"}' > trader/config.json
```
Use a real email you read. Do **not** reuse a password anywhere; none is involved.

### 3b. GitHub — only if you want me to push, or to read a private repo

The safe pattern, in order of preference:

1. **Best: you push, I patch.** I write `git diff > changes.patch`; you run
   `git apply`. I never hold a credential.
2. **Read-only pull of a private repo:** fine-grained PAT → repo = that one repo →
   permission **Contents: Read-only** → expiry **7 days** (GitHub's minimum). Paste
   it in chat; I clone with it inline and never write it to a file. Revoke after.
3. **Never:** a classic PAT, a write-scoped token, an SSH private key, or your
   password. Note `.git/config` and `.git-credentials` are excluded from my snapshot
   by design — a token embedded in a remote URL is not persisted, which is good, but
   still revoke it.

### 3c. A file, where an endpoint blocks me

| what | why | how |
|---|---|---|
| **House Clerk PTR index** (`disclosures-clerk.house.gov/.../2026FD.zip`) | **403 from the sandbox**, reproducibly | Download it in your browser (works for humans), then attach it. Then: `python3 trader-pelosi/ptr.py index --year 2026 --member pelosi --offline 2026FD.zip` — verified working on the repo's fixture |
| **PTR PDFs / any binary** | I have no browser | attach the file |
| **6 years of 5-minute bars** | Yahoo free gives ~60 days at 5m | export from your broker or a vendor in Yahoo chart-JSON shape, attach it, and I run `labs.py --offline` on it. This is the *only* way the 508%/313R claims ever get tested |
| **Paywalled full-text papers** | SSRN gives me abstracts only | attach the PDF |

---

## Group 4 — Cannot be connected to this chat. Needs a local agent, or your hands.

### 4a. Obsidian (the app and your vault)

The app is on your machine; I cannot reach your `127.0.0.1`. Three real options:

| option | how | notes |
|---|---|---|
| **Attach the vault** | `zip -r vault.zip MyVault -x "MyVault/.obsidian/workspace*" "MyVault/.trash/*" "MyVault/.git/*"` then drag it into chat | fastest; best under ~50 MB |
| **Git pull** | private repo + 7-day read-only PAT (see 3b); I clone into the workspace | best for ongoing work; I return a patch |
| **Live MCP** | Obsidian plugin **Local REST API** → its built-in MCP server at `http://127.0.0.1:27123/mcp/` → wired into **Qwen Chat Desktop** (chat window → MCP → Add MCP → JSON) or **Qwen Code** (`qwen mcp add --transport http obsidian ...`) | only works with a *local* agent, not this chat |

Before you attach anything, run the redaction scan I already built:
```bash
python3 /home/user/obsidian-datafarm/src/vault_probe.py /path/to/MyVault --test-write
```
It flags AWS/GitHub/Slack/OpenAI keys, bearer tokens, private key blocks and DB
connection strings, and prints **redacted previews only**.

### 4b. Everything identity-bound — I cannot and should not do these

| thing | why not | who does it |
|---|---|---|
| URSSAF / auto-entrepreneur registration | login, identity, signature. Also **URSSAF refused my connection outright** (bot protection) | you, ~30 min, free |
| ACRE request | filed at creation with URSSAF | you |
| `impots.gouv.fr` | FranceConnect identity login | you |
| **Bank / PEA opening** | KYC, ID, signature. This is your €10 action this week | you |
| Broker account (Alpaca, IBKR, Degiro, Trade Republic) | KYC + keys | you |
| Malt / Upwork / Fiverr / LinkedIn profiles | identity, and LinkedIn is ToS-hostile to automation. Malt also **403s** my raw HTTP | you |
| Stripe / Gumroad / Lemon Squeezy | KYC + payout identity | you |
| A2A/MCP servers on your machine | localhost | you (or a local agent) |

I can draft every form, write the profile copy, build the pricing page, and review
the wording. I cannot *be* you.

### 4c. Your broker's trading API — deliberately not connected

Alpaca's MCP server and IBKR's connector run on **your** machine and are reached by a
**local** agent, not by me. Even if I could reach them, I would not wire an agent to
live order placement on your behalf. The pack is built so this is structurally
difficult: `"paper": true` by default, `require_stop: true`, the risk verdict is bound
to the exact order *and* the exact day, and `trader-broker` only shows a ticket —
execution needs your typed yes plus Claude's own Allow-once card. My console hardens
that further: `approve`, `decline`, `result`, `fill`, `flatten` and `log` are refused
before any subprocess starts, and four tests attack that rule.

Keep it that way. Set any brokerage tool to **"Needs approval"**, never "Always allow".

---

## Group 5 — Never send me these

Broker API keys · bank credentials · any password · 2FA/TOTP seeds · your national ID
or tax number · a French `numéro fiscal` · SSH private keys · classic or write-scoped
GitHub tokens · the Local REST API key in *chat* (it belongs in your local MCP config
file only) · full vault exports containing other people's personal data.

If you paste something sensitive by accident, rotate it immediately and tell me; I
will not store or repeat it, and my own probe tools print redacted previews by design.

---

## Group 6 — Verified broken or not worth connecting

| source | status | note |
|---|---|---|
| Stooq CSV (`stooq.com/q/l/`) | **404 on every symbol format I tried** (`qqq.us`, `aapl.us`, `^spx`, `spx`) | `trader-alerts` uses it as a fallback quote source. Yahoo covers quotes, so nothing is lost, but don't rely on the Stooq path |
| House Clerk (live) | **403** | see 3c — attach the ZIP |
| URSSAF | connection dropped | reference their published rates via `economie.gouv.fr` (200) instead |
| Obsidian Sync | no public API | cannot be integrated; use git or file attach |

---

## The short version

**Nothing more is required to keep doing the research and backtesting work** — Yahoo,
SEC EDGAR and Nasdaq Trader are already reachable and I proved it by running your
agents on live data this session.

**Three things unlock the rest:**
1. `export SEC_USER_AGENT="Your Name you@example.com"` → full 13F/EDGAR tooling.
2. Your vault, as a zip or a read-only git clone → the Obsidian data farm.
3. The House Clerk `2026FD.zip` and, if you ever get one, a long 5-minute bar file →
   the Pelosi tracker live, and an actual test of the 508%/313R claims.

**Everything involving money, identity or a signature is yours to do.** I can prepare
each one to the point where you click submit.
