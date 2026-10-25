# Exact steps for every connection

Each item says **who does it**, the exact commands or clicks, and **how you verify it
worked**. Items marked 🔒 need your identity and cannot be delegated to me.

Order matters: do 1 and 2 first (they take minutes and unlock the most), then 3.

---

## 1. `SEC_USER_AGENT` — unlocks full SEC EDGAR tooling

**Who:** you (one line). **Why:** SEC policy requires every request to identify a
human. `trader-copycat copy` refuses to run without it and I will not invent a name
and email for a government endpoint. It is not a secret and grants no access.

```bash
# per-shell
export SEC_USER_AGENT="Your Name you@example.com"

# or persist it where the agents look
cd /path/to/your/project
mkdir -p trader
printf '{"sec_user_agent":"Your Name you@example.com"}\n' > trader/config.json
```

Use an email you actually read. No password is involved anywhere.

**Verify:**
```bash
python3 agent-hub/trader-skill/trader-copycat/edgar13f.py copy berkshire --top 5
```
Expected: a table of Berkshire's top holdings with weights. If you instead see the
"SEC requires a User-Agent" message, the variable did not reach that process.

**Already working without it:** `find`, and everything on `data.sec.gov`
(submissions, company tickers, XBRL facts) — I verified those return HTTP 200.

---

## 2. House Clerk PTR file — unlocks the live Pelosi tracker

**Who:** you (download), me (analyse). **Why:** `disclosures-clerk.house.gov` returns
**403 to datacentre IPs**, reproducibly. It works fine in a normal browser.

1. Open `https://disclosures-clerk.house.gov/public_disc/financial-pdfs/2026FD.zip`
   in your browser. It downloads a ZIP (the year's filing index).
2. Attach it to this chat, or drop it into the workspace.

**Verify (I run this):**
```bash
python3 agent-hub/trader-agents/trader-pelosi/ptr.py index --year 2026 \
        --member pelosi --offline 2026FD.zip
```
Expected: dated rows with member, state, filing type, document id and PDF URL. I ran
the identical command on the repository's bundled fixture and it returned four 2026
Pelosi filings, so the code path is proven; only the live download is blocked.

---

## 3. GitHub — publish the hub 🔒

**Who:** you create the empty repo; then either I push (route A) or you push (route B).

### 3a. Create the empty repository (both routes, ~30 seconds)

1. Go to `https://github.com/new`
2. **Repository name:** `agent-hub` (or anything you like)
3. **Public or private:** your call. Note that `trader-agents/` and `trader-skill/`
   are MIT third-party code with attribution preserved, so publishing is permitted.
   `docs/` contains no personal data.
4. **IMPORTANT: do not add** a README, `.gitignore` or licence. The repo must be
   empty, or the push will be rejected as a non-fast-forward.
5. Click **Create repository**.

### 3b. Route A — I push (needs a token in chat)

1. `https://github.com/settings/personal-access-tokens/new` (fine-grained)
2. **Name:** `agent-hub-push` · **Expiration:** 7 days (the minimum)
3. **Repository access:** *Only select repositories* → your new `agent-hub`
4. **Permissions → Repository permissions → Contents:** **Read and write**
   (leave everything else at "No access")
5. Generate, copy the token, and send me:
   ```
   owner: <your-username>
   repo:  agent-hub
   token: <paste>
   ```
6. I run:
   ```bash
   GITHUB_TOKEN=... GITHUB_OWNER=... GITHUB_REPO=agent-hub bash scripts/push-github.sh
   ```
   The token is used inline for one push, so it never lands in `.git/config`,
   `.git-credentials` or the reflog. The script also **aborts** if any
   credential-shaped file is tracked.
7. **You revoke the token immediately afterwards.** I will tell you when the push
   succeeded and remind you.

Note: a fine-grained token cannot *create* a repository, which is why step 3a is
yours. That is also the more secure order.

### 3c. Route B — you push, I never see a credential (recommended)

```bash
# copy agent-hub/ to your machine, or clone it from wherever you keep it, then:
cd agent-hub
bash scripts/init-git.sh                       # rebuilds the commit; safe to re-run
git remote add origin git@github.com:<you>/agent-hub.git
git push -u origin main
```

**Why this script exists:** the workspace I build in does **not persist `.git`
directories** between sessions, while all file content does. So history can vanish
while the work stays. `scripts/init-git.sh` rebuilds a clean, reproducible commit
from content and is idempotent — run it any time before pushing.

**Verify:** the GitHub page shows 347 files, `README.md` renders, and
`THIRD_PARTY_NOTICES.md` is present.

---

## 4. Obsidian vault — three ways, pick one

### 4a. Attach a redacted snapshot (fastest) 🔒

```bash
# macOS / Linux, from the PARENT folder of your vault
cd ~/Documents
zip -r vault.zip MyVault \
    -x "MyVault/.obsidian/workspace*" "MyVault/.trash/*" "MyVault/.git/*" "MyVault/.datafarm/*"
```
Windows PowerShell:
```powershell
cd $HOME\Documents
Compress-Archive -Path .\MyVault -DestinationPath .\vault.zip
```
Then drag `vault.zip` into chat.

**Scan it first** (I can, or you can locally):
```bash
python3 agent-hub/obsidian-datafarm/src/vault_probe.py /path/to/MyVault --test-write
```
It reports note counts, plugins, orphans, write access, and any AWS/GitHub/Slack/
OpenAI key, bearer token, private key block or DB connection string — **printing
redacted previews only**. Delete what it flags before sharing.

**Then I run:**
```bash
python3 agent-hub/obsidian-datafarm/src/vault_indexer.py /path/to/MyVault \
        --out /path/to/MyVault/.datafarm --reuse-layout
```
**Verify:** `.datafarm/graph.html` opens in a browser with no network, and
`stats.json` shows your real note and edge counts.

### 4b. Git (best for ongoing work) 🔒

```bash
cd /path/to/MyVault
printf '.obsidian/workspace.json\n.obsidian/workspace-mobile.json\n.trash/\n.datafarm/\n' > .gitignore
git init && git add -A && git commit -m "vault baseline"
# create a PRIVATE empty repo on GitHub, then:
git remote add origin git@github.com:<you>/myvault.git && git push -u origin main
```
Then give me a **read-only** fine-grained token for that one repo (Contents: Read,
7 days). I clone, index, and return changes as a patch you apply:
```bash
git -C vault diff > datafarm-changes.patch          # I produce this
cd /path/to/MyVault && git apply --check datafarm-changes.patch && git apply datafarm-changes.patch
```
I never need write access.

### 4c. Live MCP — only with a local agent 🔒

This **cannot** work from this chat: the plugin binds to `127.0.0.1` on *your*
machine and I have no route to it.

1. Obsidian → Settings → Community plugins → install **Local REST API**
2. Settings → Local REST API → note the API key; enable the **HTTP server** (port
   27123) to avoid trusting its self-signed CA
3. Qwen Chat Desktop: chat window → **MCP** → MCP settings → **Add MCP** → JSON:
   ```json
   {
     "mcpServers": {
       "obsidian": {
         "url": "http://127.0.0.1:27123/mcp/",
         "headers": { "Authorization": "Bearer <your-api-key>" }
       }
     }
   }
   ```
   Or Qwen Code:
   ```bash
   qwen mcp add --transport http obsidian http://127.0.0.1:27123/mcp/ \
     --header "Authorization: Bearer <your-api-key>"
   ```
**Keep the API key out of chat** — it belongs in that local config file only.

---

## 5. Long intraday history — only if you want the 508%/313R claims actually tested 🔒

Yahoo's free endpoint gives **~60 days of 5-minute bars**, so a six-year intraday
backtest is impossible from free data. To test those claims:

1. Export 5-minute bars for one Nasdaq instrument covering the claimed period, from
   your broker, Databento, Polygon, FirstRate Data or similar.
2. Save it in Yahoo chart-JSON shape (`{"chart":{"result":[{"meta":{...},
   "timestamp":[...],"indicators":{"quote":[{"open":[...],"high":[...],"low":[...],
   "close":[...],"volume":[...]}]}}]}}`), as `.json` or `.json.gz`. A folder of such
   files is merged and de-duplicated automatically.
3. Attach it. Then:
   ```bash
   python3 agent-hub/trader-console/console.py evidence QQQ --strategy ema12-flip --offline YOUR_FILE
   ```

---

## 6. Micro-entreprise + ACRE 🔒 (cannot be delegated)

**Why yours:** identity, signature, and `autoentrepreneur.urssaf.fr` **refused my
connection outright**. I can draft everything but cannot file.

1. Go to the official portal `https://www.autoentrepreneur.urssaf.fr` → *Créer mon
   auto-entreprise* (the URSSAF site blocked my probe, so verify the exact click path
   there; `economie.gouv.fr` and `entreprendre.service-public.gouv.fr` both loaded
   fine and describe the same procedure).
2. Activity: **prestations de services / profession libérale non réglementée (BNC)**
   for consulting, audits, development and writing.
3. **Request ACRE at creation.** Rates verified on `economie.gouv.fr` (dated
   06/03/2026): BNC social charges **25.6%** from 01/01/2026; **ACRE reduces BNC to
   12.8%** until the end of the third quarter after start — **but for creations from
   01/07/2026 the exemption drops from 50% to 25%.** So creating sooner is worth real
   money.
4. Ceilings verified on URSSAF and service-public: **€83,600** for services (BIC and
   BNC), €203,100 for goods sales. CFP **0.2%**. Note: micro-entrepreneurs get **no
   France Travail unemployment rights**.
5. **Verify before relying on any figure:** one secondary source still quoted 24.6%
   for BNC and another quoted a €37,500 ceiling; the official sources say 25.6% and
   €83,600. Also confirm whether your activity is Cipav-classified (23.2%).

---

## 7. PEA + bank 🔒 (your €10 action)

**Why yours:** KYC, ID, signature.

1. Open a **PEA** with any French bank or broker that offers one. Fund it with **€10**.
   The favourable tax treatment has a **5-year clock that starts at opening, not at
   contribution** — with a Switzerland move in your plans, opening now is the whole
   point.
2. Set up a **monthly standing order** into one diversified UCITS ETF, funded from
   service income. Automation's real edge here is behavioural.
3. **Verify:** the flat tax (PFU) on securities gains is reported at **31.4% for
   2026** (12.8% + 18.6%), up from 30%. Confirm on `impots.gouv.fr` (reachable, HTTP
   200) before relying on it.
4. **Before moving to Switzerland:** private capital gains on movable assets are
   generally tax-free there, but there is an annual **wealth tax**, standard VAT is
   **8.1%**, and trading frequently enough risks classification as a **professional
   securities dealer**, which costs you that exemption. Active day trading is exactly
   what triggers it. Take this to a cross-border adviser before you move.

---

## 8. Broker — paper only, and deliberately NOT connected to me 🔒

I will not wire an agent to live order placement, and from this chat I could not
anyway (your broker's MCP server runs on your machine).

If you want the pack's broker path for **paper** testing with a local agent:
1. Alpaca paper account → its official MCP server in Claude Desktop / Qwen Desktop
2. Keys in **environment variables only**, never in chat
3. Set the order tool to **"Needs approval"**, never "Always allow"
4. Keep `"paper": true` and `"require_stop": true` in `trader/config.json`

The guards are real and tested: a risk verdict is bound to the exact order *and* the
exact day, entries are refused when the market is closed, and `trader-console`
refuses `approve`, `decline`, `result`, `fill`, `flatten` and `log` before any
subprocess starts.

---

## 9. Freelance profile 🔒

**Why yours:** identity, and `malt.fr` returns **403** to my raw HTTP (I can still
read its published rate barometer via search).

1. Malt (France's strongest for TJM work), plus Upwork/Contra if you want volume.
2. Headline: name the **deliverable and the evidence**, not the title. For example:
   *"I verify AI-generated codebases: byte-exact replication, an independent test
   harness, and a defect/security report in 5 days."*
3. Portfolio: publish the `docs/RANKING-quant-labs-strategies.md` result — a viral
   508% strategy tested across 6 ETFs, **−282.88R at t = −24.75** — with the
   reproduction command. That is a sample nobody else has.
4. **Verify current rates yourself** before pricing: the public Malt barometer showed
   IT/digital average ≈ €520/day, Île-de-France ≈ €613, AI profiles ≈ €630 median vs
   €510 for developers, and **0–2 years experience data scientists around €359 mean
   with a €120 floor**. Price off your evidence, not off the top of the range.

---

## 10. Run everything

```bash
cd agent-hub
bash scripts/run-tests.sh          # 606 tests across four suites
cd trader-console
python3 console.py agents          # 16 agents
python3 console.py ask "does the ema12 rule actually work on QQQ"
python3 console.py evidence QQQ,SPY,TSLA,NVDA,AMD,IWM --strategy ema12-flip
python3 console.py pipeline TSLA --now "2026-10-19 10:16" --budget 5000
python3 console.py repl
```

---

## What is already working with no action from you

Verified HTTP 200 from my sandbox today: Yahoo Finance chart, spark and news RSS;
SEC EDGAR (`data.sec.gov` submissions, company tickers); Nasdaq Trader SymDir (both
files); GitHub clone/API/raw; PyPI; npm; `impots.gouv.fr`; `service-public.gouv.fr`;
`economie.gouv.fr`.

Known-blocked: House Clerk (403 → attach the file), URSSAF (connection refused →
yours), Malt (403 → I can still read its barometer via search), SSRN (403 direct, but
my page tool reaches it), Stooq (404 on every symbol format I tried → Yahoo covers
quotes).
