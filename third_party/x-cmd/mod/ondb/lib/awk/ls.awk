# ls.awk - List entities
# Vars: ONTO_TYPE, ONTO_FMT

BEGIN { FS="\t" }
{ onto_exec() }
END {
    onto_ls(ONTO_TYPE, _r)
    if (ONTO_FMT == "json") {
        printf "["
        for (i = 1; i <= _r[L]; i++) {
            id = _r[i]
            if (i > 1) printf ","
            printf "{\"id\":\"%s\",\"type\":\"%s\",\"name\":\"%s\"}", _onto_json_esc_cached(id), _onto_json_esc_cached(_onto_type[id]), _onto_json_esc_cached(_onto_prop[id, "name"])
        }
        printf "]\n"
    } else {
        for (i = 1; i <= _r[L]; i++) {
            id = _r[i]
            printf "%s\t%s\t%s\n", id, _onto_type[id], _onto_prop[id, "name"]
        }
    }
}
