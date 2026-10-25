# schema.awk - Schema engine for ondb
#
# Schema TSV format:
#   type        <type>     cols        <col1> <col2> ...
#   type        <type>     required    <prop1>,<prop2>,...
#   type        <type>     forbidden   <prop1>,<prop2>,...
#   type        <type>     enum        <prop> <val1>,<val2>,...
#   type        <type>     ref         <prop> <target_type>
#   type        <type>     datetime    <prop>
#   relation    <rel>      from_types  <type1>,<type2>,...
#   relation    <rel>      to_types    <type1>,<type2>,...
#   relation    <rel>      cardinality <one_to_one|one_to_many|many_to_one|many_to_many>
#   relation    <rel>      acyclic     1
#
# This file provides:
#   schema_build()              - load schema from stdin (streaming mode)
#   schema_validate_entity()    - validate single entity
#   schema_validate_relations() - validate all relations
#   schema_cols(type)           - return column string for TSV output

# Schema data structures:
# _sch_type_cols[type]  = "id title status" (space-separated column names)
# _sch_type_req[type]  = "title,status"     (comma-separated)
# _sch_type_forb[type] = "prop1,prop2"
# _sch_type_enum[type, prop] = "val1,val2"
# _sch_type_ref[type, prop]  = target_type
# _sch_type_datetime[type, prop] = 1
# _sch_rel_from[rel]   = "type1,type2"
# _sch_rel_to[rel]    = "type1,type2"
# _sch_rel_card[rel]  = "one_to_one" etc
# _sch_rel_acyclic[rel] = 1

function schema_exec(    i, n, arr, prop) {
    if ($1 == "type") {
        if ($3 == "cols") {
            # Cols: $4..$NF are column names (space-separated in output)
            _sch_type_cols[$2] = ""
            for (i = 4; i <= NF; i++) {
                if (_sch_type_cols[$2] != "") _sch_type_cols[$2] = _sch_type_cols[$2] " "
                _sch_type_cols[$2] = _sch_type_cols[$2] $i
            }
        } else if ($3 == "required") {
            _sch_type_req[$2] = $4
        } else if ($3 == "forbidden") {
            _sch_type_forb[$2] = $4
        } else if ($3 == "enum") {
            _sch_type_enum[$2, $4] = $5
        } else if ($3 == "ref") {
            _sch_type_ref[$2, $4] = $5
        } else if ($3 == "datetime") {
            _sch_type_datetime[$2, $4] = 1
        }
    } else if ($1 == "relation") {
        if ($3 == "from_types") {
            _sch_rel_from[$2] = $4
        } else if ($3 == "to_types") {
            _sch_rel_to[$2] = $4
        } else if ($3 == "cardinality") {
            _sch_rel_card[$2] = $4
        } else if ($3 == "acyclic") {
            _sch_rel_acyclic[$2] = $4
        }
    }
}

function _sch_has(list, item,    n, arr, i) {
    n = split(list, arr, ",")
    for (i = 1; i <= n; i++)
        if (arr[i] == item) return 1
    return 0
}

# Return 1 if prop is a column for this type (defined in cols)
function _sch_is_col(type, prop,    cols, n, i, arr) {
    if (!((type) in _sch_type_cols)) return 0
    cols = _sch_type_cols[type]
    n = split(cols, arr, " ")
    for (i = 1; i <= n; i++)
        if (arr[i] == prop) return 1
    return 0
}

function schema_validate_entity(id, _ret,    type, req, forb, enumlist, i, arr, prop, errs, ref_target, ref_val) {
    _ret[L] = 0; errs = 0
    type = _onto_type[id]
    if ((type) in _sch_type_req) {
        req = _sch_type_req[type]
        split(req, arr, ",")
        for (i in arr) {
            prop = arr[i]
            if (!((id, prop) in _onto_prop)) {
                _ret[++_ret[L]] = id ": missing required property '" prop "'"
                errs++
            }
        }
    }
    if ((type) in _sch_type_forb) {
        forb = _sch_type_forb[type]
        split(forb, arr, ",")
        for (i in arr) {
            prop = arr[i]
            if (((id, prop) in _onto_prop)) {
                _ret[++_ret[L]] = id ": forbidden property '" prop "'"
                errs++
            }
        }
    }
    # Check enums
    for (key in _sch_type_enum) {
        split(key, parts, SUBSEP)
        if (parts[1] != type) continue
        prop = parts[2]
        enumlist = _sch_type_enum[key]
        val = _onto_prop[id, prop]
        if (val != "" && !_sch_has(enumlist, val)) {
            _ret[++_ret[L]] = id ": property '" prop "' value '" val "' not in enum {" enumlist "}"
            errs++
        }
    }
    # Check refs
    for (key in _sch_type_ref) {
        split(key, parts, SUBSEP)
        if (parts[1] != type) continue
        prop = parts[2]
        ref_target = _sch_type_ref[key]
        ref_val = _onto_prop[id, prop]
        if (ref_val != "" && !((ref_val) in _onto_alive)) {
            _ret[++_ret[L]] = id ": ref '" prop "' points to non-existent entity '" ref_val "'"
            errs++
        }
    }
    # Check datetime format (rough check: must not be empty if required)
    for (key in _sch_type_datetime) {
        split(key, parts, SUBSEP)
        if (parts[1] != type) continue
        prop = parts[2]
        val = _onto_prop[id, prop]
        if (val != "" && !_sch_is_valid_datetime(val)) {
            _ret[++_ret[L]] = id ": property '" prop "' value '" val "' is not a valid datetime"
            errs++
        }
    }
    return errs
}

function _sch_is_valid_datetime(val,    d, t) {
    # Accept ISO 8601: 2026-05-27 or 2026-05-27T14:30:00 or 2026-05-27 14:30:00
    if (val ~ /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/) return 1
    if (val ~ /^[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}(:[0-9]{2})?/) return 1
    return 0
}

function schema_validate_relations(_ret,    i, id, rel, from_type, to_type, errs, from_id, to_id, counts, node, stack, visited, has_cycle) {
    _ret[L] = 0; errs = 0

    for (i = 1; i <= _onto_lcnt; i++) {
        if (_onto_lfrom[i] == "") continue
        rel = _onto_lrel[i]
        from_id = _onto_lfrom[i]
        to_id = _onto_lto[i]

        # Check from_types
        if ((rel) in _sch_rel_from) {
            from_type = _onto_type[from_id]
            if (!_sch_has(_sch_rel_from[rel], from_type)) {
                _ret[++_ret[L]] = "relation " rel ": from entity " from_id " type " from_type " not in {" _sch_rel_from[rel] "}"
                errs++
            }
        }
        # Check to_types
        if ((rel) in _sch_rel_to) {
            to_type = _onto_type[to_id]
            if (!_sch_has(_sch_rel_to[rel], to_type)) {
                _ret[++_ret[L]] = "relation " rel ": to entity " to_id " type " to_type " not in {" _sch_rel_to[rel] "}"
                errs++
            }
        }
    }

    # Cardinality checks
    _sch_sep = SUBSEP
    for (rel in _sch_rel_card) {
        card = _sch_rel_card[rel]
        if (card == "") continue
        delete counts
        for (i = 1; i <= _onto_lcnt; i++) {
            if (_onto_lfrom[i] == "") continue
            if (_onto_lrel[i] != rel) continue
            from_id = _onto_lfrom[i]; to_id = _onto_lto[i]
            counts["f", from_id] = counts["f", from_id] + 0 + 1
            counts["t", to_id]   = counts["t", to_id]   + 0 + 1
        }
        if (card == "one_to_one" || card == "many_to_one") {
            for (key in counts) {
                if (index(key, "f" _sch_sep) == 1 && counts[key] > 1) {
                    _ret[++_ret[L]] = "relation " rel ": from " substr(key, 3) " violates cardinality " card
                    errs++
                }
            }
        }
        if (card == "one_to_one" || card == "one_to_many") {
            for (key in counts) {
                if (index(key, "t" _sch_sep) == 1 && counts[key] > 1) {
                    _ret[++_ret[L]] = "relation " rel ": to " substr(key, 3) " violates cardinality " card
                    errs++
                }
            }
        }
    }

    # Acyclic checks
    for (rel in _sch_rel_acyclic) {
        if (_sch_rel_acyclic[rel] != "1") continue
        # Build adjacency list for this relation
        delete node; delete nodelist; local_nid = 0
        for (i = 1; i <= _onto_lcnt; i++) {
            if (_onto_lfrom[i] == "" || _onto_lrel[i] != rel) continue
            from_id = _onto_lfrom[i]; to_id = _onto_lto[i]
            if (!((from_id) in node)) { nodelist[++local_nid] = from_id; node[from_id] = 1 }
            node[from_id, "#"]++
            node[from_id, node[from_id, "#"]] = to_id
        }
        # DFS cycle detection
        delete visited
        for (ni = 1; ni <= local_nid; ni++) {
            start = nodelist[ni]
            if ((start) in visited) continue
            delete stack
            stack[start] = 1; visited[start] = 1
            if (_sch_dfs_cycle(start, node, visited, stack)) {
                _ret[++_ret[L]] = "relation " rel ": cyclic dependency detected"
                errs++
                break
            }
        }
    }

    return errs
}

function _sch_dfs_cycle(cur, node, visited, stack,    j, nxt) {
    for (j = 1; j <= node[cur, "#"] + 0; j++) {
        nxt = node[cur, j]
        if ((nxt) in stack) return 1
        if ((nxt) in visited) continue
        visited[nxt] = 1; stack[nxt] = 1
        if (_sch_dfs_cycle(nxt, node, visited, stack)) return 1
        delete stack[nxt]
    }
    return 0
}