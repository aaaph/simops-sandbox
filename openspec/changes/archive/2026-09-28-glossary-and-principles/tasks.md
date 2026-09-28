# Tasks

## 1. Project context

- [x] 1.1 Replace the template comments in `openspec/config.yaml` with a `context` holding the glossary (both bounded contexts), the principles, the supported stack and the conventions as reviewed in proposal.md; verify the file parses (`pixi run python -c "import yaml; yaml.safe_load(open('openspec/config.yaml'))"`), the `context` stays under 51,200 bytes, and `openspec instructions proposal --change glossary-and-principles --json` returns it in `context`
- [x] 1.2 Add `rules`: for `proposal` and `specs` — use the glossary's terms, no synonyms, a new term enters the glossary in the change that first uses it, terms with behavior are defined by requirements and only named in the glossary; for `tasks` — unit tests without Docker, network or autopilot builds, Docker tests on existing images; verify `openspec instructions specs --change glossary-and-principles --json` and `openspec instructions tasks --change glossary-and-principles --json` return them in `rules`

## 2. Docs

- [x] 2.1 In AGENTS.md, replace the "Words:" definitions with one sentence pointing to the glossary in `openspec/config.yaml` (keep the paragraph's description of what `simops` does); verify the terms environment, bundle, session and scenario are defined only in `openspec/config.yaml`

## 3. Check

- [x] 3.1 Check AGENTS.md, `sim/simops.py` docstrings and `openspec/specs/` against the glossary for synonyms (e.g. "robot" for an agent, "scenario" for the environment); fix AGENTS.md and docstrings, and list any spec wording that needs a change of its own; record the result in this task — result: AGENTS.md "robot code"/"robot repos" → "robot software" (fixed); `robots:` in `simops.py` and the `environment` spec is the rejected old key (intended); "scenario" appears only as the reserved word (intended); AGENTS.md's "PX4 spawns its vehicle" is PX4's own word in PX4's context (kept); no spec wording needs a change of its own
