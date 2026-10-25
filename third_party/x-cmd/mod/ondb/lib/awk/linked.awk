# linked.awk - Get related entities
# Vars: ONTO_ID, ONTO_REL, ONTO_DIR, ONTO_FMT

BEGIN { FS="\t" }
{ onto_exec() }
END {
    onto_linked(ONTO_ID, ONTO_REL, ONTO_DIR, _r)
    if (ONTO_FMT == "json") {
        printf "["
        for (i = 1; i <= _r[L]; i++) {
            if (i > 1) printf ","
            split(_r[i], _p, SUBSEP)
            li = _p[ONTO_DIR == "both" ? 4 : 3]
            if (ONTO_DIR == "both") {
                printf "{\"dir\":\"%s\",\"rel\":\"%s\",\"id\":\"%s\",\"type\":\"%s\"", _onto_json_esc_cached(_p[1]), _onto_json_esc_cached(_p[2]), _onto_json_esc_cached(_p[3]), _onto_json_esc_cached(_onto_type[_p[3]])
            } else {
                printf "{\"rel\":\"%s\",\"id\":\"%s\",\"type\":\"%s\"", _onto_json_esc_cached(_p[1]), _onto_json_esc_cached(_p[2]), _onto_json_esc_cached(_onto_type[_p[2]])
            }
            if (_onto_lpcnt[li] > 0) {
                printf ",\"link_props\":{"
                for (k = 1; k <= _onto_lpcnt[li]; k++) {
                    key = _onto_lpkeys[li, k]
                    if (k > 1) printf ","
                    printf "\"%s\":\"%s\"", _onto_json_esc_cached(key), _onto_json_esc_cached(_onto_lprop[li, key])
                }
                printf "}"
            }
            printf "}"
        }
        printf "]\n"
    } else {
        for (i = 1; i <= _r[L]; i++) {
            split(_r[i], _p, SUBSEP)
            li = _p[ONTO_DIR == "both" ? 4 : 3]
            if (ONTO_DIR == "both") {
                printf "%s\t%s\t%s\t%s", _p[1], _p[2], _p[3], _onto_type[_p[3]]
            } else {
                printf "%s\t%s\t%s", _p[1], _p[2], _onto_type[_p[2]]
            }
            for (k = 1; k <= _onto_lpcnt[li]; k++) {
                key = _onto_lpkeys[li, k]
                printf "\t%s=%s", key, _onto_lprop[li, key]
            }
            printf "\n"
        }
    }
}
