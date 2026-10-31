# Running MO as a Custom GPT (temporary)

> ⚠️ **Custom GPTs are being retired.** OpenAI is replacing them with ChatGPT **plugins**, which
> are built on MCP, so the MCP adapter (`mo-server`) is the long-term path. Reported dates
> (2026-10-31; verify): new GPT creation may already be closed (Oct 26, 2026, at least for some
> workspaces), and standard retirement is **Dec 11, 2026**. Custom Actions don't migrate
> automatically. Use this adapter only if it still lets you test on your plan.
> Sources: [OpenAI Help: GPT Actions](https://help.openai.com/en/articles/9442513-gpt-actions),
> [Visual Studio Magazine](https://visualstudiomagazine.com/articles/2026/09/28/openai-replacing-custom-gpts-with-plugins-including-for-codex-in-vs-code.aspx),
> [Virtualization Review](https://virtualizationreview.com/articles/2026/09/28/openai-to-retire-custom-gpts-replace-them-with-plugins.aspx).

ChatGPT's developer mode, which the MCP adapter needs, isn't available on every plan. A
**Custom GPT with Actions** calls MO's plain HTTPS API, described by an OpenAPI schema. Both
adapters expose the same core (`mo.api`), so behavior is identical. The 300-character limit
on Action descriptions is from memory; verify it.

```
Custom GPT "MO" ──Actions (HTTPS + Bearer token)──► mo-actions ──► mo.api ──► ~/.mo
ChatGPT/Claude  ──MCP (developer mode / connector)──► mo-server  ──┘
```

## Setup (development, via tunnel)

1. Start a tunnel: `cloudflared tunnel --url http://127.0.0.1:8000` and note the
   `https://<name>.trycloudflare.com` address.
2. In the project folder: `uv run mo-actions --port 8000 --public-host <name>.trycloudflare.com`
3. Print the GPT instructions: `uv run mo-actions --print-instructions`
4. In ChatGPT: **Explore GPTs → Create → Configure**
   - **Name:** MO
   - **Instructions:** paste the output of step 3
   - **Actions → Create new action → Import from URL:** `https://<name>.trycloudflare.com/openapi.json`
   - **Authentication:** API Key, **Bearer**, key = the contents of `~/.mo/secret`
   - **Visibility:** only me (the key gives access to your profile)
5. Use it: open the GPT directly, or type `@MO` in any chat to bring it in.

The tunnel name changes whenever cloudflared restarts; re-import the schema when it does.

## Differences from the MCP adapter

| | MCP (`mo-server`) | GPT Actions (`mo-actions`) |
|---|---|---|
| Plans | Developer mode (Pro/Business/Enterprise) or Claude connectors | Any plan that can create GPTs, including Plus |
| How it's invoked | `@MO` on the app, in any chat | `@MO` on the GPT, or chatting with the GPT |
| Tool descriptions | Full text, per tool | Short (300-char Actions limit); full guidance in the GPT's Instructions |
| Widgets (buttons, inline editing) | Possible (Apps SDK) | Not available |
| Auth (dev) | Secret path in the URL | Bearer token |

Verify current Custom GPT and Actions limits with OpenAI's docs before relying on them;
they are from memory as of 2025.
