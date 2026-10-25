---
name: ondb
description: A logical analysis and reasoning tool for AI. Use when decomposing documents into structured knowledge, querying entities and relations, validating consistency, or indexing files. Trigger on "remember", "what do I know about", "link X to Y", "show dependencies", "analyze this document", entity CRUD, or cross-skill data access.
---

# Ondb

A typed vocabulary + constraint system for representing knowledge as a verifiable graph. The TSV log is the protocol — query it with AWK, Python, JS, or SQLite.

## Core Concept

Ondb is a **logical analysis and reasoning tool for AI**. It gives AI the ability to decompose unstructured content into structured knowledge, reason along relationship chains, and validate logical consistency.

Everything is an **entity** with a **type**, **properties**, and **relations** to other entities. All mutations are appended as TSV lines to a log file.

```
Entity: { id, type, properties }
Relation: { from_id, relation_type, to_id, properties }
```

**Multiple ondb instances are the default approach.** Each sub-domain, each article, each analysis perspective can have its own independent ondb instance. This is by design — small focused ondb instances are easier to reason about, validate, and maintain.

## Application Scenarios

### Scenario 1: Project Memory (Index)

Index files in a project. The ondb instance points to files but doesn't duplicate their content.

```bash
x ondb add --datadir memory/ --type Document --name "API Design" --id doc_api \
    -- path=docs/api-design.md
x ondb add --datadir memory/ --type Person --name "Alice" --id p1
x ondb link --datadir memory/ --from doc_api --rel authored_by --to p1
```

### Scenario 2: Knowledge Base (Analysis)

Decompose an article into structured knowledge. The ondb instance IS the analysis result.

```bash
x ondb add --datadir kb/ --type Pattern --name "Saga" --id saga
x ondb add --datadir kb/ --type Problem --name "Distributed Consistency" --id prob_dc
x ondb add --datadir kb/ --type Article --name "Saga Deep Dive" --id art_001 \
    -- path=articles/saga.md
x ondb link --datadir kb/ --from saga --rel solves --to prob_dc
x ondb link --datadir kb/ --from art_001 --rel covers --to saga
```

After modeling 50 articles, you can reason: "What patterns solve distributed consistency?" → find Saga → find related articles → find complementary patterns.

### Scenario 3: Codebase Analysis (Multi-perspective)

Model the same codebase from different angles in one ondb instance. Type = concept, each with distinct required props.

```bash
# Architecture perspective
x ondb add --datadir code/ --type Module --name "auth" --id mod_auth -- path=src/auth/

# OOP perspective
x ondb add --datadir code/ --type Class --name "JWTAuth" --id cls_jwt -- file=src/auth/jwt.py

# API perspective
x ondb add --datadir code/ --type Endpoint --name "POST /login" --id ep_login

# Cross-perspective reasoning
x ondb link --datadir code/ --from ep_login --rel handled_by --to cls_jwt
x ondb link --datadir code/ --from cls_jwt --rel belongs_to --to mod_auth

# Query across perspectives: which module handles POST /login?
# Endpoint → Class → Module (two hops)
```

### Scenario 4: Task Management (Primary Store)

Lightweight structured data lives directly in an ondb instance. No external files needed.

```bash
x ondb add --datadir work/ --type Task --name "Fix auth bug" --id t1 \
    -- status=open priority=high
x ondb add --datadir work/ --type Task --name "Write tests" --id t2 \
    -- status=open
x ondb link --datadir work/ --from t1 --rel blocks --to t2
x ondb query --datadir work/ --type Task --where status=open
```

### Scenario 5: Meeting Notes (Index + Facts)

```bash
x ondb add --datadir notes/ --type Event --name "Sprint Planning" --id ev1 \
    -- date=2026-05-27 path=notes/2026-05-27-sprint.md
x ondb add --datadir notes/ --type Person --name "Bob" --id p2
x ondb link --datadir notes/ --from ev1 --rel attended_by --to p2 \
    -- role=facilitator
```

## Design Principles

### Spectrum: Casual → Designed

Ondb rewards deliberate design but can also be used casually:

| | Casual | Designed |
|---|---|---|
| Schema | None | Formal constraints |
| Types | Free-form | Clear concept system |
| Reasoning | Weak (find things) | Strong (chain inference) |
| Best for | Quick memory | Long-term knowledge base |

### Type = Concept

When merging multiple perspectives, each type must be a clear concept with no ambiguity. Rule: **same type name = same concept, always.** If "Service" could mean a code module or a runtime process, split into `Module` and `Process`.

### Required Props Define Identity

```bash
# In schema.tsv (flat TSV, no JSON/YAML):
type	Module
req	Module	path

type	Process
req	Process	port

type	Service
req	Service	kind
enum	Service	kind	module,process
```

Schema directives: `type`, `req` (required), `forbid` (forbidden), `enum` (allowed values), `rel` (relation), `rfrom`/`rto` (allowed types), `rcard` (cardinality), `racyclic` (no cycles).

### Sub-domain Analysis → Main Ondb

Multiple ondb instances are good — each is a complete, independent analysis. Integrating into a main ondb instance is only needed when sub-domains share same-level semantics that require deep joint reasoning.

```
analysis/
  auth/ondb.tsv       ← complete analysis of auth domain, usable standalone
  api/ondb.tsv        ← complete analysis of API design, usable standalone
  arch/ondb.tsv       ← complete dependency analysis, usable standalone
  main/ondb.tsv       ← refactored integration for cross-domain reasoning
```

No merge needed: query each sub-domain separately, combine results manually.

Merge needed: when concepts from different domains relate at the same semantic level, and split ontologies cannot express the cross-domain relationships.

```
# Cross-domain chain: only visible after integration
POST /login → handled_by → JWTAuth → uses_pattern → Saga → solves → Consistency

# The merge is NOT data concatenation. It is:
# 1. Refactor sub-domain's concept system to align with main ondb instance
# 2. Re-examine facts and relations in the broader context
# 3. Write curated results into main ondb instance
```

## Directory Structure

```
<datadir>/                          # specified via --datadir flag
├── ONDB.DESC.txt           # Required. What this ondb instance is about
├── ONDB.SKILL.md           # Optional. Skill description + usage methods + experience
├── rule/                       # Optional. LLM self-check rules for semantic consistency
│   ├── consistency.yml         #   e.g. no orphan links, consistent type naming
│   └── naming.yml              #   e.g. naming conventions for types and relations
├── snapshot.<epoch_ms>         # Compact snapshot (current state as TSV directives)
├── log.<epoch_ms>              # Incremental log after snapshot
├── ondb.tsv                # Initial log (deleted after first compact)
└── ondb.db                 # Optional. SQLite materialized view
```

- **ONDB.DESC.txt** is required — it identifies the directory as an ondb instance and describes its purpose
- **ONDB.SKILL.md** and **rule/** are optional, added as the ondb instance matures and needs documentation/governance
- The `ONDB.` prefix serves as a directory marker — seeing it tells you this is an ondb directory

## When to Use

| Trigger | Action |
|---------|--------|
| "Remember that..." | `x ondb add` |
| "What do I know about X?" | `x ondb get --id X` |
| "Link X to Y" | `x ondb link` |
| "Show all tasks for project Z" | `x ondb linked --id Z` |
| "What depends on X?" | `x ondb linked --id X --direction incoming` |
| Skill needs shared state | Read/write TSV log |

## TSV Log Format

Default file: `ondb.tsv` in current directory.

```
# Comments start with #, empty lines ignored
add	Person	pers_001	1716816000000	name	Alice	email	alice@example.com
add	Project	proj_001	1716816000001	name	Website Redesign	status	active
add	Task	task_001	1716816000002	title	Fix bug	status	open	priority	high
link	proj_001	has_task	task_001	1716816000003
link	pers_001	assigned_to	task_001	1716816000004
set	task_001	1716816000005	status	done
rm	task_002	1716816000006
unlink	proj_001	has_task	task_002	1716816000007
```

### Directives

| Directive | Fields | Meaning |
|-----------|--------|---------|
| `add` | type, id, epoch_ms, key val pairs... | Create entity with properties |
| `set` | id, epoch_ms, key val pairs... | Update entity properties |
| `rm` | id, epoch_ms | Delete entity |
| `link` | from, rel, to, epoch_ms, key val pairs... | Create relation |
| `unlink` | from, rel, to, epoch_ms | Remove relation |

### Escaping

- Tab in values: `\t`
- Newline in values: `\n`
- Backslash: `\\`

## CLI Usage

### Create Entity

```bash
# Auto-generated ID (pers_001, pers_002, ...)
x ondb add --type Person --name Alice

# Explicit ID
x ondb add --type Project --name "My Project" --id proj_001

# With properties
x ondb add --type Task --name "Write docs" priority=high due=2026-06-01
```

### Query

```bash
# Get single entity
x ondb get --id p_001

# List all entities
x ondb ls

# List by type
x ondb ls --type Task

# Filter by property values (multiple --where for AND)
x ondb query --type Task --where status=open
x ondb query --type Task --where status=open --where priority=high
# Note: --where falls back to AWK when JS/Python backend is active

# JSON output
x ondb ls --type Task --json
x ondb get --id p_001 --json
```

### Link Entities

```bash
# Create relation
x ondb link --from proj_001 --rel has_task --to task_001

# View relations (outgoing)
x ondb linked --id proj_001

# View relations (incoming — who links TO this entity)
x ondb linked --id task_001 --direction incoming

# Filter by relation type
x ondb linked --id proj_001 --rel has_task

# Both directions
x ondb linked --id p_001 --direction both
```

### Related Entities (Full Info)

`linked` returns relation metadata. `related` returns the **full entity** on the other side.

```bash
# What projects does task_001 belong to?
x ondb related --id task_001 --rel has_task --direction incoming

# What tasks are in proj_001?
x ondb related --id proj_001 --rel has_task --direction outgoing

# JSON output
x ondb related --id proj_001 --rel has_task --json
```

Output (TSV):
```
has_task	task_001	Task	title=Fix bug	status=open
has_task	task_002	Task	title=Write docs	status=done
```

Output (JSON):
```json
[
  {"relation":"has_task","entity":{"id":"task_001","type":"Task","props":{"title":"Fix bug","status":"open"}}},
  {"relation":"has_task","entity":{"id":"task_002","type":"Task","props":{"title":"Write docs","status":"done"}}}
]
```

### Update & Delete

```bash
# Update properties
x ondb set --id task_001 status=done

# Delete entity
x ondb rm --id task_002

# Remove relation
x ondb unlink --from proj_001 --rel has_task --to task_002
```

### Validate

```bash
# Check graph integrity and schema constraints
x ondb validate
x ondb validate
x ondb validate --datadir memory/ --schema memory/schema.tsv
```

What validate checks:
- **Dangling references**: links pointing to non-existent entities (from or to)
- **Required properties**: missing required props per schema.tsv
- **Forbidden properties**: props that should not exist per schema
- **Enum values**: values outside the allowed set
- **Relation types**: from/to types that don't match schema constraints
- **Cardinality**: one_to_one, one_to_many, many_to_one violations
- **Acyclic relations**: cycles in relations marked `racyclic` (e.g. `blocks`)

Validation is **separate from write** — run it after batch changes or before committing.

### Compact Log

Compress the append-only log into a snapshot. Old snapshots and logs are cleaned up automatically.

```bash
# Compact current directory
x ondb compact

# Compact specific directory
x ondb compact --datadir memory/
```

Output: `snapshot.<epoch_ms>` containing the current state as TSV directives. After compact, new changes go to `log.<epoch_ms>`.

### Get Paths

```bash
# Library paths for custom queries
x ondb libpath # → /path/to/ondb/lib
x ondb libpath awk # → .../lib/awk/ontology.awk
x ondb libpath py # → .../lib/py
x ondb libpath js # → .../lib/js
x ondb libpath sqlite # → .../lib/sqlite/README.md

# SQLite db path for direct SQL access
x ondb dbpath --datadir memory/ # → memory/ondb.db
```

## Output Formats

### TSV (default)

```
# x ondb ls
pers_001	Person	Alice
proj_001	Project	Website Redesign
task_001	Task	Fix bug

# x ondb get --id pers_001
id	pers_001
type	Person
ctime	1716816000000
mtime	1716816000000
prop	name=Alice
prop	email=alice@example.com

# x ondb linked --id proj_001
has_task	task_001	Task
```

### JSON

```bash
# x ondb ls --json
[{"id":"pers_001","type":"Person","name":"Alice"},...]

# x ondb get --id pers_001 --json
{"id":"pers_001","type":"Person","properties":{"name":"Alice","email":"alice@example.com"}}

# x ondb linked --id proj_001 --json
[{"rel":"has_task","id":"task_001","type":"Task"}]
```

## Core Types

| Type | Key Properties | Use Case |
|------|---------------|----------|
| Person | name, email, phone | People and contacts |
| Organization | name, type | Companies, teams |
| Project | name, status | Work containers |
| Task | title, status, priority | Actionable work items |
| Goal | description, target_date | Objectives |
| Event | title, start, end | Calendar items |
| Document | title, path, url | Files and links |
| Note | content, tags | Freeform notes |
| Location | name, address | Places |

## Relation Types

| Relation | From | To | Meaning |
|----------|------|----|---------|
| has_task | Project | Task | Project contains task |
| has_owner | Project/Task | Person | Ownership |
| assigned_to | Task | Person | Assignment |
| member_of | Person | Organization | Membership |
| blocks | Task | Task | Dependency |
| depends_on | Task/Project | Task/Project | Dependency |
| mentions | Document/Note | Any | Reference |

## Integration with digraph

The ondb TSV log is compatible with `x digraph` when using `di`/`done`/`fail` directives alongside `add`/`link`:

```bash
# In the same log file, you can mix ondb and digraph directives
add	Task	task_001	1716816000000	title	Setup CI
add	Task	task_002	1716816000001	title	Run tests
link	task_001	blocks	task_002	1716816000002
di	task_001	task_002	# digraph dependency
done	task_001	# mark as completed

# Then use digraph to find next executable tasks
x digraph next -f ondb.tsv
```

## Planning as Graph Transformation

Model multi-step plans as a sequence of graph operations:

```
Plan: "Schedule team meeting and create follow-up tasks"

1. x ondb add --type Event --name "Team Sync" --id event_001
2. x ondb link --from proj_001 --rel has_event --to event_001
3. x ondb add --type Task --name "Prepare agenda" --id task_010
4. x ondb link --from event_001 --rel has_task --to task_010
5. x ondb add --type Task --name "Send summary" --id task_011
6. x ondb link --from task_010 --rel blocks --to task_011
```

## Append-Only Rule

When working with existing ondb data, **append** changes instead of overwriting files. This preserves history and avoids clobbering prior definitions. The `set` and `rm` commands always append — they never modify existing lines.

> **Note**: `add`, `set`, `link`, and `rm` do **not** validate schema at write time. Validation is done separately via `x ondb validate`. This makes writes fast and atomic — the TSV log accepts anything, and correctness is checked on demand.

## Implementation

- **Protocol**: TSV append-only log is the authority — any language can read it
- **Default query engine**: AWK (via `x cawk`) — zero dependencies, fastest for <2000 entities
- **Optional backends**: Python (rich data structures), JS/Bun (modern), SQLite (indexed, >5k entities)

### AWK vs SQLite

AWK is the recommended and default path. Each sub-domain ondb instance stays small by design — AWK replay is millisecond-level for thousands of entities.

SQLite mode exists for one specific case: **a single domain with a genuinely large dataset** (e.g. 50k contacts, 10k indexed documents). In this case, AWK replay becomes slow and SQLite provides indexed O(log n) queries.

SQLite mode is NOT for:
- Multiple domains crammed into one ondb instance → use multiple ondb instances instead
- Avoiding proper sub-domain analysis → the right fix is smaller ondb instances

SQLite is a **materialized view** — it is automatically generated from the TSV log on first query. No manual setup needed. To force a rebuild, delete `ondb.db` and `.lines` files.

## Library Usage

ondb is a **protocol** — the TSV log is the authority. You can read and query it with any language.

### Find Library Paths

```bash
# Get library base directory
x ondb libpath
# → /path/to/ondb/lib

# Get specific language paths
x ondb libpath awk # → .../lib/awk/ontology.awk
x ondb libpath py # → .../lib/py
x ondb libpath js # → .../lib/js
x ondb libpath sqlite # → .../lib/sqlite/README.md
```

### Backend Selection Strategy

| Environment | Recommended Backend | Why |
|-------------|---------------------|-----|
| Default (no special setup) | **AWK** | Zero dependencies, fastest for <2000 entities |
| Python available | **Python** | Best balance, rich data structures |
| Node.js/Bun available | **JS (Bun)** | Modern JS, fast startup |
| `ondb.db` exists | **SQLite** | Direct SQL, indexed queries |

```bash
# Check what you have
which python3 && echo "Python available"
which bun && echo "Bun available"
which sqlite3 && ls ondb.db && echo "SQLite available"

# AWK is always the fallback
```

### Workflow Examples

#### Example 1: SQLite → AWK Pipeline

Extract data with SQLite (fast indexed query), then process with AWK:

```bash
# Step 1: SQLite extracts raw data
DBPATH=$(x ondb dbpath)
sqlite3 "$DBPATH" -separator '\t' "
    SELECT l.from_id, l.to_id, p.value
    FROM links l
    JOIN entities e ON e.id = l.to_id
    LEFT JOIN props p ON p.entity_id = l.to_id AND p.key = 'name'
    WHERE l.rel = 'blocks'
" > /tmp/blocking.tsv

# Step 2: AWK post-processes (counts, filters, formats)
awk -F'\t' '
    { count[$1]++; blocked[$1] = blocked[$1] " " $3 }
    END {
        for (task in count)
            print task " blocks " count[task] " tasks:" blocked[task]
    }
' /tmp/blocking.tsv
```

**When to use**: Complex SQL query + simple post-processing. SQLite does the heavy lifting, AWK does the formatting.

#### Example 2: SQLite → Python Analysis

Extract with SQL, analyze with Python:

```bash
DBPATH=$(x ondb dbpath)

sqlite3 "$DBPATH" -csv "
    SELECT e.id, e.type, p.key, p.value
    FROM entities e
    LEFT JOIN props p ON p.entity_id = e.id
    WHERE e.type IN ('Task', 'Project')
" | python3 -c "
import sys, csv
from collections import defaultdict

entities = defaultdict(dict)
for row in csv.reader(sys.stdin):
    eid, etype, key, val = row
    entities[eid]['type'] = etype
    if key:
        entities[eid][key] = val

# AI custom analysis: find projects with no open tasks
for eid, e in entities.items():
    if e['type'] == 'Project':
        # ... custom logic
        print(eid, e.get('name', ''))
"
```

**When to use**: Need Python data structures (dicts, sets) for complex analysis after SQL extraction.

#### Example 3: Raw TSV → AWK Streaming

Process redo.tsv directly without SQLite:

```bash
# Find all tasks blocked by overdue tasks
# (no SQLite needed — works on any POSIX system)
awk -F'\t' '
    # Pass 1: load all tasks
    $1=="add" && $2=="Task" {
        tasks[$3] = 1
        for (i=5; i<=NF; i+=2) {
            if ($i == "due") due[$3] = $(i+1)
            if ($i == "status") status[$3] = $(i+1)
        }
    }
    # Pass 2: find blocking relationships
    $1=="link" && $3=="blocks" && tasks[$2] && tasks[$4] {
        if (status[$2] == "open" && due[$2] < "2026-05-30")
            print "OVERDUE: " $2 " blocks " $4
    }
' ondb.tsv
```

**When to use**: Simple analysis on raw log, no setup needed, works everywhere.

#### Example 4: SQLite → JS (Bun) Dashboard

```bash
DBPATH=$(x ondb dbpath)

# Extract summary stats
sqlite3 "$DBPATH" -json "
    SELECT type, COUNT(*) as cnt FROM entities GROUP BY type
" | bun -e "
const data = JSON.parse(await Bun.stdin.text());
const total = data.reduce((s, r) => s + r.cnt, 0);
console.log('Total entities:', total);
for (const row of data) {
    const pct = ((row.cnt / total) * 100).toFixed(1);
    console.log(row.type + ': ' + row.cnt + ' (' + pct + '%)');
}
"
```

**When to use**: JSON output → JS processing for dashboards, reports, web APIs.

### Per-Language Details

See each `README.md` for complete API reference and schema check examples:

```bash
cat "$(dirname "$(x ondb libpath awk)")/README.md"  # AWK API
cat "$(x ondb libpath py)/README.md"        # Python API
cat "$(x ondb libpath js)/README.md"        # JS API
cat "$(x ondb libpath sqlite)"              # SQLite guide
```

### AI Custom Queries

When built-in commands are not enough, write custom code:

```python
# Example: find orphaned tasks (no parent project)
LIBPATH=$(x ondb libpath py)
python3 -c "
import sys; sys.path.insert(0, '$LIBPATH')
from ontology import Ondb

ondb = Ondb()
with open('ondb.tsv') as f:
    ondb.load(f)

for eid, e in ondb.entities.items():
    if e['type'] == 'Task':
        parents = ondb.related(eid, 'has_task', 'incoming')
        if not parents:
            print(f'Orphaned: {eid}')
"
```

```bash
# Example: find documents mentioning API
awk -F'\t' '
    $1=="add" && $2=="Document" && index($0,"API") { docs[$3]=1 }
    $1=="link" && $3=="authored_by" && docs[$2] { print $4 " authored " $2 }
' ondb.tsv
```

**Rule**: Built-in commands for quick operations. Custom code for complex graph logic.

### SQLite 配置

**WAL 模式（Write-Ahead Logging）已启用。**

ondb 的 SQLite 实例使用 `PRAGMA journal_mode=WAL` 作为默认配置，原因：
- 并发安全：多进程同时访问时自动排队（`busy_timeout=5000ms`），避免 `database is locked` 错误
- 读不阻塞写：查询操作不会阻塞 TSV → SQLite 的 replay 同步
- autocommit 性能更优：WAL 追加写入比 DELETE 模式的 journal 覆盖写入 fsync 更少

**⚠️ 已知限制**：
- WAL 产生额外的 `-wal` 和 `-shm` 临时文件（checkpoint 后自动清理）
- **NFS / 网络文件系统环境需要重新评估**：WAL 依赖共享内存机制（`-shm` 文件），某些网络文件系统不支持 mmap 或文件锁，可能导致数据损坏。如部署到 NFS，需测试 `PRAGMA journal_mode=DELETE` 是否更稳定
- 长时间运行的事务会阻止 WAL checkpoint，导致 `-wal` 文件膨胀。ondb 的查询都是短连接，此问题不显著
- 备份时需同时处理 `.db` + `.db-wal` 文件，或使用 SQLite 的 `.backup` 命令
