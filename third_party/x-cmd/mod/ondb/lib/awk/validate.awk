# validate.awk - Validate graph integrity
# Vars: ONTO_SCHEMA (1 if schema file is piped before data)

BEGIN { FS="\t" }

# First section: schema directives (if ONTO_SCHEMA and $1 is type/relation)
ONTO_SCHEMA == "1" && ($1 == "type" || $1 == "relation") {
    schema_exec()
    next
}

# Data section
{ onto_exec() }

END {
    # Basic integrity: dangling refs
    n = onto_validate(_r)
    for (i = 1; i <= _r[L]; i++)
        _out[++_out[L]] = _r[i]

    # Schema: entity validation (required, forbidden, enum)
    if (ONTO_SCHEMA == "1") {
        for (i = 1; i <= _onto_cnt; i++) {
            id = _onto_order[i]
            if (!_onto_alive[id]) continue
            sn = schema_validate_entity(id, _sr)
            for (j = 1; j <= _sr[L]; j++)
                _out[++_out[L]] = _sr[j]
            n += sn
        }

        # Schema: relation validation (types, cardinality, acyclic)
        sn = schema_validate_relations(_sr)
        for (j = 1; j <= _sr[L]; j++)
            _out[++_out[L]] = _sr[j]
        n += sn
    }

    if (n == 0) {
        print "Graph is valid."
    } else {
        for (i = 1; i <= _out[L]; i++)
            print "  - " _out[i]
    }
    exit (n > 0)
}
