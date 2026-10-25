# ondb Python Library

Python library for reading and querying ondb TSV logs.

## Quick Start

```python
from ontology import Ondb

ondb = Ondb()
with open('ondb.tsv') as f:
    ondb.load(f)

# List all Task entities
for eid, etype, name in ondb.ls('Task'):
    print(eid, name)

# Get entity
entity = ondb.get('t1')
print(entity['type'], entity['props'])

# Get related entities
for rel in ondb.related('t1', 'depends_on', 'outgoing'):
    print(rel['relation'], rel['entity']['id'], rel['entity']['props'])

# Validate
for err in ondb.validate():
    print("ERROR:", err)
```

## Schema Check Example

```python
from ontology import Ondb

ondb = Ondb()
with open('ondb.tsv') as f:
    ondb.load(f)

# Check required properties
for eid, e in ondb.entities.items():
    if not e['alive']:
        continue
    if e['type'] == 'Task':
        if 'title' not in e['props']:
            print(f"{eid}: missing required property 'title'")
        if 'status' in e['props'] and e['props']['status'] not in ('open', 'done'):
            print(f"{eid}: invalid status")

# Check dangling links
for err in ondb.validate():
    print("ERROR:", err)
```

## Custom Query Example

```python
# Find all tasks blocked by open tasks
for eid, e in ondb.entities.items():
    if e['type'] == 'Task' and e['props'].get('status') == 'open':
        for rel in ondb.related(eid, 'blocks', 'outgoing'):
            blocked = rel['entity']
            print(f"{eid} blocks {blocked['id']} ({blocked['props'].get('name', '')})")
```

## API Reference

| Method | Args | Returns |
|--------|------|---------|
| `load(lines)` | file iterator | - |
| `ls(type=None)` | type or None | [(eid, type, name), ...] |
| `get(id)` | entity ID | dict or None |
| `linked(id, rel, direction)` | id, rel, dir | [(rel, target, type, props), ...] |
| `related(id, rel, direction)` | id, rel, dir | [{relation, entity}, ...] |
| `validate()` | - | [error strings] |

## When to Use Python

- **2000-10000 entities**: Best balance of speed and features
- **Rich data structures**: dicts, lists, sets for complex logic
- **AI integration**: Easy to embed in Python-based AI pipelines
