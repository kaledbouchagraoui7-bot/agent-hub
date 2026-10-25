# get.awk - Get entity by ID
# Vars: ONTO_ID, ONTO_FMT

BEGIN { FS="\t" }
{ onto_exec() }
END {
    if (!onto_get(ONTO_ID, _e)) {
        print "Entity not found: " ONTO_ID > "/dev/stderr"
        exit 1
    }
    if (ONTO_FMT == "json") {
        printf "{\"id\":\"%s\",\"type\":\"%s\",\"ctime\":\"%s\",\"mtime\":\"%s\",\"properties\":{", _onto_json_esc_cached(_e["id"]), _onto_json_esc_cached(_e["type"]), _onto_json_esc_cached(_e["ctime"]), _onto_json_esc_cached(_e["mtime"])
        n = split(_e["props"], _pp, "\001")
        for (i = 1; i <= n; i++) {
            eq = index(_pp[i], "=")
            k = substr(_pp[i], 1, eq - 1)
            v = substr(_pp[i], eq + 1)
            if (i > 1) printf ","
            printf "\"%s\":\"%s\"", _onto_json_esc_cached(k), _onto_json_esc_cached(v)
        }
        printf "}}\n"
    } else {
        printf "id\t%s\n", _e["id"]
        printf "type\t%s\n", _e["type"]
        printf "ctime\t%s\n", _e["ctime"]
        printf "mtime\t%s\n", _e["mtime"]
        n = split(_e["props"], _pp, "\001")
        for (i = 1; i <= n; i++) {
            printf "prop\t%s\n", _pp[i]
        }
    }
}
