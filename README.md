# Modus Operandi (MO)

**Long-Term Memory for AI.** Everything you read makes sense to you. Everything you write sounds like you.

> **Status:** building [v1](docs/v1/DESIGN.md). `make setup` and `make run` work; in ChatGPT,
> Help, Config, Output, and Tune all work, with a voice per chat. The old prototype is under the `v0-prototype` git tag.

## Setup

**Once:**

```bash
make setup
```

Installs everything MO needs (uv, cloudflared, Python packages). macOS with [Homebrew](https://brew.sh).

**Every time:**

```bash
make run
```

Prints two links. Leave this terminal open; **Ctrl+C** stops MO.

```
MO is reachable at:  https://<random-name>.trycloudflare.com/mcp/<secret>   ← for ChatGPT (keep private)
Trace:               http://127.0.0.1:8000/trace                            ← for you (this computer only)
```

**Connect ChatGPT** (first time, and again whenever the link changes, which is every `make run`):

1. ChatGPT → **Settings → Apps → Advanced → Developer mode** on.
2. **Add custom MCP server** · Name: `MO` · URL: the *reachable at* link · Authentication: **none**.
3. Already added before? Open **Settings → Apps → MO**, update the URL, and **Refresh**.
4. Open a **new chat** and type `@MO`.

### Hosted: one fixed link (Fly.io)

So the ChatGPT link never changes and old MO windows keep working:

```bash
fly auth login                        # once (a free Fly.io account; it asks for a card)
make setup-host APP=<a-unique-name>   # once: creates the app and a 1 GB disk for MO's data
make deploy                           # every change: ships the code; link and data stay the same
make link                             # prints the private link: add it in ChatGPT once
make trace                            # then open http://127.0.0.1:8000/trace (private tunnel to the server)
make logs
```

`make run` still works for quick local experiments (a separate, temporary link).

## Use

Three MO windows, each opened by a command:

| You type | Window |
|---|---|
| **`@MO` + anything** | **Output**: ChatGPT's answer reworked against your seeds, labeled with the voice it was written in. Attach files or paste text and links in the chat as usual. |
| **`@MO`** · `@MO config` · `@MO profile` · `@MO seed` | **Config**: Profiles (create, delete, *Use in this chat*) and Seeds |
| **`@MO help`** | **Help** |
| **`@MO tune`** · or **Tune voice profile** under an output | **Tune**: say what part you didn't like (or skip), pick between A / B / C with comments until you confirm; it goes into the voice |

- **Voice for this chat:** each chat has its own voice (a profile). Only you set it, in an MO
  window in that chat (Config, the Output window, or when a chat's first output asks), and it
  stays until you change it. Nothing carries over between chats.
- **Seeds:** perfect examples (yours, or anyone's), pasted into the Seeds tab, saved exactly as
  plain text into this chat's voice. Check seeds to delete them.
- Only what you click or type **in an MO window** counts; typed answers in the chat aren't recorded.

## Check what happened

Open **http://127.0.0.1:8000/trace** while `make run` is running. It works only on this computer, never through the public link.

- **Every event, with who caused it:** HUMAN USER (a click in the MO box), CHATGPT (a tool call), MO, or DEV (you, debugging).
- **Outputs:** ChatGPT's first draft vs. the final, and every pass in between.
- **Tune boxes:** every round, pick, and note.
- **Alarms:** anything that broke the rules, e.g. a click that didn't come from the box, an old box reused, a pass skipped or unchanged, an output that was never shown.

For scripts and debugging: `/trace/events` (JSON), `/trace/events/stream` (live), `/trace/profiles/<name>`, `/trace/boxes/<id>`, `/trace/alarms`.

## Why MO

AI explanations are generic: they don't know what you already understand, which analogies click, or how deep to go. AI writing drifts toward generic AI language, and longer pieces lose your voice. Both are the same problem: **the AI doesn't keep what you've taught it, and nothing makes it use it.**

MO keeps a store of **your own judgments** (seeds and tunes), per profile, and makes ChatGPT work through all of it before you see anything.

- **MO doesn't trust the AI.** ChatGPT writes; it never judges, never carries your answers, and never decides what's stored.
- **You are the only judge.** MO runs no checks and makes no AI calls. It records your evaluations and enforces the order of steps.
- **Nothing is skipped silently**, and **the wrong profile is never used**: when in doubt, MO asks.

Your data lives in `~/.mo/` on this computer. Never commit it.

## Docs

- [v1 design](docs/v1/DESIGN.md) and [v1 lessons](docs/v1/LESSONS.md): what's being built, and what building it teaches us
- [v0 lessons](docs/v0/LESSONS.md): why the prototype was reset
