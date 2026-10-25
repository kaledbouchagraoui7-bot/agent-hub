# ondb SQLite Mode

SQLite materialized view for ondb. Use when you have >5000 entities in a single domain.

## Enable SQLite Mode

```bash
mkdir -p "$___X_CMD_ROOT_DATA/sqlite/mode"
: > "$___X_CMD_ROOT_DATA/sqlite/mode/sqlite_enable"
```

## How It Works

1. **redo.tsv remains the authority** — all writes append to redo.tsv
2. **ondb.db is a materialized view** — query-time replay from redo.tsv to SQLite
3. **WAL mode** — concurrent reads don't block writes

## Schema

```sql
-- Current state
SELECT * FROM entities WHERE type='Task';
SELECT * FROM props WHERE entity_id='t1';
SELECT * FROM links WHERE from_id='t1' AND rel='depends_on';

-- Get db path
x ondb dbpath -d memory/
-- → memory/ondb.db
```

## Direct SQLite Access

```bash
# Get db path
DBPATH=$(x ondb dbpath -d memory/)

# Open with sqlite3
sqlite3 "$DBPATH" "SELECT * FROM entities WHERE type='Task';"

# Complex JOIN
sqlite3 "$DBPATH" "
    SELECT e.id, e.type, p.value as name
    FROM entities e
    LEFT JOIN props p ON p.entity_id=e.id AND p.key='name'
    WHERE e.type='Task'
    ORDER BY e.id;
"

# Relation traversal
sqlite3 "$DBPATH" "
    SELECT l.to_id, e.type, p.value as name
    FROM links l
    JOIN entities e ON e.id=l.to_id
    LEFT JOIN props p ON p.entity_id=e.id AND p.key='name'
    WHERE l.from_id='t1' AND l.rel='depends_on';
"
```

## WAL Mode

```sql
-- WAL is enabled by default
PRAGMA journal_mode;  -- → wal

-- Checkpoint (merge wal into main db)
PRAGMA wal_checkpoint;

-- Busy timeout (default 5000ms)
PRAGMA busy_timeout;
```

## When to Use SQLite

- **>5000 entities in one domain**: AWK replay becomes slow
- **Complex queries**: JOIN, subquery, aggregation
- **Concurrent access**: Multiple readers + one writer
- **External tools**: BI tools, SQL clients

## When NOT to Use SQLite

- **Multiple domains**: Use separate ondb instances instead
- **Git-friendly workflow**: redo.tsv is text, .db is binary
- **Simple queries**: AWK is faster for <2000 entities

## Backup

```bash
# Backup while running (WAL mode)
sqlite3 ondb.db ".backup to ondb.db.backup"

# Or copy both files
cp ondb.db ondb.db-wal backup/
```
