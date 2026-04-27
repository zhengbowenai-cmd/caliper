# Caliper as a skill — drop-in for any agent

This directory ships **Caliper itself as a skill** so any agent that
respects the SKILL.md format (Claude Code, Hermes, OpenClaw, anything
implementing the [agentskills.io](https://agentskills.io) standard) can
invoke `caliper compare`, `caliper lint`, `caliper iterate`, and
`caliper analyze` from inside its own conversation.

## Files

| File | Purpose |
|------|---------|
| `caliper/SKILL.md`         | Canonical SKILL.md — works in Claude Code, Hermes, OpenClaw, agentskills.io |
| `caliper/cursor-rules.mdc` | Cursor rule file — copy to your `.cursor/rules/` |

## Install per-agent

### Claude Code

```bash
mkdir -p ~/.claude/skills/caliper
curl -L https://raw.githubusercontent.com/zhengbowenai-cmd/caliper/master/skills/caliper/SKILL.md \
  > ~/.claude/skills/caliper/SKILL.md
```

Restart Claude Code. The skill will auto-trigger on prompts about prompt evaluation.

### Hermes Agent

```bash
hermes skills install caliper --from github:zhengbowenai-cmd/caliper:skills/caliper
# or manually:
curl -L https://raw.githubusercontent.com/zhengbowenai-cmd/caliper/master/skills/caliper/SKILL.md \
  > ~/.hermes/skills/caliper/SKILL.md
```

### OpenClaw

```bash
mkdir -p ~/.openclaw/skills/caliper
curl -L https://raw.githubusercontent.com/zhengbowenai-cmd/caliper/master/skills/caliper/SKILL.md \
  > ~/.openclaw/skills/caliper/SKILL.md
```

### Cursor

Copy `caliper/cursor-rules.mdc` into your project's `.cursor/rules/`
directory, or your global Cursor rules folder. Cursor will load it
automatically.

```bash
mkdir -p .cursor/rules
curl -L https://raw.githubusercontent.com/zhengbowenai-cmd/caliper/master/skills/caliper/cursor-rules.mdc \
  > .cursor/rules/caliper.mdc
```

### Aider

Add to your `aider.conventions.md` (or `--read` it explicitly):

```bash
aider --read https://raw.githubusercontent.com/zhengbowenai-cmd/caliper/master/skills/caliper/SKILL.md
```

### Continue (VS Code / JetBrains)

Drop `SKILL.md` into your `.continue/rules/` directory.

### Codex CLI

Pull the SKILL.md content into your `~/.codex/instructions.md` (Codex
doesn't have native skills yet — use it as a system-level rule).

### Any OpenAI-compatible agent (universal fallback)

Caliper is just a CLI. Any agent that can run shell commands can use it
directly without a skill file:

```python
# inside your agent harness
result = subprocess.run(
    ["caliper", "compare", "old.md", "new.md", "--eval", "cases.jsonl"],
    capture_output=True, text=True,
)
```

## Updating

The canonical SKILL.md lives in this repo. To update your installed
copy, re-run the curl command above.

## Contributing

Found a place where the skill triggers wrongly, or fails to trigger
when it should? Open an issue or PR — see
[`CONTRIBUTING.md`](../CONTRIBUTING.md).
