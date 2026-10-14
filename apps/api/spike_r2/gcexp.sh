#!/bin/bash
# Reseeds a size and runs the garbage collector experiment on it:  bash gcexp.sh 5000
SIZE=$1
WORKTREE=/mnt/c/Users/Stefan.Insam/dev/lorenzo-worktrees/spike/release-scale/apps/api
bash "$WORKTREE/spike_r2/run.sh" "$SIZE" seed > /dev/null 2>&1
cd ~/lorenzo-r2/api && source spike_r2/env.sh
mise exec -- uv run python -m spike_r2.gcexp "$SIZE" 2>&1 | tee ~/lorenzo-r2/results/log_gc_$SIZE.txt
cp -r ~/lorenzo-r2/results/. "$WORKTREE/spike_r2/results/"
