# related.awk - Get related entities with full info (like ontology.py get_related)
# Vars: ONTO_ID, ONTO_REL, ONTO_DIR, ONTO_FMT

BEGIN { FS="\t" }
{ onto_exec() }
END {
    onto_related(ONTO_ID, ONTO_REL, ONTO_DIR, _r)
    if (ONTO_FMT == "json") {
        printf "["
        for (i = 1; i <= _r[L]; i++) {
            if (i > 1) printf ","
            n = split(_r[i], _p, SUBSEP)
            rel = _p[1]
            eid = _p[2]
            etype = _p[3]
            pcnt = _p[4]
            printf "{\"relation\":\"%s\",\"entity\":{\"id\":\"%s\",\"type\":\"%s\",\"props\":{", _onto_json_esc_cached(rel), _onto_json_esc_cached(eid), _onto_json_esc_cached(etype)
            first_prop = 1
            for (k = 5; k <= n; k += 2) {
                pk = _p[k]
                pv = _p[k + 1]
                if (k + 1 > n) continue
                if (!first_prop) printf ","
                printf "\"%s\":\"%s\"", _onto_json_esc_cached(pk), _onto_json_esc_cached(pv)
                first_prop = 0
            }
            printf "}}}"
        }
        printf "]\n"
    } else {
        for (i = 1; i <= _r[L]; i++) {
            n = split(_r[i], _p, SUBSEP)
            rel = _p[1]
            eid = _p[2]
            etype = _p[3]
            pcnt = _p[4]
            printf "%s\t%s\t%s", rel, eid, etype
            for (k = 5; k <= n; k += 2) {
                pk = _p[k]
                pv = _p[k + 1]
                if (k + 1 > n) continue
                printf "\t%s=%s", pk, pv
            }
            printf "\n"
        }
    }
}
