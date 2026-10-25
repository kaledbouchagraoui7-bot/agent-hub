# query.awk - Query entities by type and property filters
# Vars: ONTO_TYPE, ONTO_FMT, ONTO_FILTERS, ONTO_TSV_COLS

BEGIN { FS="\t" }
{ onto_exec() }
END {
    onto_query(_r)
    if (ONTO_FMT == "tsv") {
        _print_tsv()
    } else if (ONTO_FMT == "json") {
        _print_json()
    } else {
        _print_default()
    }
}

function _print_default(    i, id) {
    for (i = 1; i <= _r[L]; i++) {
        id = _r[i]
        printf "%s\t%s\t%s\n", id, _onto_type[id], _onto_prop[id, "name"]
    }
}

function _print_json(    first, i, id) {
    printf "["
    for (i = 1; i <= _r[L]; i++) {
        if (i > 1) printf ","
        id = _r[i]
        printf "{\"id\":\"%s\",\"type\":\"%s\",\"name\":\"%s\"}", _onto_json_esc_cached(id), _onto_json_esc_cached(_onto_type[id]), _onto_json_esc_cached(_onto_prop[id, "name"])
    }
    printf "]\n"
}

# TSV schema mode: fixed columns from schema + misc at end
# Columns: col1 col2 ... colN misc
# For each entity: fixed cols in order, then misc as "key=value\tkey=value"
function _print_tsv(    i, id, j, n, k, col, val, misc, first) {
    if (ONTO_TSV_COLS == "") {
        # No schema cols, fallback to default 3-col format
        _print_default()
        return
    }
    # Split column list
    n = split(ONTO_TSV_COLS, _tsv_cols_arr, " ")
    for (i = 1; i <= _r[L]; i++) {
        id = _r[i]
        misc = ""
        for (j = 1; j <= n; j++) {
            col = _tsv_cols_arr[j]
            val = _onto_prop[id, col]
            if (j > 1) printf "\t"
            printf "%s", val
        }
        # Collect all non-schema props into misc
        for (k = 1; k <= _onto_pcnt[id]; k++) {
            kk = _onto_pkeys[id, k]
            if (!__sch_is_col(_onto_type[id], kk)) {
                if (misc != "") misc = misc "\t"
                misc = misc kk "=" _onto_prop[id, kk]
            }
        }
        printf "\t%s\n", misc
    }
}

# Check if a prop is in the schema columns (used in ONTO_TSV_COLS context)
function __sch_is_col(type, prop,    cols, n, i, arr) {
    if (ONTO_TSV_COLS == "") return 0
    cols = ONTO_TSV_COLS
    n = split(cols, arr, " ")
    for (i = 1; i <= n; i++)
        if (arr[i] == prop) return 1
    return 0
}

function onto_query(_ret,    i, id, j, ismatch, wk, wv) {
    _ret[L] = 0
    for (i = 1; i <= _onto_cnt; i++) {
        id = _onto_order[i]
        if (!_onto_alive[id]) continue
        if (ONTO_TYPE != "" && _onto_type[id] != ONTO_TYPE) continue
        ismatch = 1
        for (j = 1; j <= _qwcnt; j++) {
            wk = _qwkeys[j]
            wv = _qwvals[j]
            if (_onto_unescape(_onto_prop[id, wk]) != wv) { ismatch = 0; break }
        }
        if (ismatch) _ret[++_ret[L]] = id
    }
}

# Parse filter pairs from ONTO_FILTERS (tab-separated key=val)
BEGIN {
    _qwcnt = 0
    if (ONTO_FILTERS != "") {
        _fn = split(ONTO_FILTERS, _fp, "\t")
        for (i = 1; i <= _fn; i++) {
            _eq = index(_fp[i], "=")
            if (_eq > 0) {
                _qwcnt++
                _qwkeys[_qwcnt] = substr(_fp[i], 1, _eq - 1)
                _qwvals[_qwcnt] = substr(_fp[i], _eq + 1)
            }
        }
    }
}