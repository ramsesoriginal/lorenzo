#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
for size in 1000 5000 20000; do bash "$DIR/gcexp.sh" "$size"; done
echo finished
