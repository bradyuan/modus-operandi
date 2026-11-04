export PATH := /opt/homebrew/bin:$(HOME)/.local/bin:$(HOME)/.fly/bin:$(PATH)
APP = $(shell sed -n 's/^app = "\(.*\)"/\1/p' fly.toml)

.PHONY: setup test setup-host deploy logs

# --- MO runs only hosted (AGENTS.md item 10); tests are plumbing only ------------

setup:  ## once: install uv, flyctl, and MO's Python packages
	@command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
	@command -v uv >/dev/null || brew install uv
	@command -v fly >/dev/null || brew install flyctl
	uv sync

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

logs:
	fly logs --app $(APP)
