#!/bin/bash
# The whole R2 run for one size, in WSL:  bash run.sh 5000 [steps]
#
#   steps (default "all"): any of  seed timings mem profile
#
# It copies apps/api to ~/lorenzo-r2/api on the native filesystem (timings from /mnt/c are not
# trustworthy), drops and recreates the spike database lorenzo_r2 on the container
# lorenzo-postgres-1 (localhost:55432), migrates it, seeds it, measures, and copies the result
# files back to spike_r2/results in the worktree.
set -e
SIZE=$1
STEPS=${2:-all}
WORKTREE=/mnt/c/Users/Stefan.Insam/dev/lorenzo-worktrees/spike/release-scale/apps/api
bash "$WORKTREE/spike_r2/sync.sh"
cd ~/lorenzo-r2/api
source spike_r2/env.sh
RUN="mise exec -- uv run python -m spike_r2"

want() { [[ "$STEPS" == "all" || " $STEPS " == *" $1 "* ]]; }

mkdir -p ~/lorenzo-r2/results

if want seed; then
  docker exec lorenzo-postgres-1 psql -U lorenzo -d postgres \
    -c 'DROP DATABASE IF EXISTS lorenzo_r2 WITH (FORCE)' -c 'CREATE DATABASE lorenzo_r2'
  mise exec -- uv run alembic upgrade head 2>&1 | tail -1
  $RUN.seed "$SIZE" 2>&1 | tee ~/lorenzo-r2/results/log_seed_$SIZE.txt
fi

if want timings; then
  $RUN.measure "$SIZE" 2>&1 | tee ~/lorenzo-r2/results/log_timings_$SIZE.txt
fi

PUBLIC_OPS="read_document_core read_document_bridge updates_shelf_core updates_stack_bridge \
copy_plan_core copy_plan_bridge browse_page_core browse_last_page_core load_upstream_core \
publish_build_core publish_build_bridge assess_core assess_bridge load_content_core \
load_content_bridge"
PRIVATE_OPS="updates_shelf_core updates_stack_bridge copy_plan_core copy_plan_bridge \
browse_page_core load_upstream_core"

if want mem; then
  for op in $PUBLIC_OPS; do
    $RUN.measure "$SIZE" --op "$op" --visibility public > /dev/null
    $RUN.measure "$SIZE" --op "$op" --visibility public --tracemalloc > /dev/null
  done
  for op in $PRIVATE_OPS; do
    $RUN.measure "$SIZE" --op "$op" --visibility private > /dev/null
    $RUN.measure "$SIZE" --op "$op" --visibility private --tracemalloc > /dev/null
  done
fi

if want profile; then
  for op in updates_shelf_core copy_plan_bridge read_document_core assess_core; do
    $RUN.measure "$SIZE" --profile "$op" --visibility public > /dev/null
  done
  $RUN.measure "$SIZE" --profile updates_shelf_core --visibility private > /dev/null
fi

mkdir -p "$WORKTREE/spike_r2/results"
cp -r ~/lorenzo-r2/results/. "$WORKTREE/spike_r2/results/"
cp -r ~/lorenzo-r2/state/. "$WORKTREE/spike_r2/results/" 2>/dev/null || true
echo "done: $SIZE ($STEPS)"
