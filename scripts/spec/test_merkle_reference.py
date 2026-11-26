"""Tests for the claim-list reference implementation (docs/spec/merkle.md)."""
import hashlib
import json
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import merkle_reference as m  # noqa: E402

DOMAIN = m.DOMAINS["weekly-drop"]
DIST = m.sha256(b"test-distribution")


def wallet(n):
    return m.sha256(b"test-wallet", n.to_bytes(4, "little"))


class LeafEncodingTest(unittest.TestCase):
    def test_leaf_matches_the_byte_layout_in_the_spec(self):
        tag = DOMAIN.encode()
        expected = hashlib.sha256(
            b"\x00" + bytes([len(tag)]) + tag + DIST + wallet(1)
            + (500).to_bytes(8, "little") + (7).to_bytes(4, "little")
        ).digest()
        self.assertEqual(m.leaf(DOMAIN, DIST, wallet(1), 500, 7), expected)

    def test_node_is_order_independent_and_prefixed(self):
        a, b = wallet(1), wallet(2)
        low, high = sorted([a, b])
        self.assertEqual(m.node(a, b), m.node(b, a))
        self.assertEqual(m.node(a, b), hashlib.sha256(b"\x01" + low + high).digest())

    def test_every_field_changes_the_leaf(self):
        base = m.leaf(DOMAIN, DIST, wallet(1), 500, 0)
        variants = [
            m.leaf(m.DOMAINS["guaranteed"], DIST, wallet(1), 500, 0),
            m.leaf(DOMAIN, m.sha256(b"other"), wallet(1), 500, 0),
            m.leaf(DOMAIN, DIST, wallet(2), 500, 0),
            m.leaf(DOMAIN, DIST, wallet(1), 501, 0),
            m.leaf(DOMAIN, DIST, wallet(1), 500, 1),
        ]
        self.assertEqual(len({base, *variants}), 6)

    def test_out_of_range_fields_rejected(self):
        for args in [(DOMAIN, DIST, wallet(1), 0, 0),
                     (DOMAIN, DIST, wallet(1), 2**64, 0),
                     (DOMAIN, DIST, wallet(1), 1, 2**32),
                     (DOMAIN, DIST, wallet(1), 1, -1),
                     ("", DIST, wallet(1), 1, 0),
                     ("x" * 256, DIST, wallet(1), 1, 0),
                     (DOMAIN.replace("/", "į"), DIST, wallet(1), 1, 0)]:
            with self.assertRaises(ValueError):
                m.leaf(*args)
        self.assertEqual(len(m.leaf("x" * 255, DIST, wallet(1), 1, 0)), 32)


class TreeTest(unittest.TestCase):
    def test_every_proof_verifies_for_many_sizes(self):
        rng = random.Random(1)
        for size in list(range(1, 40)) + [127, 128, 129, 1000]:
            entries = [(wallet(n), rng.randrange(1, 2**64), rng.randrange(2**32))
                       for n in range(size)]
            root, proofs = m.build(DOMAIN, DIST, entries)
            depth = math.ceil(math.log2(size)) if size > 1 else 0
            for w, a, i in entries:
                h = m.leaf(DOMAIN, DIST, w, a, i)
                self.assertTrue(m.verify(proofs[h], root, h))
                self.assertLessEqual(len(proofs[h]), depth)

    def test_root_does_not_depend_on_input_order(self):
        entries = [(wallet(n), n + 1, 0) for n in range(25)]
        root, _ = m.build(DOMAIN, DIST, entries)
        shuffled = entries[:]
        random.Random(2).shuffle(shuffled)
        self.assertEqual(m.build(DOMAIN, DIST, shuffled)[0], root)

    def test_tampered_proofs_fail(self):
        entries = [(wallet(n), n + 1, 0) for n in range(9)]
        root, proofs = m.build(DOMAIN, DIST, entries)
        h = m.leaf(DOMAIN, DIST, wallet(0), 1, 0)
        proof = proofs[h]
        for k in range(len(proof)):
            bad = proof[:k] + [bytes(32)] + proof[k + 1:]
            self.assertFalse(m.verify(bad, root, h))
        self.assertFalse(m.verify(proof[:-1], root, h))
        self.assertFalse(m.verify(proof + [bytes(32)], root, h))

    def test_one_entry_root_is_its_leaf(self):
        root, proofs = m.build(DOMAIN, DIST, [(wallet(1), 5, 0)])
        self.assertEqual(root, m.leaf(DOMAIN, DIST, wallet(1), 5, 0))
        self.assertEqual(proofs[root], [])

    def test_invalid_lists_rejected(self):
        with self.assertRaises(ValueError):
            m.build(DOMAIN, DIST, [])
        with self.assertRaises(ValueError):
            m.build(DOMAIN, DIST, [(wallet(1), 5, 0), (wallet(1), 6, 0)])
        with self.assertRaises(ValueError):
            m.build(DOMAIN, DIST, [(wallet(1), 0, 0)])
        # The same wallet with different indexes (tranche releases) is fine.
        m.build(DOMAIN, DIST, [(wallet(1), 5, 0), (wallet(1), 5, 1)])

    def test_proof_length_limit(self):
        h = m.leaf(DOMAIN, DIST, wallet(1), 5, 0)
        siblings = [wallet(n) for n in range(m.MAX_PROOF_LEN + 1)]
        full, long = siblings[:m.MAX_PROOF_LEN], siblings
        self.assertTrue(m.verify(full, m.fold(full, h), h))
        # Would verify if the length were not checked.
        self.assertFalse(m.verify(long, m.fold(long, h), h))


class VectorsTest(unittest.TestCase):
    def setUp(self):
        with open(m.VECTORS_PATH, encoding="utf-8") as handle:
            self.vectors = json.load(handle)

    def test_length_limit_vectors(self):
        ok = self.vectors["at_limit"]
        bad = self.vectors["over_limit"]
        self.assertIn(bad, self.vectors["must_fail"])
        self.assertEqual(len(ok["proof"]), m.MAX_PROOF_LEN)
        self.assertEqual(len(bad["proof"]), m.MAX_PROOF_LEN + 1)
        for v in (ok, bad):
            proof = [bytes.fromhex(p) for p in v["proof"]]
            self.assertEqual(m.fold(proof, bytes.fromhex(v["leaf"])).hex(), v["root"])
        self.assertTrue(m.verify([bytes.fromhex(p) for p in ok["proof"]],
                                 bytes.fromhex(ok["root"]), bytes.fromhex(ok["leaf"])))
        self.assertFalse(m.verify([bytes.fromhex(p) for p in bad["proof"]],
                                  bytes.fromhex(bad["root"]), bytes.fromhex(bad["leaf"])))

    def test_committed_vectors_are_current(self):
        with open(m.VECTORS_PATH, encoding="utf-8", newline="") as handle:
            self.assertEqual(handle.read(), m.render())

    def test_every_vector_proof_verifies(self):
        for case in self.vectors["cases"]:
            root = bytes.fromhex(case["root"])
            for entry in case["entries"]:
                expected = m.leaf(case["domain"], m.pubkey(case["distribution"]),
                                  m.pubkey(entry["wallet"]), int(entry["amount"]),
                                  entry["index"])
                self.assertEqual(entry["leaf"], expected.hex())
                proof = [bytes.fromhex(p) for p in entry["proof"]]
                self.assertTrue(m.verify(proof, root, expected), case["name"])

    def test_every_must_fail_vector_fails(self):
        self.assertGreaterEqual(len(self.vectors["must_fail"]), 6)
        for bad in self.vectors["must_fail"]:
            proof = [bytes.fromhex(p) for p in bad["proof"]]
            self.assertFalse(
                m.verify(proof, bytes.fromhex(bad["root"]), bytes.fromhex(bad["leaf"])),
                bad["why"],
            )

    def test_base58_round_trip(self):
        for case in self.vectors["cases"]:
            key = case["distribution"]
            self.assertEqual(m.b58encode(m.pubkey(key)), key)


if __name__ == "__main__":
    unittest.main()
