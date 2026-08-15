{
  description = "Public synthetic closed-ancestry provenance discriminator";

  inputs = { };

  outputs = { self }:
    let
      system = "x86_64-linux";
      busybox = builtins.path {
        path = /bin/busybox;
        name = "fixture-busybox";
      };
      builderScript = builtins.toFile "fixture-builder.sh" ''
        set -eu
        case "$mode" in
          plain)
            printf '%s\n' "$payload" > "$out"
            ;;
          with-g)
            IFS= read -r generator_payload < "$g"
            printf '%s|%s\n' "$payload" "$generator_payload" > "$out"
            ;;
          undeclared)
            IFS= read -r generator_payload < "$undeclared_g"
            printf '%s|%s\n' "$payload" "$generator_payload" > "$out"
            ;;
          *)
            exit 97
            ;;
        esac
      '';
      mk = name: mode: extra:
        builtins.derivation ({
          inherit name system mode;
          builder = busybox;
          args = [ "sh" builderScript ];
          payload = name;
        } // extra);
      neutral = mk "neutral-toolchain" "plain" { };
      g = mk "fixture-g" "plain" { };
      pair = mk "fixture-pair" "plain" { };
      oracle = mk "fixture-oracle" "plain" { };
      pairShared = mk "fixture-pair-shared" "with-g" { inherit g; };
      oracleShared = mk "fixture-oracle-shared" "with-g" { inherit g; };
      undeclaredG = builtins.unsafeDiscardStringContext "${g}";
      pairUndeclared = mk "fixture-pair-undeclared" "undeclared" {
        undeclared_g = undeclaredG;
      };
    in {
      packages.${system} = {
        inherit neutral g pair oracle;
        "pair-shared" = pairShared;
        "oracle-shared" = oracleShared;
        "pair-undeclared" = pairUndeclared;
        default = pair;
      };
    };
}

