# Modus Operandi (MO)

**Long-Term Memory for AI**

Everything you read makes sense to you. Everything you write sounds like you.

> **Status:** early design. No code yet. See [docs/DESIGN.md](docs/DESIGN.md).

## 1. What problem does Modus Operandi solve?

Reading and writing with AI still takes hours, and the results don't feel like yours.

**Reading:** AI explanations are generic. They don't know what you already understand, which analogies click for you, or how deep to go. "Explain like I'm 5" is a difficulty level, not an explanation built for *your* brain.

**Writing:** AI drafts drift toward generic AI language. Even with instructions, longer pieces and later conversations lose your voice, and you spend as long fixing a draft as you would writing it.

Reading and synthesizing a topic can take 2 hours. Writing it up can take another 2. MO aims to cut each to minutes.

## 2. What does Modus Operandi do?

MO keeps a **persistent profile of you** and applies it in two directions.

**Reading (world → you):** Give MO any source, such as a paper, a contract, or an article. It explains the source in terms that make sense to you, builds on what you already know, and points back to the original so you can check what was simplified.

**Writing (you → world):** Give MO a rough idea and some data. It turns them into finished prose in your voice, using only the claims your data supports.

## 3. How does it work?

### Calibrate, then use

MO has two modes:

1. **Calibrate:** Short exercises build your profile: pick which explanation clicks, choose which paragraph sounds like you, upload writing samples. You approve every change to your profile before it takes effect.
2. **Use:** MO reads your profile while you work, but **never changes it on its own**. That way your profile can't slowly drift.

### It learns from you, with your approval

While you use MO, it notices patterns: what you rate well or poorly, and how you edit its drafts. It saves these as suggestions for your next calibration. For example: *"You removed em dashes in 9 of 11 drafts. Add a rule?"*

### A profile you can read

Your profile is compact, human-readable text: preferences with the reasons behind them, plus a few examples of what you liked best. You can open it, edit it, and take it to any AI model.

## 4. How is it different from an ordinary LLM?

Ordinary LLMs start fresh, or rely on loose memory and instructions that drift over time.

**MO keeps a stable, user-approved profile of how you understand and how you write, and applies it every time.**

## 5. Planned delivery

MO is planned as an [MCP](https://modelcontextprotocol.io) app, so one profile works across ChatGPT, Claude, and other AI tools: type `@MO read`, `@MO write`, or `@MO tune`.

MO is a **harness**, not another AI. It keeps your profile, hands it to the AI you're already using, and checks the result. Your data is kept to a minimum, encrypted, and yours to export or delete.

## Development

Requires [uv](https://docs.astral.sh/uv/) and Node.js (for the MCP Inspector).

```bash
uv sync                      # install dependencies
uv run pytest                # run tests
uv run mo-server             # run over stdio
uv run mo-server --transport http --port 8000   # run over HTTP at http://127.0.0.1:8000/mcp

# Try the tools in a browser UI
npx @modelcontextprotocol/inspector uv run mo-server
```

### Connect to ChatGPT (developer mode)

```bash
cloudflared tunnel --url http://127.0.0.1:8000
# prints https://<random-name>.trycloudflare.com; in a second terminal:
uv run mo-server --transport http --port 8000 --public-host <random-name>.trycloudflare.com
# prints the full link with a secret path; keep it private
```

In ChatGPT: **Settings → Apps & Connectors → Advanced → Developer mode**, then create a connector with that link and no authentication. The tunnel name changes on every restart, so update the link each session.

### Profiles

Manage profiles from inside ChatGPT with `@MO profile`: list, create, and switch profiles, save your own writing samples ("use this essay as a sample" saves it right away). Use `@MO tune` to get variations until one fits, or to calibrate with a writing or reading diagnostic.

Data lives in `~/.mo/` (override with `MO_HOME`): profiles in `profiles/<name>/`, a tool-call log in `logs/calls.jsonl`. Samples are plain files in `profiles/<name>/exemplars/<register>/`, where register is one of `email`, `essay`, `cover_letter`, `article`, `notes`, or `other`. Never commit them.

## Docs

- [Design](docs/DESIGN.md): product design and open questions
- [Decisions](docs/decisions/): why the direction changed
