#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 2 || ! $1 =~ ^-?[0-9]+$ || ! $2 =~ ^-?[0-9]+$ ]]; then
  echo "Usage: $0 <integer1> <integer2>" >&2
  exit 1
fi

echo $(( $1 + $2 ))
