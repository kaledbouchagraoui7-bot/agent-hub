# snapshot.awk - Output current graph state as compact TSV
# Vars: (none)

BEGIN { FS="\t" }
{ onto_exec() }
END {
    onto_snapshot()
}
