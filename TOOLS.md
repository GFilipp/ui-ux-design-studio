# Tools this engine needs on the machine

`engine/preflight.sh` is the executable version of this page. It checks every tool below, installs
what is missing with `--install` (Homebrew for binaries, npm for the Playwright module and browser),
and exits non-zero while a REQUIRED tool is absent. The design-pod runs it at Stage 0 and halts on
`FAIL`. The self-test suite asserts that the table below names exactly the script's registry, so the
two cannot drift apart silently.

```bash
bash engine/preflight.sh                      # check only
bash engine/preflight.sh --install            # install what is missing, then re-check
bash engine/preflight.sh --install --target . # also the package manager the target repo's lockfile implies
bash engine/preflight.sh --list               # print the registry
```
Exit codes: `0` every REQUIRED tool present (`WARN` lines allowed), `1` a REQUIRED tool is missing,
`2` usage error.

## Registry

| tool | tier | needed for | install (macOS) | how it is checked |
|---|---|---|---|---|
| `python3` | required | `run_state.py`, `floor_check.py`, `drawing_check.py` (stdlib only, no pip packages) | `brew install python3` | on PATH and the stdlib modules import |
| `node` | required | `render.mjs`, `extract.js`, `capture-*.mjs` | nvm (`nvm install --lts`) or `brew install node` | on PATH and its major version satisfies `engines.node` of the installed Playwright (read from `node_modules`, never typed here) |
| `npm` | required | installs the Playwright module declared in `package.json` | ships with node | on PATH |
| `npx` | required | `npx playwright install chromium` downloads the render browser | ships with node | on PATH |
| `git` | required | `run_state.py init` records `base_sha`; `drawing_check.py --git-diff` scopes the scan to it | `brew install git` | on PATH |
| `playwright` | required | the node module `render.mjs` imports | `npm ci` at the engine root | `require("playwright")` resolves from the engine root |
| `browser` | required | `render.mjs` launches Playwright's bundled Chromium, else system Chrome (`channel: "chrome"`) | `npx playwright install chromium` | a headless launch succeeds the same way `render.mjs` tries it |
| `timeout` | recommended | the pod wraps long renders in GNU `timeout`; macOS ships none, and on 2026-09-08 four reference renders were reported as failures for that reason alone | `brew install coreutils` (Homebrew links it unprefixed because no macOS command conflicts) | on PATH; a lone `gtimeout` is reported and linked by `--install` |
| `stop-hook` | recommended | enforcement: `~/.claude/settings.json` sets `env.DESIGN_STUDIO_HOME` and runs `hooks/design-gate.sh` as a Stop hook | follow `hooks/README.md` (a settings edit, not a package) | both entries present in `settings.json`; `WARN` only, never edited by the script |

Tiers: **required** means the engine cannot run without it and preflight exits `1`; **recommended**
means runs hit noise without it, preflight prints `WARN`, and `--install` installs it anyway.

## Target repo package manager (`--target <dir>`)

The engine builds inside the asset's real repo, so the pod also needs whatever installs that repo's
dependencies. The rule, derived from the lockfile, with a `packageManager` field in `package.json`
taking precedence:

| in the target repo | requires |
|---|---|
| `bun.lock` or `bun.lockb` | `bun` (`brew install oven-sh/bun/bun`) |
| `pnpm-lock.yaml` | `pnpm` (`brew install pnpm`) |
| `yarn.lock` | `yarn` (`brew install yarn`) |
| `package-lock.json` or `npm-shrinkwrap.json` | `npm` |
| several lockfiles, `npm` among them | `npm` is used; the others are `WARN` when missing |

## Deliberately not on the list

- **Component-library and image MCPs** (shadcn, magicui, heroui, 21st, flowbite, mcp-image). These
  are Claude Code connectors, enumerated live by `agents/component-scout.md`; their keys live in the
  user's `~/.claude.json`, never in this repo. Preflight cannot see them and does not pretend to.
- **`pnpm`, `bun`, `yarn` globally.** Only required when a target repo's lockfile says so.
- **ImageMagick, ffmpeg, a global `astro` or `vercel` CLI.** Nothing in the engine calls them;
  deploy is `git push`, Astro runs as a local dependency, screenshots come from Playwright.

## Maintenance

Adding a tool means two edits, or the suite goes red: the `REGISTRY` block in `engine/preflight.sh`
(name, tier, Homebrew formula, why) plus a check or installer case when it is not a plain binary, and
a row in the Registry table above. Never type a version floor into either file; read it from the
dependency that imposes it, the way the `node` check reads Playwright's `engines.node`.
