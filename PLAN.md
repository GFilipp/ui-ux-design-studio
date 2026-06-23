# Plan: RocketMinds AI Design Capability

## Context

**Why this exists.** Claude's web/graphic/marketing output is text-heavy and weak on craft. A live page took ~10 correction rounds and still shipped low-contrast text, an empty hero, and no imagery. The initial hypothesis was "better skill discipline + component repos + exemplars."

**Objective (resolved after pressure-test).** Build a durable, reusable, **brand-agnostic** UI/UX design-studio capability that reliably produces strong visual output across surfaces (web, app UI, marketing assets), with Gary reviewing at decision gates rather than acting as the manual fixer. The engine is design-system / brand-kit agnostic; a brand kit is a swappable per-project input. It serves any brand profile (RocketMinds, garyflip, tegy, actor sites, and client / third-party brands alike), not one hardcoded brand. This is capability-building for ongoing multi-surface, multi-brand production, not a one-off page. That objective is what justifies building rather than buying. Buying (a contractor or a premium template) stays the right move for any single asset that must be perfect on a hard deadline; the system handles the ongoing 90%.

**Pressure-test verdict (strategist + devil's advocate).**
- Diagnosis corrected. The root cause is not missing inventory. It is three holes: (1) enforcement gap (zero hooks on disk; design skills fire ~4x lifetime vs strategy skills 1,700+; Gary is the runtime gate); (2) no asset generation (you cannot enforce imagery into existence; true greenfield); (3) no closed vision-critique loop (the parts exist but are unchained). Taste-not-encoded is secondary; inventory is a red herring.
- The original 8-capability "studio" was over-built and not MECE. Two of its most expensive ideas were harmful: a model "design-judge" scoring world-class taste regresses output to a generic mean, and hooks that force skill invocation cannot force quality (green check on an ugly page). Evidence: the documented, MANDATORY orphan-words rule is still violated repeatedly; more machinery does not make taste stick.

**Resolution.** Build the ambitious capability, reshaped so the machine owns the objective FLOOR and the human owns the taste CEILING. Start with a lean core that doubles as empirical validation, then expand only on proof.

## Locked decisions (this session)
- **Taste seat — you pick from divergent candidates.** The machine clears the objective floor and proposes; you make the final aesthetic call. It never ships on "world-class" taste autonomously. Lightweight in Phase 1 (2-3 directions for the key section); full L5 automation in Phase 2.
- **v1 scope — spine first, then expand** (Phase 1 lean core below).
- **Asset default — clean type first.** Imagery is generated only when a slot needs it AND it beats the type-only version AND passes brand coherence. Clean type + space is the preferred default, never slop-filled.
- **Brand-agnostic engine.** The system is design-system / brand-kit agnostic. A brand kit (tokens + type + palette + logo + DNA rubric + voice) is a swappable per-project input/profile; RocketMinds is one profile, not the system. No brand kit selected for a project → halt (never silently default a brand).

## Architecture (reshaped: 6 layers + governance wrapper)

| Layer | Owns | Human vs machine |
|---|---|---|
| **L1 Direction** | Taste-as-code: a **pluggable brand-kit profile** (design tokens + 3-4 exemplar reference screenshots + DNA rubric), loaded per project and fed via vision to the builder (constraints) and the floor-checker (rubric). Brand-kit-agnostic; RocketMinds is the first profile. Memory/library grows per profile over time. | Human seeds the kit; machine applies |
| **L2 Material** | Asset factory: image generation + SVG/icon/illustration first; motion/3D/video later. The one true greenfield. | Machine generates; human selects |
| **L3 Build** | Compose within the design system (web-artifacts-builder + shadcn already installed + 21st.dev components). | Machine |
| **L4 Floor** (not "judge") | Deterministic + objective only: contrast/WCAG, orphan-words, responsive breakpoints (desktop AND mobile screenshots), broken-layout, perf. A model assists by flagging defects and surfacing options; it never scores "world-class." | Machine |
| **L5 Route + diverge** | Auto-discovered best model per task (no hardcoded IDs); generate N divergent directions and present them to the human to choose. No automated judge-merge (that is the regression trap). | Machine proposes; human picks |
| **L6 Enforce + orchestrate** | One bundled command on the existing delivery/off-ramp spine; a hook that refuses to call a web build "done" until the L4 floor passes AND a screenshot was rendered and reviewed. Enforces the floor + forces review, not taste. | Machine gates |
| **Governance (wrapper)** | One spine serves web/app/marketing; metrics: floor pass-rate, iterations-to-ship, % shipped without Gary rework. | — |

Net: the system raises the floor to "clean, on-brand, high-contrast, real components, real imagery" every time and removes Gary from policing it. Gary spends attention only on the taste ceiling and direction choice.

## Where existing assets fit (integration map)

**Coverage scorecard.** Of 6 layers, only L2 is true greenfield. L1 ~70%, L3 ~80%, L4 ~75% of parts but ~10% as a wired loop, L5 ~30%, L6 ~40% (zero hooks). Mostly assembly + enforcement with one real build.

**Skills (LB = load-bearing, REP = replaceable):**
- `design:design-critique`, `design:accessibility-review` → L4 floor (LB). Must run on screenshots, auto-fire, blocking. accessibility-review owns the contrast bug; pair with a deterministic contrast check so it is not LLM-only.
- `design:design-system` → L1 (LB). Point it at a real RM token file that is a forced input at gen time.
- `anthropic-skills:web-artifacts-builder` → L3 (LB). The compose engine (React/Tailwind/shadcn). Wrap with L1 tokens in + L4 floor around.
- `anthropic-skills:canvas-design` → L2 day-1 stopgap (LB-ish). Vector/graphic generation with no new MCP; missing photographic imagery.
- `anthropic-skills:pptx` + `rocketminds-slide-generator` → proves design-language-as-code works; reuse its token defs as the L1 seed. Deck surface of governance.
- Brand-kit source → L1 (LB). For ANY brand, the generic `brand-voice` plugin (discover-brand / generate-guidelines / enforce-voice) produces the kit; `rocketminds-brand-voice` is just the RM-specific profile. Supplies the verbal half + palette/type/logo; the visual-token half is unbuilt.
- `c-gtm-g-marketing-asset-builder` (agent) → reposition as the brief writer feeding web-artifacts-builder (it outputs specs, not pixels).
- `a-biz-d-delivery` + `biz-off-ramp-bridge`/`-recommender` → L6 orchestration host for the bundled command (LB; extend, do not rebuild).
- `design:ux-copy`/`design-handoff`/`c-gtm-b-brand-positioning`/`c-gtm-aa-critic`/`user-research`/`biz-workshop-design` → REP or out of scope for graphic craft.

**Component libraries:**
- **shadcn** → L3 (LB); ALREADY installed on the RM site (`components.json`). Alone it produces the "plain boxes" look; needs L1 tokens + motion.
- **21st.dev** → L3/L2-richer; the key external acquire (real MCP exists). Crafted components on tap; directly fixes plain-boxes / empty-hero. Not yet wired.
- **Aceternity.UI** → REP for now (overlaps 21st; copy-paste, no MCP; higher integration cost). Source of Exat/Lando-style motion later.
- **Refero / Mobbin / Godly/Recent** → all collapse into one job: feed the L1 reference corpus. Zero value until screenshots are ingested. Mobbin strongest for real-app flows; buy only if we ingest.

**Exemplars (your 14 + distilled DNA)** → the raw material for L1 and the single most underused asset you own. You already did the hardest part (taste distillation). Encode the DNA lines verbatim as builder constraints + floor rubric (e.g., "dark-native by default" / "spacing+type as the only language, zero noise" / "one signature accent on black" / "confident CTAs, no urgency"). Screenshot the 3-4 closest (Tresmares = closest to RM, Linear, Zed, Lando) as vision references; the diff-vs-reference check compares renders against these. The other ~10 are the memory-library backlog.

## Recommended approach (phased)

**Phase 1 — Lean core. This is both the MVP and the kill-test.**
1. L1 seed: define the **brand-kit profile format** (engine-agnostic) and author the FIRST profile as the working example (RM, from brand-voice palette/type + slide-generator tokens + exemplar DNA lines) plus 3-4 exemplar screenshots. Any other brand loads the same way.
2. L4 floor loop: web-artifacts-builder → render on a dev server → Chrome screenshot (desktop + mobile) → deterministic contrast + orphan-word + broken-layout checks + accessibility-review → auto-fix → loop until the floor passes.
3. L2 input (clean-type-first): make image generation available so a slot CAN get real imagery when it beats type-only and passes brand coherence; clean type + space stays the preferred default, never slop-filled (canvas-design as day-1 stopgap; a dedicated image-gen MCP as the real fix).
4. L6 gate: a hook that blocks "done" until the floor passes and a screenshot was reviewed; wrap 1-3 in one bundled command on the delivery/off-ramp spine. The command presents 2-3 divergent directions for the key section so you make the final aesthetic pick (machine never auto-ships taste; full L5 automation deferred to Phase 2).

Validation built in: build ONE fresh premium sample section through the loop and a baseline without it. If the loop version clears contrast/orphan/mobile and looks materially better, the thesis is confirmed in production. This is the devil's advocate's 1-hour kill-test, delivered as the first increment instead of as a separate detour.

Acquire for Phase 1: nothing required to start (wire from installed assets + turn hooks on). Then 21st.dev MCP (fixes plain boxes), then an image-gen MCP (opens L2). Grant npm-install/build Bash permission (currently absent) so the loop can drive the dev servers. All model references auto-discovered, never hardcoded (per no-hardcoded-rotting-values).

**Phase 2 — Expand the capability (only after Phase 1 proves out).**
- Deepen L2 (illustration, then motion per Aceternity/Exat/Lando DNA, then 3D/video).
- L5 divergent-directions-for-human-choice (N directions, you pick; no auto-merge).
- Ingest the reference galleries (Mobbin/Refero/Godly) into the growing L1 memory library.
- Extend the one spine to app UI + marketing assets (flyers/social/ads via canvas-design + a Canva MCP).
- Vercel agent-skills (web-design-guidelines / react-best-practices) bolted into the L4 floor for code-audit rigor.

## Repository & sync
- **Create a GitHub repo** under personal account **GFilipp** (authenticated; token has `repo` scope) to version and sync the design-studio engine.
- **Name:** `ui-ux-design-studio` (brand-agnostic; renamed per your call, not tethered to RocketMinds).
- **Visibility:** private to start. Because the engine carries no proprietary brand assets, it could be made public / open-sourced later if you want.
- **Committer identity:** `Gary Filipp <79236069+GFilipp@users.noreply.github.com>` (current global default; privacy-preserving; matches the personal account).
- **Contents — the brand-agnostic ENGINE only (NOT the rest of `~/Documents/Claude`):** this plan; the bundled command/skill + hook scripts + design-pod orchestration; the brand-kit profile FORMAT + one example profile; the exemplar-corpus index; the `design-run` state schema; a `learnings.md` (memory that compounds). Real brand kits (RM, client, garyflip, tegy) stay external inputs, never committed.
- `.gitignore` for secrets/keys/`.claude.json` and any real brand-kit assets; no credentials or proprietary brand files committed.

## Critical files / surfaces the build will touch (read-only so far)
- `/Users/garyfilipp/.claude/settings.json` — add the hook (the gate) + Bash npm/build permission. Route through the `update-config` skill.
- Brand-kit profile format + the first example profile (in the engine repo as a sample; real / proprietary brand kits stay external inputs).
- New brand-agnostic bundled command/skill (e.g. `design-studio`) hosted on the `a-biz-d-delivery` / off-ramp spine; composes the active brand kit + tokens + builder + floor loop.
- MCP config (`~/.claude.json`) — add 21st.dev + an image-gen server.
- A reference-screenshots directory for the L1 corpus.
- New GitHub repo `ui-ux-design-studio` (private to start) under GFilipp (via `gh repo create`), committer = the noreply identity; holds the brand-agnostic engine artifacts listed above.

## Verification
- Build one fresh premium page section via the bundled command. Confirm: contrast passes on desktop AND mobile screenshots; no orphan words; real imagery present; crafted components (not plain boxes); no console errors.
- Baseline comparison: same section built without the loop; Gary eyeballs both. The loop version should clearly clear the floor and look better.
- Metrics: iterations-to-floor-pass, and whether Gary had to fix the floor (target: zero).
- Repo: confirm `ui-ux-design-studio` exists under GFilipp, the engine files are pushed, and commits are attributed to `79236069+GFilipp@users.noreply.github.com`.
- Brand-agnostic proof: build the same section against two different brand kits and confirm the output reflects each kit, with no hardcoded brand.

## Risks (carried from the devil's advocate, not dismissed)
1. Model judge cannot arbitrate taste → MITIGATED by design: machine owns the floor only; human owns the ceiling; no auto-merge.
2. Hooks force invocation, not quality (false green) → MITIGATED: the gate enforces deterministic floor checks + forces human review of a real screenshot, not a model "looks good."
3. Over-build for volume → MITIGATED: Phase 1 is lean and doubles as validation; expensive layers (L5, multi-surface, deep L2) are gated on proof.
4. Maintenance / rot (best-model routing) → MITIGATED: auto-discover models, env-override, no hardcoded IDs.
5. Demo is not a system (breaks across breakpoints) → MITIGATED: the floor runs on desktop AND mobile; orphan/contrast checked on both.
- Residual: if even the lean core produces competent-but-generic output you still dislike, that confirms the ceiling is taste/brief; we then lean harder on human direction + bought point-solutions for hero assets. Phase 1 surfaces this cheaply, before any heavy spend.
