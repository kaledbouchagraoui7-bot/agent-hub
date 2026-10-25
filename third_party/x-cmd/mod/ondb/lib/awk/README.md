# ondb AWK Library

Zero-dependency library for reading and querying ondb TSV logs.

## Quick Start

```awk
@include "ontology.awk"

BEGIN { FS="\t" }
{ onto_exec() }
END {
    # List all Task entities
    onto_ls("Task", _r)
    for (i = 1; i <= _r[L]; i++) {
        print _r[i]
    }
    
    # Get related entities
    onto_related("t1", "depends_on", "outgoing", _r)
    for (i = 1; i <= _r[L]; i++) {
        n = split(_r[i], _p, SUBSEP)
        print "rel=" _p[1] " id=" _p[2] " type=" _p[3]
    }
    
    # Validate
    onto_validate(_r)
    if (_r[L] > 0) {
        for (i = 1; i <= _r[L]; i++) {
            print "ERROR: " _r[i]
        }
    }
}
```

## Schema Check Example

```awk
@include "schema.awk"

BEGIN { FS="\t" }
# Schema directives first
{ schema_exec() }
# Then data
{ onto_exec() }
END {
    # Validate each entity
    for (i = 1; i <= _onto_cnt; i++) {
        id = _onto_order[i]
        schema_validate_entity(id, _r)
        for (j = 1; j <= _r[L]; j++) {
            print _r[j]
        }
    }
    
    # Validate relations
    schema_validate_relations(_r)
    for (j = 1; j <= _r[L]; j++) {
        print _r[j]
    }
}
```

## API Reference

| Function | Args | Returns |
|----------|------|---------|
| `onto_exec()` | - | Parse current line into graph |
| `onto_ls(type, _ret)` | type or "" | Array of entity IDs |
| `onto_get(id)` | entity ID | Entity dict or "" |
| `onto_linked(id, rel, dir, _ret)` | id, rel, dir | Array of relations |
| `onto_related(id, rel, dir, _ret)` | id, rel, dir | Array of related entities with props |
| `onto_validate(_ret)` | - | Array of error messages |
| `onto_snapshot()` | - | Print TSV snapshot |
| `schema_exec()` | - | Parse schema directive |
| `schema_validate_entity(id, _ret)` | id | Errors for this entity |
| `schema_validate_relations(_ret)` | - | Errors for all relations |

## When to Use AWK

- **< 2000 entities**: Fastest option, zero startup cost
- **No dependencies**: Works on any POSIX system
- **Streaming**: Process log line by line, constant memory
