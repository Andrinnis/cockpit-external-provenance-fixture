# External Provenance Experiment V1

STATUS | PUBLIC SYNTHETIC FIXTURE / NOT COCKPIT PRODUCT CODE

This repository-sized fixture tests whether two externally executed builds can
prove that `pair` and `oracle` do not share an undeclared or omitted generator.
It contains no Cockpit source, project controls, credentials or personal data.

The GitHub lane installs the official NixOS `2.35.1` installer directly on the
hosted runner after verifying its literal SHA-256. The Nix derivations use the
exact BusyBox executable embedded in that pinned Nix closure as an explicit
`inputSrc`; the fixture verifies its store path and SHA-256 before evaluation.
There are no flake inputs and no fixed-output derivations. The neutral
derivation closes the exact shared builder/script set. `g` is an ordinary
derivation and therefore becomes a literal `inputDrvs` edge when it is supplied
to both subjects.

The matrix is:

- `positive`: pair/oracle closures intersect only in the neutral allowlist;
- `shared`: both roots consume `g` and return `HOLD_COMMON_GENERATOR`;
- `omitted`: one literal root-to-`g` edge is removed only from the submitted
  graph and returns `HOLD_ANCESTRY_INCOMPLETE` against provider-built `.drv`;
- `undeclared`: the derivation contains only a context-free spelling of the
  `g` store path and must fail to read it in the Linux Nix sandbox.

`scripts/run_nix_matrix.sh` builds and exports raw derivation JSON, exact `.drv`
bytes, explicit input-source bytes, outputs, logs and sandbox configuration.
`scripts/verify_matrix.py` independently reconstructs the graph, executes the
typed checks and creates deterministic `evidence-bundle.tar`.

The GitHub workflow runs Nix directly on the hosted runner and signs the
evidence bundle with GitHub artifact attestation. `cloudbuild.yaml` remains a
separate later lane that places the same bundle in an Artifact Registry image
and requests verified Cloud Build provenance; it is not run before a clean
GitHub artifact/attestation. Provider attestations are evidence inputs for the
later exact-byte evaluator; they are not H0 admission by themselves.
