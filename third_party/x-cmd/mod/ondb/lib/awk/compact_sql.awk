# compact_sql.awk - Output current state as SQLite INSERT statements
# Piped into: sqlite3 ondb.db
# Vars: (none)

BEGIN { FS="\t" }
{ onto_exec() }
END {
    # Entities
    for (i = 1; i <= _onto_cnt; i++) {
        id = _onto_order[i]
        if (!_onto_alive[id]) continue
        eid = id; gsub(/'/, "''", eid)
        etype = _onto_type[id]; gsub(/'/, "''", etype)
        printf "INSERT OR REPLACE INTO entities (id,type,ctime,mtime) VALUES ('%s','%s',%s,%s);\n", eid, etype, _onto_ctime[id]+0, _onto_mtime[id]+0
    }
    # Props
    for (i = 1; i <= _onto_cnt; i++) {
        id = _onto_order[i]
        if (!_onto_alive[id]) continue
        eid = id; gsub(/'/, "''", eid)
        for (k = 1; k <= _onto_pcnt[id]; k++) {
            key = _onto_pkeys[id, k]
            if (!((id, key) in _onto_prop)) continue
            val = _onto_prop[id, key]
            printf "INSERT OR REPLACE INTO props (entity_id,key,value) VALUES ('%s','%s','%s');\n", eid, key, val
        }
    }
    # Links + link_props
    for (i = 1; i <= _onto_lcnt; i++) {
        if (_onto_lfrom[i] == "") continue
        fid = _onto_lfrom[i]; gsub(/'/, "''", fid)
        fr = _onto_lrel[i]; gsub(/'/, "''", fr)
        ti = _onto_lto[i]; gsub(/'/, "''", ti)
        printf "INSERT OR REPLACE INTO links (from_id,rel,to_id,epoch) VALUES ('%s','%s','%s',%s);\n", fid, fr, ti, _onto_lepoch[i]+0
        for (k = 1; k <= _onto_lpcnt[i]; k++) {
            key = _onto_lpkeys[i, k]
            val = _onto_lprop[i, key]
            gsub(/'/, "''", key); gsub(/'/, "''", val)
            printf "INSERT OR REPLACE INTO link_props (from_id,rel,to_id,key,value) VALUES ('%s','%s','%s','%s','%s');\n", fid, fr, ti, key, val
        }
    }
    printf "UPDATE meta SET value='%d' WHERE key='last_lines';\n", NR
}
