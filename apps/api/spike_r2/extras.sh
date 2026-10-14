#!/bin/bash
# The extra experiments of extras.py for one size on the database as it is (run after run.sh).
#   bash extras.sh 5000
SIZE=$1
WORKTREE=/mnt/c/Users/Stefan.Insam/dev/lorenzo-worktrees/spike/release-scale/apps/api
bash "$WORKTREE/spike_r2/sync.sh"
cd ~/lorenzo-r2/api && source spike_r2/env.sh
mise exec -- uv run python -m spike_r2.extras "$SIZE" 2>&1 | tee ~/lorenzo-r2/results/log_extras_$SIZE.txt
mkdir -p "$WORKTREE/spike_r2/results"
cp -r ~/lorenzo-r2/results/. "$WORKTREE/spike_r2/results/"
