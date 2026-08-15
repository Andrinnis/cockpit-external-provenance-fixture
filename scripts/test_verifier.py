#!/usr/bin/env python3
import copy
import unittest

from verify_matrix import (
    HOLD_ANCESTRY_INCOMPLETE,
    HOLD_COMMON_GENERATOR,
    VERIFIABLE_PASS,
    canonical_nodes,
    closure,
    decide,
)


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.nodes = canonical_nodes({
            "/nix/store/neutral.drv": {"inputDrvs": {}, "inputSrcs": ["/nix/store/builder"]},
            "/nix/store/pair.drv": {"inputDrvs": {}, "inputSrcs": ["/nix/store/builder"]},
            "/nix/store/oracle.drv": {"inputDrvs": {}, "inputSrcs": ["/nix/store/builder"]},
        })
        self.neutral = closure(self.nodes, "/nix/store/neutral.drv")

    def test_positive(self):
        self.assertEqual(
            decide(self.nodes, copy.deepcopy(self.nodes), "/nix/store/pair.drv", "/nix/store/oracle.drv", self.neutral)[0],
            VERIFIABLE_PASS,
        )

    def test_shared_generator(self):
        nodes = copy.deepcopy(self.nodes)
        nodes["/nix/store/g.drv"] = {"inputDrvs": [], "inputSrcs": ["/nix/store/builder"]}
        nodes["/nix/store/pair.drv"]["inputDrvs"] = ["/nix/store/g.drv"]
        nodes["/nix/store/oracle.drv"]["inputDrvs"] = ["/nix/store/g.drv"]
        self.assertEqual(
            decide(nodes, copy.deepcopy(nodes), "/nix/store/pair.drv", "/nix/store/oracle.drv", self.neutral)[0],
            HOLD_COMMON_GENERATOR,
        )

    def test_omitted_edge(self):
        submitted = copy.deepcopy(self.nodes)
        submitted["/nix/store/pair.drv"]["inputSrcs"] = []
        self.assertEqual(
            decide(self.nodes, submitted, "/nix/store/pair.drv", "/nix/store/oracle.drv", self.neutral)[0],
            HOLD_ANCESTRY_INCOMPLETE,
        )


if __name__ == "__main__":
    unittest.main()

