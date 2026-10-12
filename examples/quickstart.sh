#!/bin/sh
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
temp_root=$(mktemp -d "${TMPDIR:-/tmp}/orqivra-quickstart.XXXXXXXX")
project_root="$temp_root/project"
mkdir "$project_root"
dag_path="$repo_dir/examples/solo-change.json"
state_path="$temp_root/state.json"

orqivra validate dag "$dag_path"
orqivra state init "$dag_path" --state "$state_path" --project-root "$project_root"
orqivra report --state "$state_path"
printf 'Disposable quickstart directory: %s\n' "$temp_root"
