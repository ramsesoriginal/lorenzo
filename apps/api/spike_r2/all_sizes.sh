#!/bin/bash
# Every size, one after the other:  bash all_sizes.sh
DIR="$(cd "$(dirname "$0")" && pwd)"
for size in 1000 5000 20000; do
  bash "$DIR/run.sh" "$size" all > ~/lorenzo-r2/run_${size}.log 2>&1
done
echo finished
