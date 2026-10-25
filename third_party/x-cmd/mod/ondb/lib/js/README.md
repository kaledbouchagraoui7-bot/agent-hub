# ondb JavaScript Library (Bun)

JavaScript library for reading and querying ondb TSV logs.
Optimized for Bun runtime.

## Quick Start

```javascript
import { Ondb } from './ontology.js';

const ondb = new Ondb();
const text = await Bun.file('ondb.tsv').text();
ondb.load(text);

// List all Task entities
for (const [eid, etype, name] of ondb.ls('Task')) {
    console.log(eid, name);
}

// Get entity
const entity = ondb.get('t1');
console.log(entity.type, entity.props);

// Get related entities
for (const rel of ondb.related('t1', 'depends_on', 'outgoing')) {
    console.log(rel.relation, rel.entity.id, rel.entity.props);
}

// Validate
for (const err of ondb.validate()) {
    console.log("ERROR:", err);
}
```

## Schema Check Example

```javascript
import { Ondb } from './ontology.js';

const ondb = new Ondb();
ondb.load(await Bun.file('ondb.tsv').text());

// Check required properties
for (const [eid, e] of ondb.entities) {
    if (!e.alive) continue;
    if (e.type === 'Task') {
        if (!e.props.title) {
            console.log(`${eid}: missing required property 'title'`);
        }
        if (e.props.status && !['open', 'done'].includes(e.props.status)) {
            console.log(`${eid}: invalid status`);
        }
    }
}

// Check dangling links
for (const err of ondb.validate()) {
    console.log("ERROR:", err);
}
```

## Custom Query Example

```javascript
// Find all tasks blocked by open tasks
for (const [eid, e] of ondb.entities) {
    if (e.type === 'Task' && e.props.status === 'open') {
        for (const rel of ondb.related(eid, 'blocks', 'outgoing')) {
            const blocked = rel.entity;
            console.log(`${eid} blocks ${blocked.id} (${blocked.props.name || ''})`);
        }
    }
}
```

## API Reference

| Method | Args | Returns |
|--------|------|---------|
| `load(text)` | TSV string | - |
| `ls(type)` | type or null | [[eid, type, name], ...] |
| `get(id)` | entity ID | object or null |
| `linked(id, rel, direction)` | id, rel, dir | [[rel, target, type, props], ...] |
| `related(id, rel, direction)` | id, rel, dir | [{relation, entity}, ...] |
| `validate()` | - | [error strings] |

## When to Use JS (Bun)

- **2000-10000 entities**: Fast startup, modern JS features
- **Type safety**: Easy to add TypeScript definitions
- **Bun ecosystem**: Fast I/O, built-in bundler

## Installation

```bash
bun install  # if published as npm package
# or just copy lib/js/ontology.js + ondb_core.js
```
