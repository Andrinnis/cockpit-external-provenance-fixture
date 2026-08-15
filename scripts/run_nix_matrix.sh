#!/bin/sh
set -eu

export NIX_CONFIG="experimental-features = nix-command flakes
sandbox = true
warn-dirty = false
"

rm -rf evidence
mkdir -p evidence/raw evidence/drvs evidence/input-srcs evidence/outputs evidence/logs evidence/results

nix config show sandbox > evidence/sandbox-config.txt
nix --version > evidence/nix-version.txt

show_one() {
  attr="$1"
  drv="$(nix path-info --impure --derivation ".#$attr")"
  printf '%s\n' "$drv" > "evidence/results/$attr.drv-path"
  nix derivation show --recursive "$drv" > "evidence/raw/$attr.json"
}

build_one() {
  attr="$1"
  out="$(nix build --impure --option sandbox true --no-link --print-out-paths ".#$attr" 2> "evidence/logs/$attr.log")"
  printf '0\n' > "evidence/results/$attr.exit"
  printf '%s\n' "$out" > "evidence/results/$attr.out-path"
  cp "$out" "evidence/outputs/$attr"
  show_one "$attr"
}

for attr in neutral g pair oracle pair-shared oracle-shared; do
  build_one "$attr"
done

show_one pair-undeclared
set +e
nix build --impure --option sandbox true --no-link --print-out-paths ".#pair-undeclared" \
  > evidence/results/pair-undeclared.stdout \
  2> evidence/logs/pair-undeclared.log
undeclared_exit="$?"
set -e
printf '%s\n' "$undeclared_exit" > evidence/results/pair-undeclared.exit
if [ "$undeclared_exit" -eq 0 ]; then
  printf '%s\n' "undeclared input unexpectedly built" >&2
  exit 41
fi

grep -h -o '"/nix/store/[^" ]*\.drv"' evidence/raw/*.json \
  | tr -d '"' | sort -u > evidence/results/all-drv-paths.txt
while IFS= read -r drv; do
  cp "$drv" "evidence/drvs/$(basename "$drv")"
done < evidence/results/all-drv-paths.txt

grep -h -o '"/nix/store/[^" ]*"' evidence/raw/*.json \
  | tr -d '"' | sort -u > evidence/results/all-store-paths.txt
while IFS= read -r store_path; do
  case "$store_path" in
    *.drv) continue ;;
  esac
  if [ -f "$store_path" ]; then
    cp "$store_path" "evidence/input-srcs/$(basename "$store_path")"
  fi
done < evidence/results/all-store-paths.txt

