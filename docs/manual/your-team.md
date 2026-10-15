# Your team (agents and models)

With Claude Code the kit comes with seven small agents in `.claude/agents/`. Cheap models do the mechanical work, a stronger one judges what needs eyes. None uses Opus.

| Agent | Model | Job |
|---|---|---|
| `promo-intake` | Haiku | Runs the intake and reports BLOCK and WARN lines |
| `promo-runner` | Haiku | Starts a run and reads only the status and the log tail |
| `epic-compliance` | Haiku | Mechanical checks from `epic_specs.json` |
| `social-copywriter` | Haiku | Drafts the English subtitles |
| `release-manager` | Haiku | Version, changelog and test chores; never publishes |
| `art-director` | Sonnet | Judges the thumbnails from one contact sheet |
| `kit-auditor` | Sonnet | On request: audits the kit |

The rules that keep token use low are in `CLAUDE.md`: short replies, no polling, no whole-file reads of big logs or images. `python scripts\agent_cost.py` (or the console's `/costs`) shows where tokens went.
