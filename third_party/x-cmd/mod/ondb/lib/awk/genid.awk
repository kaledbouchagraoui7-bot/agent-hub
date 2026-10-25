# genid.awk - Generate next sequential ID for a type prefix
# Vars: ONTO_PREFIX
# Output: next available NNN (e.g. 003)

BEGIN { FS="\t" }
$1 == "add" && $3 ~ "^" ONTO_PREFIX "_[0-9]+$" {
    n = substr($3, length(ONTO_PREFIX "_") + 1) + 0
    if (n > m) m = n
}
END { printf "%03d", m + 1 }
