# UX laws: what this engine encodes, and what it deliberately does not

Decided 2026-09-08. The point of writing this down is so a future scan or a screenshot of
"20 UX laws to tell Claude" does not re-add things we already judged out of scope.

## Enforced as objective gates (`engine/floor/floor_check.py`)
| Law | Gate | Behaviour |
|---|---|---|
| **Fitts's law** (target size/distance) | `targets` | BLOCKS: min 44px on touch breakpoints; 24px warn on pointer. Inline prose links are exempt — they are text, not standalone hit areas. |
| readability floor | `type_size` | BLOCKS under 12px body on touch; warns to 15px. |
| **Miller's law** (measure half) | `measure` | BLOCKS over ~130 characters per line; warns over 100. Comfortable body measure is 45-75. |
| RULES 5, density half | `density` | WARNS on any single text block over 120 words. |
| **Hick's law** + **Miller's law** (choice load) | `choices` | WARNS on a sibling set of 10+, or primary nav over 7 links. Warn-only on purpose: a 12-logo wall can be correct. |

Note "minimize target distance" from the popular list is not a separate law; it is the
distance half of Fitts's and is covered by the same gate.

## Encoded as human judgment (brief §4b + DNA rubric), NOT as thresholds
Serial position effect, peak-end rule, Von Restorff effect, and the Gestalt four (proximity,
similarity, uniform connectedness, Prägnanz). These need a view of the whole composition and an
intent. A numeric threshold here would fake precision we do not have, and the human already
judges the candidates against the rubric at the pick.

**Jakob's law** is satisfied structurally rather than checked: RULES 4 forces real library
components, which is what "works the way users expect" means in practice.

## Deliberately REJECTED for this tool, with reasons
| Law | Why not |
|---|---|
| **Postel's law** (be liberal in what you accept) | An input-handling principle. These are marketing assets; there are rarely forms to be liberal with. |
| **Tesler's law** (conservation of complexity) | A product-design tradeoff about where complexity lives. Nothing to measure on a landing page. |
| **Parkinson's law** | About elapsed time filling available time. Relevant to project scoping, not to a hero section. |
| **Zeigarnik effect** (incomplete tasks are remembered) | Applies to multi-step flows and progress indicators. A one-page asset has no task to leave incomplete. |
| **Doherty threshold** (<400ms response) | Genuinely relevant, but it is a PERFORMANCE gate (LCP/INP) and this engine has none. Adding a real perf gate is a separate, honest piece of work; asserting the law without measuring it would be theatre. |
| **Pareto principle** | A prioritisation heuristic for deciding what to build. It belongs in the brief conversation, not in a floor check. |
| **Occam's Razor** | Already covered concretely by RULES 5 and the rubric's "spacing and type carry the design; zero decorative noise". |

Source note: the popular "20 UX laws" list circulating as a lead magnet repackages
lawsofux.com (Jon Yablonski, a legitimate source) but lists Postel's law twice and counts the
Fitts corollary separately, so it is ~18 distinct principles, not 20.
