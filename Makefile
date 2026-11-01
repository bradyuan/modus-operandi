export PATH := /opt/homebrew/bin:$(HOME)/.local/bin:$(PATH)

.PHONY: setup run test

setup:  ## once: install uv, cloudflared, and MO's Python packages
	@command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
	@command -v uv >/dev/null || brew install uv
	@command -v cloudflared >/dev/null || brew install cloudflared
	uv sync

run:    ## every time: start MO behind a fresh public link; Ctrl+C stops it
	uv run mo

test:
	uv run pytest -q
