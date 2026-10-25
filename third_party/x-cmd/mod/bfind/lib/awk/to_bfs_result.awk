# BFS depth sort — reads paths from stdin, outputs in depth order
# Variables:
#   color - if non-empty, colorize per-segment, filename bold cyan
#   base  - optional root path for depth calculation

BEGIN { if (base != "") base_nf = split(base, _b, "/") }

{
    d = (base_nf > 0) ? split($0, _a, "/") - base_nf : split($0, _a, "/") - 1
    buf[d] = buf[d] $0 ORS
    if (d > maxd) maxd = d
}

END {
    if (!color) {
        for (d = 1; d <= maxd; d++) printf "%s", buf[d]
        exit
    }

    esc = sprintf("%c", 27)
    dc[1] = esc "[32m"; dc[2] = esc "[33m"; dc[3] = esc "[34m"
    nc = 3; fn = esc "[1;36m"; dim = esc "[2m"; reset = esc "[0m"

    start = (base_nf > 0) ? base_nf + 1 : 1
    for (d = 1; d <= maxd; d++) {
        nl = split(buf[d], _L, "\n")
        for (i = 1; i <= nl; i++) {
            if (_L[i] == "") continue
            np = split(_L[i], _P, "/")
            for (j = 1; j < start && j < np; j++) printf "%s/", _P[j]
            for (j = start; j < np; j++) printf "%s%s%s%s/%s", dc[(j - start) % nc + 1], _P[j], reset, dim, reset
            printf "%s%s%s\n", fn, _P[np], reset
        }
    }
}
