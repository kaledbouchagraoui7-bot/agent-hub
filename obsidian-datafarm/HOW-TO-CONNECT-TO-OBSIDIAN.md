# How to connect the agent to Obsidian

**Read this first.** It answers one question: *how does the assistant get read/write access to your vault?*

---

## 0. The hard constraint (verified in this session)

The assistant runs in a **sandboxed Linux workspace** at `/home/user`, as `root`, with:

| Capability | Status | Verified by |
|---|---|---|
| Read/write files under `/home/user` | ✅ yes | `touch` probe, persists across messages |
| Outbound HTTPS from sandbox | ✅ yes | `urllib` → `pypi.org` = HTTP 200 |
| `git`, `python3` (3.11), `node` (v20), `pip` | ✅ present | `--version` output |
| `curl` | ❌ not installed | use `python3 -m urllib` |
| Inbound connections from your machine | ❌ **impossible** | sandbox has no public endpoint |
| Reach `127.0.0.1:27124` on *your* machine | ❌ **impossible** | loopback ≠ this sandbox |

**Consequence:** any Obsidian plugin that serves a *local* API (Local REST API, obsidian-git daemon, MCP over localhost) **cannot be called by this chat agent directly** — localhost means *your* computer, not the sandbox. Those paths work only if you run a **local** agent (Qwen Code CLI / Qwen Chat Desktop with MCP).

So there are exactly **two families** of connection:

* **A. Files come to me** (vault copied/synced into the workspace) → works in *this* chat, today.
* **B. I go to your files** (live MCP/REST from a local agent) → needs a local agent runtime.

---

## 1. Decision table

| # | Path | Live? | Write-back | Setup effort | Risk | Use when |
|---|---|---|---|---|---|---|
| **A1** | **Attach vault** (zip/folder dragged into chat) | no | I return files/zip | 1 min | low | Vault < ~50 MB, one-shot or occasional work |
| **A2** | **Git pull into workspace** (private repo + 7-day read-only token) | no (re-pull on demand) | I emit a **patch**; you `git apply` | 10 min | medium | Ongoing project, real vault, full history |
| **A3** | **Mounted/synced folder** (vault folder placed in the workspace dir) | near-live | direct write | depends on client | low | Your client supports folder mounting |
| **B1** | **Local REST API + its built-in MCP server** (Obsidian plugin) | **yes** | yes, section-level PATCH | 10 min | medium | You run **Qwen Chat Desktop** (MCP-capable) |
| **B2** | **Qwen Code CLI + MCP** (filesystem or obsidian MCP server) | **yes** | yes | 15 min | medium | You want a terminal agent with vault tools |

> B1/B2 are the *right long-term* answer for a "data farm" that ingests continuously. A2 is the *right answer for this chat*, and it is what I recommend we start with.

---

## 2. Path A1 — attach the vault (fastest, do this now)

1. Close Obsidian (so no half-written files).
2. Create a **redacted export**:
   ```bash
   # macOS/Linux — run in the PARENT folder of your vault
   cd ~/Documents                      # <- adjust
   zip -r vault-snapshot.zip MyVault \
       -x "MyVault/.obsidian/workspace*" "MyVault/.trash/*" "MyVault/.git/*"
   ```
   Windows (PowerShell):
   ```powershell
   cd $HOME\Documents
   Compress-Archive -Path .\MyVault -DestinationPath .\vault-snapshot.zip
   ```
3. Drag `vault-snapshot.zip` into this chat.
4. I will run:
   ```bash
   python3 src/vault_probe.py /home/user/MyVault --test-write
   python3 src/vault_indexer.py /home/user/MyVault --out /home/user/MyVault/.datafarm
   ```
5. **Connection is proven** when the probe prints `status: CONNECTED`.

**Before you attach it:** run the secret scan locally (`python3 src/vault_probe.py <vault>`) and delete anything it flags. The probe only ever prints redacted previews, but do not send me credentials at all.

---

## 3. Path A2 — git pull (recommended for the larger project)

**On your machine:**
```bash
cd /path/to/MyVault
git init && git add -A && git commit -m "vault baseline"
# create a PRIVATE repo, then:
git remote add origin git@github.com:you/myvault.git
git push -u origin main
```
Add a `.gitignore` first:
```
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.trash/
.datafarm/
```
Create a **fine-grained PAT**: GitHub → Settings → Developer settings → Fine-grained tokens →
repo = `myvault` only, permission = **Contents: Read-only**, expiry = **7 days** (minimum supported).

**Then give me, in chat:**
```
repo: https://github.com/you/myvault.git
token: <paste>
```
I run (token stays in the remote URL, never written to a file, `.git/config` is excluded from snapshots):
```bash
git clone --depth 1 "https://x-access-token:$TOKEN@github.com/you/myvault.git" /home/user/vault
python3 src/vault_probe.py /home/user/vault --test-write
```

**Write-back without giving me push rights** (recommended):
```bash
# I produce this in the sandbox:
git -C /home/user/vault diff > /home/user/datafarm-changes.patch
# you apply it locally:
cd /path/to/MyVault && git apply --check datafarm-changes.patch && git apply datafarm-changes.patch
```
**Revoke the token when we are done.** Do not paste a token with write scope.

---

## 4. Path B1 — Local REST API + MCP (live, needs a local agent)

Verified against the plugin's own README (`coddingtonbear/obsidian-local-rest-api`):

* Install **Local REST API** from Obsidian → Settings → Community plugins.
* Settings → Local REST API gives you an **API key**; HTTPS on `127.0.0.1:27124`, optional plain HTTP on `127.0.0.1:27123`.
* It ships a **built-in MCP server** at `https://127.0.0.1:27124/mcp/` (Bearer auth), plus REST CRUD, **section-level PATCH** (heading / block / frontmatter key), full-text + JsonLogic search, **SSE event stream**, tag listing, and command execution.
* Its CA cert is downloadable at `/obsidian-local-rest-api.crt` and is **name-constrained to localhost** — trusting it cannot let anyone impersonate other sites.

Qwen Chat Desktop MCP config (chat window → **MCP** → MCP settings → **Add MCP** → JSON):
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
(Use the HTTP port, or trust the plugin CA for the HTTPS port.)

Qwen Code CLI:
```bash
qwen mcp add --transport http obsidian http://127.0.0.1:27123/mcp/ \
  --header "Authorization: Bearer <your-api-key>"
```

Sanity check from your machine:
```bash
python3 - <<'EOF'
import json,ssl,urllib.request
req=urllib.request.Request("https://127.0.0.1:27124/", headers={"Authorization":"Bearer <key>"})
print(json.load(urllib.request.urlopen(req, context=ssl._create_unverified_context())))
EOF
```

---

## 5. Path B2 — Qwen Code CLI, no plugin at all

If the vault is just a folder, a filesystem MCP server is enough:
```bash
npm i -g @qwen-code/qwen-code
cd /path/to/MyVault && qwen      # agent runs with the vault as its working dir
```
Then point it at the tools in this repo:
```bash
python3 /path/to/obsidian-datafarm/src/vault_indexer.py . --out .datafarm --reuse-layout
```

---

## 6. Security rules for every path

1. **Never** paste a write-capable credential into chat. Read-only, 7-day expiry, single repo.
2. **Never** paste the Local REST API key into a *chat* — it belongs in the local MCP config file only.
3. Run `vault_probe.py` **before** sharing any snapshot; it flags AWS/GitHub/Slack/OpenAI keys, bearer tokens, private key blocks, and DB connection strings.
4. Keep `.obsidian/` out of the share unless you want me to review plugins (it contains `community-plugins.json`, workspace state, and sometimes plugin data with tokens).
5. I write to `<vault>/.datafarm/` only, and never delete notes. Destructive operations require your explicit go-ahead.
6. Revoke/rotate any token the moment the task ends.

---

## 7. Tell me these four things and I will wire it up

1. **Path**: A1 / A2 / A3 / B1 / B2
2. **Vault size**: number of notes, and whether it is mostly text or has heavy attachments
3. **OS + Obsidian version**, and whether you use **Obsidian Sync / iCloud / Dropbox / git**
4. **The larger project**: what is the data farm *for* (source data, expected note volume, who consumes the graph)
