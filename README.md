# Modus Operandi (MO)

**Long-Term Memory for AI**

Everything you read makes sense to you. Everything you write sounds like you.

> **Status:** redesign in progress. The v1 design is in [docs/DESIGN-v1.md](docs/DESIGN-v1.md)
> (draft, pending sign-off). The current code is a prototype and will be rebuilt to match it.

## 1. What problem does Modus Operandi solve?

Reading and writing with AI still takes hours, and the results don't feel like yours.

**Reading:** AI explanations are generic. They don't know what you already understand, which analogies click for you, or how deep to go. "Explain like I'm 5" is a difficulty level, not an explanation built for *your* brain.

**Writing:** AI drafts drift toward generic AI language. Even with instructions, longer pieces and later conversations lose your voice, and you spend as long fixing a draft as you would writing it.

Both are the same problem: **the AI doesn't keep what you've taught it, and nothing makes it use what you've taught it.** An explanation is output, and so is an essay. MO fixes both with one mechanism.

## 2. How does it work?

MO keeps a **persistent store of your own judgments**, per profile, and makes ChatGPT work through all of it before you see anything.

| Command | What you do | What happens |
|---|---|---|
| **`@MO seed`** | Paste a perfect example: your own writing, or an excerpt you want to sound like | Stored exactly as given |
| **`@MO tune`** | Pick between three versions of a part (A / B / C) until it's right, saying why when it isn't | The whole back-and-forth is stored as one example |
| **`@MO`** | Ask for anything: explain this paper, write this cover letter | ChatGPT drafts, then reworks the draft against your seeds and tunes, pass by pass, until it has gone through all of them. The result appears in the MO box. |
| **`@MO profiles`** | List, create, or delete profiles | One profile per purpose: an AI tutor, an essay writer, a journal |

**Seeding and tuning fill the store. Output reads it.** Tunes you worked hardest on (the most rounds) go first, because ten rounds of "not quite" teach more than one "looks good."

## 3. What makes it different

- **MO doesn't trust the AI.** ChatGPT writes; it never judges, never carries your answers, and never decides what gets stored. Your clicks and notes go straight to MO.
- **You are the only judge.** MO runs no checks and makes no AI calls. It records your evaluations, verbatim, and enforces the order of steps.
- **Nothing is skipped silently.** Output appears only after ChatGPT has worked through your whole store. If it skips, there's no MO box, and you can see it.
- **The wrong profile is never used.** If MO isn't sure which profile you mean, it asks.

## 4. Planned delivery

MO is planned as a ChatGPT plugin built on [MCP](https://modelcontextprotocol.io), with an MO box inside the chat for your clicks. Your data is kept to a minimum and yours to export or delete.

## Development (prototype)

Requires [uv](https://docs.astral.sh/uv/) and [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) for testing in ChatGPT.

```bash
uv sync          # install dependencies
uv run pytest    # run tests
uv run mo-dev    # start MO behind a temporary public link for ChatGPT, with a local trace page
```

`mo-dev` prints a private link (add it in ChatGPT as a custom MCP server, no authentication; it changes on every restart) and a trace page at `http://127.0.0.1:8000/trace` (this computer only) showing every call MO received.

Data lives in `~/.mo/` (override with `MO_HOME`). Never commit it.

## Docs

- [Design v1](docs/DESIGN-v1.md): the design being built (draft)
- [Decisions](docs/decisions/): why the direction changed
- [Prototype design](docs/DESIGN.md): the earlier design, kept for reference
