# MO v0 — Lessons

## 2026-11-01 — Limit reached; reset to v1

**What testing in ChatGPT showed** (from the trace of real sessions):

- MO stored feedback but enforced nothing. The reader profile had 14 pieces of feedback, 0 rules,
  and 0 samples, so every kit ChatGPT received was empty.
- Turning feedback into rules depended on ChatGPT choosing to do it. Even when MO's reply told it
  to, it didn't.
- Checks "passed" with nothing to compare against, so a pass meant nothing.
- The user's voice drifted over long chats: the calibration lived in the chat, not in MO.
- Every fix asked the AI to cooperate.

**The limit:** the prototype trusted the LLM inside its own data pipeline — to relay the user's
answers, to summarize feedback into rules, to pick profiles, and to decide when steps happen. A
harness built that way can't guarantee anything.

**Rejected going forward** (don't re-propose without new evidence):

- **AI-written rules or summaries in the store** (asking the host to "promote" feedback): the host
  skips it, and its wording isn't the user's.
- **MO-side checks or scoring** of drafts (AI-phrase lists, voice distance, best-of-N selection by
  MO): MO doesn't evaluate; the human user does.
- **Compaction** of the store: deciding that two pieces of feedback mean the same thing needs an AI.
- **A global active profile** and **profile choice by the host:** they cause wrong-profile use.
- **Separate reading and writing pipelines:** both are output.
- **A vector database / RAG:** retrieval is a fixed ranking by rounds, not similarity search.
- **Custom GPTs with Actions:** being retired by OpenAI; MCP is the path to ChatGPT plugins.
- **Relaying the human user's input through ChatGPT:** input goes only through the MO box.
