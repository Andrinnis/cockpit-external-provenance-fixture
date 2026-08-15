#!/bin/sh
set -eu

export NIX_CONFIG="experimental-features = nix-command flakes
sandbox = true
warn-dirty = false
"

rm -rf evidence
mkdir -p evidence/raw evidence/drvs evidence/input-srcs evidence/outputs evidence/logs evidence/results

nix_installer_sha256="3b49a0b91820accb76e3d9ff7ed64fc430121b9fafb3869b0d549721fbeb4c85"
if [ ! -f "${NIX_INSTALLER:-}" ]; then
  printf '%s\n' "missing exact Nix installer input" >&2
  exit 40
fi
actual_nix_installer_sha256="$(sha256sum "$NIX_INSTALLER" | awk '{print $1}')"
if [ "$actual_nix_installer_sha256" != "$nix_installer_sha256" ] || [ "${NIX_INSTALLER_SHA256:-}" != "$nix_installer_sha256" ]; then
  printf '%s\n' "Nix installer SHA-256 mismatch" >&2
  exit 41
fi
printf '%s  %s\n' "$actual_nix_installer_sha256" "$(basename "$NIX_INSTALLER")" > evidence/results/nix-installer.sha256

if ! printf '%s\n' "${FIXTURE_SOURCE_COMMIT:-}" | grep -Eq '^[0-9a-f]{40}$'; then
  printf '%s\n' "missing exact Git source commit" >&2
  exit 44
fi
printf '%s\n' "$FIXTURE_SOURCE_COMMIT" > evidence/results/source-commit.txt

fixture_busybox="/nix/store/yysvxw5iwwijaci7ggrnms4mavwcjnpk-busybox-1.37.0/bin/busybox"
fixture_busybox_sha256="8ec12605eb7c1c550189c0b7a25fd4f77bd1cd34e846b444e2579c6de49d3ff9"
if [ ! -f "$fixture_busybox" ]; then
  printf '%s\n' "missing exact fixture BusyBox: $fixture_busybox" >&2
  exit 45
fi
actual_busybox_sha256="$(sha256sum "$fixture_busybox" | awk '{print $1}')"
if [ "$actual_busybox_sha256" != "$fixture_busybox_sha256" ]; then
  printf '%s\n' "fixture BusyBox SHA-256 mismatch" >&2
  exit 46
fi
printf '%s  %s\n' "$actual_busybox_sha256" "$fixture_busybox" > evidence/results/fixture-busybox.sha256

nix config show sandbox > evidence/sandbox-config.txt
nix config show sandbox-fallback > evidence/sandbox-fallback-config.txt
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
