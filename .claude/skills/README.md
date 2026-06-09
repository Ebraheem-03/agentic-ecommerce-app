# Skills in this project

Your personal skills in `~/.claude/skills/` are already available to the **main Claude Code thread**
in every project (loaded at startup, invoked on demand by their description).

## Two things specific to this project

### 1. Commit them as project skills (recommended for a portfolio repo)
So the repo is self-contained and works in CI / for anyone who clones it, copy each skill folder here
and commit it. The directory name must equal the skill's `name`.

```bash
# from the project root — adjust folder names to match your installed skills
cp -r ~/.claude/plugins/marketplaces/google-labs-code-stitch-skills       .claude/skills/stitch
21st-dev was added as an MCP to claude code use that.
cp -r ~/.claude/skills/impeccable    .claude/skills/impeccable
git add .claude/skills && git commit -m "chore: vendor project skills"
```

If a skill name collides across levels, **personal overrides project** (and enterprise overrides personal).

### 2. Subagents do NOT inherit skills automatically
The specialist agents (Nova, Iris, …) won't pick up a skill just because it's installed. Each agent that
needs a skill is already **told to use it in its system prompt** (`.claude/agents/*.md`):
- **Nova** → Google Stitch (branding, logos, screens)
- **Iris** → 21st.dev (components) + Impeccable (UI build standard)

Make sure those agents have the `Read` (and `Bash`, if the skill bundles scripts) tools so they can read the
`SKILL.md` and run anything bundled. They already do in their frontmatter.

## After adding/changing skills
Restart the Claude Code session (skills load at startup), then verify:

```
> what skills do you have available?
```
