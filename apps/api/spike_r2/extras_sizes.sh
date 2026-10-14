#!/bin/bash
# Reseed and re-measure the smaller sizes, then run their extras (the 20,000 extras ran on the
# state run.sh left): bash extras_sizes.sh
DIR="$(cd "$(dirname "$0")" && pwd)"
for size in 5000 1000; do
  bash "$DIR/run.sh" "$size" "seed timings" > ~/lorenzo-r2/run_${size}_again.log 2>&1
  bash "$DIR/extras.sh" "$size" > /dev/null 2>&1
done
echo finished
