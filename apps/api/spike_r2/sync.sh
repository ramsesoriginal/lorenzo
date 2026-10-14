#!/bin/bash
# Copies the spike worktree's apps/api to a clone on the native Linux filesystem (timings from
# /mnt/c are not trustworthy) and installs it.
SRC=/mnt/c/Users/Stefan.Insam/dev/lorenzo-worktrees/spike/release-scale/apps/api
mkdir -p ~/lorenzo-r2
rsync -a --delete --exclude .venv --exclude __pycache__ --exclude state --exclude results "$SRC" ~/lorenzo-r2/
cd ~/lorenzo-r2/api && mise trust . >/dev/null 2>&1; mise exec -- uv sync >/dev/null 2>&1
