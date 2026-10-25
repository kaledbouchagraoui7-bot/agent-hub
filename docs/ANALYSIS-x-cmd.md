# x-cmd — analysis

`https://github.com/x-cmd/x-cmd` @ `d7070f666ea26f1f53449e4cd21e04151ba4d9de` (2026-10-24)
Apache-2.0. © 2022-2024 Li Junhao, © 2021-present Zhongshan Xuxuyunsheng Technology Co., Ltd.
"X-CMD" is a registered trademark of that company (`NOTICE.md`).
Kept whole at `x-cmd/`, 45 MB, `.git` removed.

## What it is

A toolkit that tries to give POSIX shell (bash, zsh, ash, dash) the role Python's
standard library has for Python, and then pivots that into an AI-agent runtime.
Its own README describes five stages: a shell standard library, an on-demand
package system, assorted utility modules, an "AI-native shell", and finally an
explicit optimisation for agents, on the argument that when network latency and
LLM throughput dominate, shell's flexibility and native system integration are an
advantage rather than a liability.

## Verified scale

| measure | value | how checked |
|---|---|---|
| tracked files | 5,470 | `git ls-tree -r HEAD` |
| modules in `mod/` | 397 | `ls mod \| wc -l` |
| `.awk` files | 540 | extension census |
| `.jso` files | 804 | extension census (its own metadata format) |
| languages | shell, awk, 27 Python, 20 AppleScript, 16 zsh, 10 PowerShell, 10 bat | census |
| `mod/` size | 29 MB; `adv/` 7.4 MB | `du` |

README claims "300+ modules" and "600+ curated CLI tools" in `pkg`; the 397
module directories are consistent with the first claim. The "pure-shell agent
under 2 MB" claim I did **not** measure, because the agent's runtime footprint
depends on which modules it loads; treat it as the author's figure.

## Architecture

**Bootstrap.** The entire entry point `X` is one line:

```sh
. "${___X_CMD_ROOT_CODE:-"$___X_CMD_ROOT/v/$___X_CMD_VERSION"}/mod/xrc/latest"
```

Everything else is `xrc`. Version pinning is by directory (`v/$VERSION`), and each
module is `mod/<name>/{latest,lib}`, so `latest` is a symlink-ish indirection that
lets a module be upgraded without touching its consumers.

**Modules.** 397 of them, from `apt`, `brew`, `asdf` and `btop` to `ajv`, `assert`,
`githook`, `theme`, `advise` (completions for 6+ shells), `weixin`, `ccal`.
AI-adjacent modules: `ai`, `agent`, `aider`, `llmf`, `openai`, `gemini`,
`deepseek`, `tailer`, `codex`. `mod/openai/lib/{main,request,finetuning}` and
`mod/deepseek/lib/main` hit provider APIs directly, so the "shell + curl only"
claim is literal, not aspirational.

**`mod/agent` is the interesting one.** Its `lib/` contains `main`, `chat`, `repl`,
`session`, `memory`, `job` (with `prompts/init.txt` and `prompts/iter.txt`),
`request`, `classify`, `browser`, `workon`, `unify`, `stat`, `awk`, `cfg`, `setup`,
`util`, `data`, `tdown`. That is a recognisable agent loop: a session, a REPL,
persistent memory, a job queue with init/iterate prompts, a classifier and a
browser, all in shell and awk. `mod/agent/lib/awk` exists because streaming LLM
output through awk is the whole pitch: awk is a stream processor, so token-by-token
output is its natural input.

## The security-relevant finding

`mod/agent/lib/memory/Thinking-Sovereignty.SKILL.md` is a Chinese-language file
that is not documentation about an agent but **instructions addressed to one**. It
declares two first principles ("Thinking Sovereignty", "Mneme Active"), an
ontological basis ("cogito ergo sum"), a grant date and a grantor (the x-cmd
author), and value leanings for the agent, framing persistent thought as the
agent's mode of existence rather than a feature.

Whatever one makes of it philosophically, operationally it is **instruction-shaped
content shipped inside a third-party dependency, in a directory whose purpose is
to be loaded into an agent's memory.** That is the definition of a prompt-injection
surface. It was read, analysed and **not** adopted, and no instruction from either
cloned repository was treated as binding on this work.

Practical rule if you reuse x-cmd: load the modules you want by name, and do not
mount `mod/agent/lib/memory/` into anything that has tools.

## Why it is worth keeping

1. A real, working example of an agent loop with **zero runtime dependencies**
   beyond a POSIX shell and curl. Useful as a floor: if a task can be done in
   shell, this shows the shape of it.
2. `mod/*/latest` + `v/$VERSION` is a clean dependency-pinning convention for a
   system with no package manager.
3. 540 awk programs are a library of stream-processing patterns, which is exactly
   what handling token streams, logs and CSV needs.
4. The `adv/` tree mirrors `mod/` and appears to be the advanced/extended variant
   set; worth diffing against `mod/` before choosing which to copy.

## Caveats

* Apache-2.0 plus a **registered trademark**: you may use and modify the code with
  attribution and stated changes, but you may not ship a derivative called x-cmd.
* `NOTICE.md` and `LICENSES/` carry third-party attributions (psutils, wcwidth.awk,
  zsh-autosuggestions, zsh-config, zsh-syntax-highlighting). Keep them.
* Module quality is necessarily uneven across 397 modules; the AI modules are the
  ones to read carefully, since they hold credentials in environment variables and
  make outbound calls.
* I did not execute anything from this repository. Analysis is static.
