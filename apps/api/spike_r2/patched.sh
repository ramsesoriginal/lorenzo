#!/bin/bash
# Reseeds 20,000 and times the bridge's updates with and without the proposed local_of fix.
DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$DIR/run.sh" 20000 "seed timings" > ~/lorenzo-r2/run_20000_patched.log 2>&1
cd ~/lorenzo-r2/api && source spike_r2/env.sh
for patch in "" 1; do
  R2_PATCH_LOCAL_OF=$patch mise exec -- uv run python -m spike_r2.patched_run 20000 2>&1 | tee -a ~/lorenzo-r2/results/log_patched_20000.txt
done
cp -r ~/lorenzo-r2/results/. "$DIR/results/"
