
# md lint rule — orphan-fence
#
# Detects unbalanced ``` fenced code blocks: an open fence with no matching
# close (the classic cause of Vite/Vue build failures).
#
# Layering — a reusable core plus a policy dispatcher:
#   md_lint_fence_line   per-line handler (the shared while body)
#   md_lint_fence_file   entry: read one file by path,    return 1 if orphan
#   md_lint_fence_stdin  entry: read markdown from stdin, return 1 if orphan
#   file/stdin differ ONLY in the getline source and share the same while body.
# The entry functions are pure — they read input and return a status; the
# dispatchers (BEGIN for stdin mode, the main rule for a file list) call an
# entry and do the logging / exit code, so the entries stay reusable.
#
# File mode streams a list of filenames on stdin (one per line); each is opened
# in isolation, which scales to many files with no ARG_MAX limit.
#
# Strict model:
#   - a fence line carrying a language tag (```lang) is ALWAYS an open;
#   - a bare ``` is a close when a block is open, or an open when none is;
#   - at end of input any fence left on the stack is an orphan (unclosed).
#
# Both backtick (```) and tilde (~~~) fences are tracked, type-aware: a line
# that looks like a fence but sits inside a block of the OTHER type is treated
# as literal content. Only column-0 fences are considered; indented are ignored.

function log_err( _msg ){
    printf( "MD-LINT|E: %s\n", _msg ) >"/dev/stderr"
}

# push an open fence of type `sym` ("`" or "~") opened at `lineno`
function md_lint_fence_push( _sym, _lineno ){
    MD_FENCE_STACK[ ++MD_FENCE_STACK_LEN ] = _lineno
    MD_FENCE_TYPE[ MD_FENCE_STACK_LEN ] = _sym
}

# ---- per-line handler: the shared body of both entry points' while loop ----
function md_lint_fence_line( _lineno,    _sym, _rest ){
    if ($0 ~ /^```/)      _sym = "`"
    else if ($0 ~ /^~~~/) _sym = "~"
    else return                                 # not a fence — ignore
    # a fence line inside a block of the other type is literal content
    if (MD_FENCE_STACK_LEN > 0 && MD_FENCE_TYPE[MD_FENCE_STACK_LEN] != _sym) return
    _rest = $0
    sub( /^(`+|~+)/, "", _rest )                # strip the leading fence run (>= 3)
    if (_rest ~ /^[ \t]*$/) {                   # bare fence -> close (or open if none open)
        if (MD_FENCE_STACK_LEN == 0) md_lint_fence_push( _sym, _lineno )
        else                        MD_FENCE_STACK_LEN--
    } else {                                    # tagged fence (```lang / ~~~lang) -> open
        md_lint_fence_push( _sym, _lineno )
    }
}

# status helper: true iff every open fence has been closed
function md_lint_fence_ok(){
    return ( MD_FENCE_STACK_LEN == 0 )
}

# error message listing still-open fence line numbers
function md_lint_fence_report(    _s, _i ){
    _s = ""
    for (_i=1; _i<=MD_FENCE_STACK_LEN; ++_i) {
        _s = _s " " MD_FENCE_STACK[_i]
    }
    return ( "unclosed ``` opened at line(s):" _s )
}

# ---- pure entry points: read input, return 1 if orphan else 0 (no logging) ----

function md_lint_fence_file( _fname,    _lineno ){
    MD_FENCE_STACK_LEN = 0
    _lineno = 0
    while ((getline < _fname) > 0) md_lint_fence_line( ++_lineno )
    close( _fname )
    return md_lint_fence_ok() ? 0 : 1
}

function md_lint_fence_stdin(    _lineno ){
    MD_FENCE_STACK_LEN = 0
    _lineno = 0
    while ((getline) > 0) md_lint_fence_line( ++_lineno )
    return md_lint_fence_ok() ? 0 : 1
}

BEGIN{
    MD_FENCE_STACK_LEN = 0
    EXIT_CODE = 0
    # stdin mode: the markdown document itself is on stdin (`x md lint checkfence -`)
    if (MODE == "stdin") {
        if (md_lint_fence_stdin()) {
            log_err( "[<stdin>] " md_lint_fence_report() )
            EXIT_CODE = 1
        }
        exit( EXIT_CODE )
    }
}

# file mode (default): each stdin line is a filename — check it
{
    CUR_FNAME = $0
    if (md_lint_fence_file( CUR_FNAME )) {
        log_err( "[" CUR_FNAME "] " md_lint_fence_report() )
        EXIT_CODE = 1
    }
}

END{
    exit( EXIT_CODE )
}
