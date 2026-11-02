export PATH := /opt/homebrew/bin:$(HOME)/.local/bin:$(HOME)/.fly/bin:$(PATH)
APP = $(shell sed -n 's/^app = "\(.*\)"/\1/p' fly.toml)

.PHONY: setup run test setup-host deploy link trace logs

# --- local -------------------------------------------------------------------

setup:  ## once: install uv, cloudflared, flyctl, and MO's Python packages
	@command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
	@command -v uv >/dev/null || brew install uv
	@command -v cloudflared >/dev/null || brew install cloudflared
	@command -v fly >/dev/null || brew install flyctl
	uv sync

run:    ## local MO behind a temporary link (changes every run); Ctrl+C stops it
	uv run mo

test:
	uv run pytest -q

# --- hosted (Fly.io): one fixed link; `make deploy` ships each change ----------

setup-host:  ## once: make setup-host APP=<a-unique-name>   (needs `fly auth login` first)
	@test -n "$(APP)" -a "$(APP)" != "CHANGE-ME" || { echo "Usage: make setup-host APP=<a-unique-name>"; exit 1; }
	sed -i '' 's/^app = ".*"/app = "$(APP)"/' fly.toml
	fly apps create $(APP)
	fly volumes create mo_data --app $(APP) --region $$(sed -n 's/^primary_region = "\(.*\)"/\1/p' fly.toml) --size 1 --yes
	@echo "\nNext: make deploy, then make link."

deploy:  ## ship the current code; the link and the data stay the same
	fly deploy --app $(APP) --ha=false

link:    ## print the private MO link for ChatGPT (set it once)
	@echo "https://$(APP).fly.dev/mcp/$$(fly ssh console --app $(APP) -q -C 'cat /data/secret' | tr -d '\r\n ')"

trace:   ## the hosted MO's trace, privately: open http://127.0.0.1:8000/trace while this runs
	@echo "Open http://127.0.0.1:8000/trace (Ctrl+C to stop)"
	fly proxy 8000:8080 --app $(APP)

logs:
	fly logs --app $(APP)
