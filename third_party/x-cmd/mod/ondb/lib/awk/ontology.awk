# ondb.awk - Knowledge graph engine for AWK
#
# Graph-log format (tab-separated):
#   add  <type> <id> <epoch_ms> [<key1> <val1> <key2> <val2>...]
#   set  <id> <epoch_ms> [<key> <val>...]
#   rm   <id> <epoch_ms>
#   link <from> <rel> <to> <epoch_ms>
#   unlink <from> <rel> <to> <epoch_ms>
#   # comment, empty lines ignored
#
# Property values: tab encoded as \t, newline as \n, backslash as \\
#
# Streaming mode: data arrives via main rule, call onto_exec() per line,
#   then call query functions in END block.

BEGIN {
    L = "\001"
}

function _onto_unescape(s) {
    if (index(s, "\\") == 0) return s
    gsub(/\\t/, "\t", s)
    gsub(/\\n/, "\n", s)
    gsub(/\\\\/, "\\", s)
    return s
}

function _onto_escape(s) {
    if (index(s, "\\") == 0 && index(s, "\t") == 0 && index(s, "\n") == 0) return s
    gsub(/\\/, "\\\\", s)
    gsub(/\t/, "\\t", s)
    gsub(/\n/, "\\n", s)
    return s
}

function _onto_json_esc(s) {
    if (index(s, "\\") == 0 && index(s, "\"") == 0 && index(s, "\n") == 0 && index(s, "\t") == 0 && index(s, "\r") == 0) return s
    gsub(/\\/, "\\\\", s)
    gsub(/"/, "\\\"", s)
    gsub(/\n/, "\\n", s)
    gsub(/\t/, "\\t", s)
    gsub(/\r/, "\\r", s)
    return s
}

# Cached version for bulk JSON output (e.g. ls/query/linked)
# type/name values repeat heavily across entities
function _onto_json_esc_cached(s,    r) {
    if (s in _onto_json_esc_cache) return _onto_json_esc_cache[s]
    r = s
    if (index(r, "\\") || index(r, "\"") || index(r, "\n") || index(r, "\t") || index(r, "\r")) {
        gsub(/\\/, "\\\\", r)
        gsub(/"/, "\\\"", r)
        gsub(/\n/, "\\n", r)
        gsub(/\t/, "\\t", r)
        gsub(/\r/, "\\r", r)
    }
    _onto_json_esc_cache[s] = r
    return r
}

# Execute single directive. Fields shifted for epoch_ms column:
#   add  $2=type $3=id $4=epoch_ms $5..=props
#   set  $2=id   $3=epoch_ms $4..=key/val pairs
#   rm   $2=id   $3=epoch_ms
#   link $2=from $3=rel $4=to $5=epoch_ms
function onto_exec(    id, i, n, k, v, pcnt) {
    if ($1 == "add") {
        id = $3
        if ((id) in _onto_type) return
        _onto_type[id] = $2
        _onto_alive[id] = 1
        pcnt = 0
        _onto_ctime[id] = $4
        _onto_mtime[id] = $4
        _onto_order[++_onto_cnt] = id
        for (i = 5; i <= NF; i += 2) {
            k = $i
            _onto_prop[id, k] = $(i + 1)
            _onto_pkeys[id, ++pcnt] = k
        }
        _onto_pcnt[id] = pcnt
    } else if ($1 == "set") {
        id = $2
        if (!(id in _onto_alive)) return
        _onto_mtime[id] = $3
        pcnt = _onto_pcnt[id]
        for (i = 4; i <= NF; i += 2) {
            k = $i
            v = $(i + 1)
            if (v == "") {
                delete _onto_prop[id, k]
            } else {
                if (!((id, k) in _onto_prop)) {
                    _onto_pkeys[id, ++pcnt] = k
                }
                _onto_prop[id, k] = v
            }
        }
        _onto_pcnt[id] = pcnt
    } else if ($1 == "rm") {
        _onto_alive[$2] = 0
    } else if ($1 == "link") {
        # O(1) duplicate check via associative array
        if (($2, $3, $4) in _onto_link_seen) return
        _onto_link_seen[$2, $3, $4] = 1
        ++_onto_lcnt
        _onto_lfrom[_onto_lcnt] = $2
        _onto_lrel[_onto_lcnt]  = $3
        _onto_lto[_onto_lcnt]   = $4
        _onto_lepoch[_onto_lcnt] = $5
        _onto_lpcnt[_onto_lcnt] = 0
        for (i = 6; i <= NF; i += 2) {
            k = $i
            _onto_lprop[_onto_lcnt, k] = $(i + 1)
            _onto_lpkeys[_onto_lcnt, ++_onto_lpcnt[_onto_lcnt]] = k
        }
    } else if ($1 == "unlink") {
        delete _onto_link_seen[$2, $3, $4]
        for (i = 1; i <= _onto_lcnt; i++) {
            if (_onto_lfrom[i] == $2 && _onto_lrel[i] == $3 && _onto_lto[i] == $4) {
                _onto_lfrom[i] = ""; _onto_lrel[i] = ""; _onto_lto[i] = ""
            }
        }
    }
}

function _onto_reset() {
    _onto_cnt = 0; _onto_lcnt = 0
    delete _onto_type; delete _onto_alive
    delete _onto_prop; delete _onto_pkeys; delete _onto_pcnt
    delete _onto_ctime; delete _onto_mtime
    delete _onto_order
    delete _onto_lfrom; delete _onto_lrel; delete _onto_lto
    delete _onto_lprop; delete _onto_lpkeys; delete _onto_lpcnt
    delete _onto_link_seen
}

function onto_get(id, _ret,    i, k) {
    if (!(id in _onto_alive) || !_onto_alive[id]) {
        _ret[L] = 0
        return 0
    }
    _ret[L] = 6
    _ret["id"]     = id
    _ret["type"]   = _onto_type[id]
    _ret["name"]   = _onto_prop[id, "name"]
    _ret["ctime"]  = _onto_ctime[id]
    _ret["mtime"]  = _onto_mtime[id]
    _ret["props"]  = ""
    for (i = 1; i <= _onto_pcnt[id]; i++) {
        k = _onto_pkeys[id, i]
        if (!((id, k) in _onto_prop)) continue
        if (_ret["props"] != "") _ret["props"] = _ret["props"] "\001"
        _ret["props"] = _ret["props"] k "=" _onto_prop[id, k]
    }
    return 1
}

function onto_ls(type, _ret,    i, id) {
    _ret[L] = 0
    for (i = 1; i <= _onto_cnt; i++) {
        id = _onto_order[i]
        if (!_onto_alive[id]) continue
        if (type != "" && _onto_type[id] != type) continue
        _ret[++_ret[L]] = id
    }
}

function onto_linked(id, rel, dir, _ret,    i) {
    _ret[L] = 0
    for (i = 1; i <= _onto_lcnt; i++) {
        if (_onto_lfrom[i] == "") continue
        if (rel != "" && _onto_lrel[i] != rel) continue

        if (dir == "outgoing" || dir == "") {
            if (_onto_lfrom[i] == id && _onto_alive[_onto_lto[i]]) {
                _ret[++_ret[L]] = _onto_lrel[i] SUBSEP _onto_lto[i] SUBSEP i
            }
        } else if (dir == "incoming") {
            if (_onto_lto[i] == id && _onto_alive[_onto_lfrom[i]]) {
                _ret[++_ret[L]] = _onto_lrel[i] SUBSEP _onto_lfrom[i] SUBSEP i
            }
        } else if (dir == "both") {
            if (_onto_lfrom[i] == id && _onto_alive[_onto_lto[i]]) {
                _ret[++_ret[L]] = "out" SUBSEP _onto_lrel[i] SUBSEP _onto_lto[i] SUBSEP i
            } else if (_onto_lto[i] == id && _onto_alive[_onto_lfrom[i]]) {
                _ret[++_ret[L]] = "in" SUBSEP _onto_lrel[i] SUBSEP _onto_lfrom[i] SUBSEP i
            }
        }
    }
}

function onto_related(id, rel, dir, _ret,    i, target, t, k, pcnt) {
    _ret[L] = 0
    for (i = 1; i <= _onto_lcnt; i++) {
        if (_onto_lfrom[i] == "") continue
        if (rel != "" && _onto_lrel[i] != rel) continue
        target = ""
        if (dir == "outgoing" || dir == "") {
            if (_onto_lfrom[i] == id && _onto_alive[_onto_lto[i]]) {
                target = _onto_lto[i]
            }
        } else if (dir == "incoming") {
            if (_onto_lto[i] == id && _onto_alive[_onto_lfrom[i]]) {
                target = _onto_lfrom[i]
            }
        } else if (dir == "both") {
            if (_onto_lfrom[i] == id && _onto_alive[_onto_lto[i]]) {
                target = _onto_lto[i]
            } else if (_onto_lto[i] == id && _onto_alive[_onto_lfrom[i]]) {
                target = _onto_lfrom[i]
            }
        }
        if (target == "") continue
        t = _onto_type[target]
        _ret[++_ret[L]] = _onto_lrel[i] SUBSEP target SUBSEP t SUBSEP _onto_pcnt[target]
        for (k = 1; k <= _onto_pcnt[target]; k++) {
            pk = _onto_pkeys[target, k]
            if ((target, pk) in _onto_prop) {
                _ret[_ret[L]] = _ret[_ret[L]] SUBSEP pk SUBSEP _onto_prop[target, pk]
            }
        }
    }
}

function onto_validate(_ret,    i, id, errs) {
    _ret[L] = 0
    errs = 0
    for (i = 1; i <= _onto_lcnt; i++) {
        if (_onto_lfrom[i] == "") continue
        id = _onto_lfrom[i]
        if (!(id in _onto_alive) || !_onto_alive[id]) {
            _ret[++_ret[L]] = "dangling_from: link from=" id " rel=" _onto_lrel[i] " to=" _onto_lto[i]
            errs++
        }
        id = _onto_lto[i]
        if (!(id in _onto_alive) || !_onto_alive[id]) {
            _ret[++_ret[L]] = "dangling_to: link from=" _onto_lfrom[i] " rel=" _onto_lrel[i] " to=" id
            errs++
        }
    }
    return errs
}

# Snapshot: output current state as TSV directives (add with ctime, set to restore mtime)
function onto_snapshot(    i, id, k, pk) {
    for (i = 1; i <= _onto_cnt; i++) {
        id = _onto_order[i]
        if (!_onto_alive[id]) continue
        printf "add\t%s\t%s\t%s", _onto_type[id], id, _onto_ctime[id]
        for (k = 1; k <= _onto_pcnt[id]; k++) {
            pk = _onto_pkeys[id, k]
            if (!((id, pk) in _onto_prop)) continue
            printf "\t%s\t%s", pk, _onto_prop[id, pk]
        }
        printf "\n"
        if (_onto_mtime[id] != _onto_ctime[id]) {
            printf "set\t%s\t%s\n", id, _onto_mtime[id]
        }
    }
    for (i = 1; i <= _onto_lcnt; i++) {
        if (_onto_lfrom[i] == "") continue
        printf "link\t%s\t%s\t%s\t%s", _onto_lfrom[i], _onto_lrel[i], _onto_lto[i], _onto_lepoch[i]+0
        for (k = 1; k <= _onto_lpcnt[i]; k++) {
            key = _onto_lpkeys[i, k]
            printf "\t%s\t%s", key, _onto_lprop[i, key]
        }
        printf "\n"
    }
}
