# Brand-kit profile format (brand-agnostic)

A **brand kit** is the only brand-specific input to the engine. The engine itself
hardcodes no brand. Swap the kit, get a different brand's output from the same pipeline.
No kit selected for a run → the run **halts** (never silently defaults a brand).

A profile is a directory containing:

```
<kit-name>/
  brand-kit.json     # tokens: color, type, logo, voice pointer, dna rubric pointer
  dna-rubric.md      # binary design rules the builder must satisfy + human judges against
  references/        # 3-4 exemplar screenshots fed to the builder + floor rubric (vision)
    INDEX.md
```

## brand-kit.json keys

| Key | Meaning |
|---|---|
| `name` | human label |
| `mode` | `light` \| `dark` \| `auto` |
| `color` | `bg`, `surface`, `text`, `muted`, `accent`, `accentText` as `{r,g,b}` (sRGB 0-255) |
| `type` | `display` / `body` `{family, weights[]}`; `scale[]` (px steps) |
| `logo` | `{wordmark, asset}`; asset is an external path, never committed to the engine repo |
| `voice` | `{skill, tenets[]}` — which brand-voice profile governs copy |
| `dna_rubric` | relative path to the rubric file |

Optional keys (used when the brand needs them):

| Key | Meaning |
|---|---|
| `status` | provenance note: where the values came from + what to verify before production use |
| `color.border`, `color.faint`, `color.accent2` | extended palette: hairline borders, tertiary text, a sparse secondary accent |
| `type.mono` | third face for labels/eyebrows/code when it differs from `body` |
| `motifs` | signature visual devices as strings (e.g. blueprint grid, sharp corners, reveal-on-scroll) |

Real / proprietary kits (RocketMinds, clients, garyflip, tegy) live OUTSIDE this repo as
external inputs. The repo ships ONE example profile to document the format.
