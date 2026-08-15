#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
import tarfile
from pathlib import Path


HOLD_ANCESTRY_INCOMPLETE = "HOLD_ANCESTRY_INCOMPLETE"
HOLD_COMMON_GENERATOR = "HOLD_COMMON_GENERATOR"
HOLD_UNDECLARED_INPUT = "HOLD_UNDECLARED_INPUT"
VERIFIABLE_PASS = "VERIFIABLE_PASS"


def canonical_nodes(raw: dict) -> dict[str, dict[str, list[str]]]:
    nodes = {}
    for drv, body in raw.items():
        nodes[drv] = {
            "inputDrvs": sorted(body.get("inputDrvs", {}).keys()),
            "inputSrcs": sorted(body.get("inputSrcs", [])),
        }
    return dict(sorted(nodes.items()))


def closure(nodes: dict[str, dict[str, list[str]]], root: str) -> set[str]:
    seen: set[str] = set()
    pending = [root]
    while pending:
        drv = pending.pop()
        if drv in seen:
            continue
        if drv not in nodes:
            raise ValueError(f"missing derivation node: {drv}")
        seen.add(drv)
        seen.update(nodes[drv]["inputSrcs"])
        pending.extend(nodes[drv]["inputDrvs"])
    return seen


def decide(
    observed: dict[str, dict[str, list[str]]],
    submitted: dict[str, dict[str, list[str]]],
    pair_root: str,
    oracle_root: str,
    neutral: set[str],
) -> tuple[str, list[str]]:
    if observed != submitted:
        return HOLD_ANCESTRY_INCOMPLETE, []
    common = sorted((closure(observed, pair_root) & closure(observed, oracle_root)) - neutral)
    if common:
        return HOLD_COMMON_GENERATOR, common
    return VERIFIABLE_PASS, []


def load_raw(base: Path, attr: str) -> dict:
    return json.loads((base / "raw" / f"{attr}.json").read_text())


def root_for(base: Path, attr: str) -> str:
    return (base / "results" / f"{attr}.drv-path").read_text().strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deterministic_tar(base: Path, destination: Path) -> None:
    with tarfile.open(destination, "w", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(p for p in base.rglob("*") if p.is_file() and p != destination):
            relative = path.relative_to(base)
            info = archive.gettarinfo(str(path), arcname=str(relative))
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            with path.open("rb") as handle:
                archive.addfile(info, handle)


def main() -> int:
    base = Path(sys.argv[1] if len(sys.argv) > 1 else "evidence")
    if (base / "sandbox-config.txt").read_text().strip().split()[-1].lower() not in {"true", "relaxed"}:
        raise SystemExit("sandbox was not enabled")

    neutral_nodes = canonical_nodes(load_raw(base, "neutral"))
    neutral_set = closure(neutral_nodes, root_for(base, "neutral"))

    positive_observed = canonical_nodes({
        **load_raw(base, "pair"),
        **load_raw(base, "oracle"),
    })
    positive_submitted = json.loads(json.dumps(positive_observed))
    positive = decide(
        positive_observed,
        positive_submitted,
        root_for(base, "pair"),
        root_for(base, "oracle"),
        neutral_set,
    )

    shared_observed = canonical_nodes({
        **load_raw(base, "pair-shared"),
        **load_raw(base, "oracle-shared"),
    })
    shared_submitted = json.loads(json.dumps(shared_observed))
    shared = decide(
        shared_observed,
        shared_submitted,
        root_for(base, "pair-shared"),
        root_for(base, "oracle-shared"),
        neutral_set,
    )

    g_root = root_for(base, "g")
    omitted_submitted = json.loads(json.dumps(shared_observed))
    pair_shared_root = root_for(base, "pair-shared")
    omitted_submitted[pair_shared_root]["inputDrvs"].remove(g_root)
    omitted = decide(
        shared_observed,
        omitted_submitted,
        pair_shared_root,
        root_for(base, "oracle-shared"),
        neutral_set,
    )

    undeclared_nodes = canonical_nodes(load_raw(base, "pair-undeclared"))
    undeclared_root = root_for(base, "pair-undeclared")
    undeclared_exit = int((base / "results" / "pair-undeclared.exit").read_text())
    undeclared_has_g = g_root in undeclared_nodes[undeclared_root]["inputDrvs"]
    undeclared = HOLD_UNDECLARED_INPUT if undeclared_exit != 0 and not undeclared_has_g else "UNEXPECTED_UNDECLARED_RESULT"

    submitted_dir = base / "submitted"
    submitted_dir.mkdir(exist_ok=True)
    for name, graph in {
        "positive": positive_submitted,
        "shared": shared_submitted,
        "omitted": omitted_submitted,
    }.items():
        (submitted_dir / f"{name}.json").write_text(json.dumps(graph, sort_keys=True, separators=(",", ":")) + "\n")

    verdicts = {
        "positive": {"verdict": positive[0], "unexpected_common": positive[1]},
        "shared": {"verdict": shared[0], "common": shared[1]},
        "omitted": {"verdict": omitted[0]},
        "undeclared": {"verdict": undeclared, "build_exit": undeclared_exit, "declared_g": undeclared_has_g},
    }
    expected = {
        "positive": VERIFIABLE_PASS,
        "shared": HOLD_COMMON_GENERATOR,
        "omitted": HOLD_ANCESTRY_INCOMPLETE,
        "undeclared": HOLD_UNDECLARED_INPUT,
    }
    if {key: value["verdict"] for key, value in verdicts.items()} != expected:
        raise SystemExit(json.dumps(verdicts, sort_keys=True))

    files = {}
    for path in sorted(p for p in base.rglob("*") if p.is_file() and p.name not in {"manifest.json", "evidence-bundle.tar"}):
        files[str(path.relative_to(base))] = sha256(path)
    manifest = {
        "schema": "cockpit.external-provenance-fixture.v1",
        "provider": os.environ.get("FIXTURE_PROVIDER", "local-untrusted-preflight"),
        "verdicts": verdicts,
        "files": files,
    }
    (base / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    deterministic_tar(base, base / "evidence-bundle.tar")
    print(json.dumps({"bundle_sha256": sha256(base / "evidence-bundle.tar"), "verdicts": verdicts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

