# MO v1 — Hosting: from a tunnel to the cloud, from one user to many

Status: **Approved** · 2026-11-02 · part of v1 · log: [LESSONS.md](LESSONS.md)

Finishing v1 means moving MO off the laptop tunnel onto Fly.io, for many users. The rule doesn't
change: ChatGPT produces, MO keeps the books, the HUMAN USER evaluates only through the MO window.
Tools, windows, the window's signed direct line, the event log, seeds, tunes, and output passes all
work as before. What changes is **where MO runs** and **whose data each call touches**.

## 1. Where MO runs

| | Before | After |
|---|---|---|
| Server | laptop, behind a temporary Cloudflare address | one Fly machine, `modus-operandi-v1.fly.dev` |
| Data | `~/.mo` | Fly volume `/data` (encrypted) |
| ChatGPT link | `/mcp/<secret>`, new each run | `/mcp`, fixed, the same for everyone |
| Ship a change | restart `make run` | `make deploy` |

Removed: the tunnel (`mo.dev`, `make run`), the link secret, the trace's "this computer only" check.

## 2. Sign-in

```
ChatGPT "Connect" → MO: "sign-in is WorkOS AuthKit"   (/.well-known/oauth-protected-resource)
→ WorkOS login (Google / Microsoft / Apple, one click) → ChatGPT holds a token
→ every tool call carries the token → MO checks it against WorkOS's public keys → user ID
```

- Anyone can sign up. MO stores **only the WorkOS user ID**.
- No token or a bad one → refused before any tool runs. ChatGPT never says who the user is.
- Admins: a sign-in whose **verified** email is in the `MO_ADMINS` Fly secret. The email is checked
  at sign-in, not stored.

## 3. Data: data → users → profiles (each 1 → N)

```
/data/
├── users/<user id>/
│   ├── profiles/<name>/{profile.json, seeds/, tunes/, runs/}
│   ├── chats/  tunes/  runs/  boxes/
│   └── events.jsonl          the user's own log
├── box-owners/<box id>       routing only: which user a window belongs to
└── mo-events.jsonl           MO-wide events with no user (e.g. calls refused for no token); no text
```

| Request | User comes from |
|---|---|
| ChatGPT tool call | the sign-in token |
| Window direct line | window key → `box-owners` → user (set from the token of the call that opened it) |
| Trace page | the browser's sign-in (WorkOS, same account) |

- **No default user.** No user → refused; never a shared fallback.
- Enforced in one place: `mo_home()` returns the current request's user folder, or fails.

## 4. Trace

- `@MO trace` opens a Trace window: this chat's recent MO activity, and **Open full trace**.
- Full trace: `https://modus-operandi-v1.fly.dev/trace`, signed in with the same account; each
  user sees only their own.
- Admins also get an **All users** tab: every user's full data and trace, read-only.

## 5. Account rules (AGENTS.md item 12)

- Delete account: two clicks in Config; wipes `/data/users/<id>/` and its `box-owners` entries.
- 50 MB per user: new seeds and tunes refused past it, said in the window.
- Export: download your folder from the trace page.

## 6. Build order (each step ends with the human user's test in ChatGPT)

1. **Sign-in spike:** MO deployed with sign-in required and one tool, `mo_whoami`.
   Test: Connect with Google, then Microsoft; `@MO who am I` in two chats.
   Works: Connect completes; the same ID every time. Fails: Connect errors, or IDs differ.
2. **Per-user folders:** all tools back, scoped per user. Test: a second account sees none of the
   first's profiles.
3. **Trace per user + `@MO trace` + admin tab.** Test: each account sees only itself; an admin sees both.
4. **Delete account, 50 MB cap, export.**
5. **Apple sign-in** (Apple Developer account, $99/year).

## 7. Risks and open questions

- How ChatGPT registers with WorkOS (dynamic client registration vs client ID metadata documents):
  step 1 finds out.
- Cold starts: the machine sleeps when idle; if the first call times out in ChatGPT, keep one
  machine running.
- Volume backups: check Fly's snapshot retention in step 1.
- Open: are alarms and OpenTelemetry part of finishing v1 (proposed: yes, before strangers use MO)?
- Before a public launch: a privacy policy (sign-in providers and ChatGPT's app directory ask for one).
