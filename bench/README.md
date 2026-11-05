# MO latency benchmark

Measures how long `@MO` + a request takes end to end, over an external query set, so a pipeline change
is judged by numbers, not feel.

- **Queries:** `queries.jsonl`: 300 prompts sampled from [Databricks Dolly-15k](https://huggingface.co/datasets/databricks/databricks-dolly-15k)
  (CC BY-SA 3.0; this sample is shared under the same license). 75 each of open_qa, general_qa,
  creative_writing, summarization; context ≤ 600 words; seed 15. Rebuild: `uv run python -m bench.dataset`.
- **Harness:** an OpenAI model (Responses API) stands in for ChatGPT and runs MO's real tool loop
  (`mo_output` → `mo_output_pass` …) against local MO servers, one per tune schedule, each with its own
  copy of one frozen profile. Every query runs on all schedules at the same time.
- **Reported:** p50 / p95 / p99 end-to-end (last pass accepted), p50 time to first voiced version,
  passes, model calls, output tokens, and every run that didn't finish.

```
export OPENAI_API_KEY=…        # your shell only
uv run python -m bench.harness run --profile-dir bench/profiles/<profile> \
    --schedule A=1,3,10,30 --schedule B=10,30,100 --model gpt-5 --limit 300
uv run python -m bench.harness report bench/results/<file>.jsonl
```

Frozen profiles, raw results, and work folders stay local (`.gitignore`): they hold the user's writing.
