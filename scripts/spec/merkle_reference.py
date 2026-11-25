#!/usr/bin/env python3
"""Reference implementation of the claim-list format in docs/spec/merkle.md.

Deliberately simple and independent of the Rust and TypeScript code, so the
three can be checked against each other. Also generates the shared test
vectors.

Usage:
  merkle_reference.py generate   write docs/spec/merkle-vectors.json
  merkle_reference.py check      fail if the committed vectors are stale
"""
import hashlib
import json
import os
import sys

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"
MAX_PROOF_LEN = 24

DOMAINS = {
    "guaranteed": "percolator-dao-launch/guaranteed/v1",
    "legacy-tranche": "percolator-dao-launch/legacy-tranche/v1",
    "weekly-drop": "percolator-dao-launch/weekly-drop/v1",
}

VECTORS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "spec", "merkle-vectors.json"
)

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = B58[r] + out
    return "1" * (len(data) - len(data.lstrip(b"\0"))) + out


def b58decode(text: str) -> bytes:
    n = 0
    for char in text:
        n = n * 58 + B58.index(char)
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\0" * (len(text) - len(text.lstrip("1"))) + body


def pubkey(text: str) -> bytes:
    raw = b58decode(text)
    if len(raw) != 32:
        raise ValueError(f"not a 32-byte public key: {text}")
    return raw


def sha256(*parts: bytes) -> bytes:
    h = hashlib.sha256()
    for part in parts:
        h.update(part)
    return h.digest()


def leaf(domain: str, distribution: bytes, wallet: bytes, amount: int, index: int) -> bytes:
    tag = domain.encode("ascii")
    if not 0 < len(tag) < 256:
        raise ValueError("domain must be 1-255 ASCII bytes")
    if not 0 < amount < 2**64:
        raise ValueError("amount must be a non-zero u64")
    if not 0 <= index < 2**32:
        raise ValueError("index must be a u32")
    return sha256(
        LEAF_PREFIX,
        bytes([len(tag)]),
        tag,
        distribution,
        wallet,
        amount.to_bytes(8, "little"),
        index.to_bytes(4, "little"),
    )


def node(a: bytes, b: bytes) -> bytes:
    low, high = (a, b) if a <= b else (b, a)
    return sha256(NODE_PREFIX, low, high)


def build(domain: str, distribution: bytes, entries):
    """Returns (root, {leaf: proof}) for entries of (wallet, amount, index)."""
    if not entries:
        raise ValueError("a list must have at least one entry")
    seen = set()
    for wallet, _, index in entries:
        if (wallet, index) in seen:
            raise ValueError("duplicate (wallet, index) entry")
        seen.add((wallet, index))
    leaves = sorted(leaf(domain, distribution, w, a, i) for w, a, i in entries)
    proofs = {h: [] for h in leaves}
    members = {h: [h] for h in leaves}  # leaves under each current node
    level = leaves
    while len(level) > 1:
        above = []
        for i in range(0, len(level) - 1, 2):
            left, right = level[i], level[i + 1]
            for h in members[left]:
                proofs[h].append(right)
            for h in members[right]:
                proofs[h].append(left)
            parent = node(left, right)
            members[parent] = members.pop(left) + members.pop(right)
            above.append(parent)
        if len(level) % 2:
            above.append(level[-1])  # odd one out moves up unchanged
        level = above
    return level[0], proofs


def fold(proof, candidate: bytes) -> bytes:
    """The root `proof` leads to from `candidate`, ignoring the length limit."""
    h = candidate
    for sibling in proof:
        h = node(h, sibling)
    return h


def verify(proof, root: bytes, candidate: bytes) -> bool:
    if len(proof) > MAX_PROOF_LEN:
        return False
    h = candidate
    for sibling in proof:
        h = node(h, sibling)
    return h == root


def fake_key(label: str) -> str:
    """Deterministic stand-in public keys for the vectors."""
    return b58encode(sha256(b"merkle-vector-key:", label.encode()))


def case(name, kind, distribution_label, entries):
    domain = DOMAINS[kind]
    distribution = fake_key(distribution_label)
    rows = [(fake_key(w), a, i) for w, a, i in entries]
    raw = [(pubkey(w), a, i) for w, a, i in rows]
    root, proofs = build(domain, pubkey(distribution), raw)
    out = []
    for (w, a, i), (rw, _, _) in zip(rows, raw):
        h = leaf(domain, pubkey(distribution), rw, a, i)
        out.append({
            "wallet": w,
            "amount": str(a),
            "index": i,
            "leaf": h.hex(),
            "proof": [p.hex() for p in proofs[h]],
        })
    return {
        "name": name,
        "domain": domain,
        "distribution": distribution,
        "root": root.hex(),
        "entries": out,
    }


def vectors():
    six = [(f"wallet-{n}", (n + 1) * 1_000_000_000, 0) for n in range(6)]
    cases = [
        case("one entry", "guaranteed", "raise-a", [("wallet-0", 500_000_000, 0)]),
        case("two entries", "guaranteed", "raise-a",
             [("wallet-0", 500_000_000, 0), ("wallet-1", 120_000_000, 0)]),
        case("three entries (odd level)", "weekly-drop", "week-1",
             [("wallet-0", 1, 0), ("wallet-1", 2, 0), ("wallet-2", 3, 0)]),
        case("six entries", "weekly-drop", "week-2", six),
        case("tranche releases for one wallet", "legacy-tranche", "raise-a",
             [("wallet-0", 100_000_000, 0), ("wallet-0", 100_000_000, 1),
              ("wallet-0", 100_000_000, 2), ("wallet-1", 50_000_000, 0)]),
        case("largest amount and index", "legacy-tranche", "raise-a",
             [("wallet-0", 2**64 - 1, 2**32 - 1), ("wallet-1", 1, 0)]),
    ]

    # Cases that must fail verification against the "six entries" root.
    base = cases[3]
    domain, distribution = base["domain"], pubkey(base["distribution"])
    root = bytes.fromhex(base["root"])
    first = base["entries"][0]
    wallet = pubkey(first["wallet"])
    proof = [bytes.fromhex(p) for p in first["proof"]]
    other_case = cases[2]
    # Proofs of exactly the limit and one step over it, each with the root it
    # leads to, so only the length check can reject the longer one.
    pad = [sha256(b"merkle-vector-pad:", bytes([n])) for n in range(MAX_PROOF_LEN + 1)]
    long_proof = (proof + pad)[:MAX_PROOF_LEN + 1]
    full_proof = long_proof[:MAX_PROOF_LEN]
    at_limit = {"why": "proof of exactly the maximum",
                "leaf": first["leaf"], "proof": [p.hex() for p in full_proof],
                "root": fold(full_proof, bytes.fromhex(first["leaf"])).hex()}
    assert verify(full_proof, bytes.fromhex(at_limit["root"]), bytes.fromhex(first["leaf"]))
    over_limit = {"why": "proof longer than the maximum",
                  "leaf": first["leaf"], "proof": [p.hex() for p in long_proof],
                  "root": fold(long_proof, bytes.fromhex(first["leaf"])).hex()}
    must_fail = [
        {"why": "amount changed",
         "leaf": leaf(domain, distribution, wallet, int(first["amount"]) + 1, 0).hex(),
         "proof": first["proof"], "root": base["root"]},
        {"why": "index changed",
         "leaf": leaf(domain, distribution, wallet, int(first["amount"]), 1).hex(),
         "proof": first["proof"], "root": base["root"]},
        {"why": "same entry under another domain",
         "leaf": leaf(DOMAINS["guaranteed"], distribution, wallet, int(first["amount"]), 0).hex(),
         "proof": first["proof"], "root": base["root"]},
        {"why": "same entry under another distribution",
         "leaf": leaf(domain, pubkey(other_case["distribution"]), wallet,
                      int(first["amount"]), 0).hex(),
         "proof": first["proof"], "root": base["root"]},
        {"why": "proof from another list",
         "leaf": first["leaf"], "proof": other_case["entries"][0]["proof"],
         "root": base["root"]},
        over_limit,
    ]
    for bad in must_fail:
        assert not verify([bytes.fromhex(p) for p in bad["proof"]],
                          bytes.fromhex(bad["root"]), bytes.fromhex(bad["leaf"])), bad["why"]
    return {
        "spec": "docs/spec/merkle.md",
        "hash": "sha256",
        "leaf_prefix": "00",
        "node_prefix": "01",
        "max_proof_len": MAX_PROOF_LEN,
        "domains": DOMAINS,
        "cases": cases,
        "must_fail": must_fail,
        "at_limit": at_limit,
        "over_limit": over_limit,
    }


def render() -> str:
    return json.dumps(vectors(), indent=2) + "\n"


def main(argv):
    mode = argv[1] if len(argv) == 2 else ""
    if mode == "generate":
        with open(VECTORS_PATH, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(render())
        print(f"wrote {os.path.normpath(VECTORS_PATH)}")
        return 0
    if mode == "check":
        with open(VECTORS_PATH, encoding="utf-8", newline="") as handle:
            if handle.read() != render():
                print("merkle vectors are stale: run `merkle_reference.py generate`",
                      file=sys.stderr)
                return 1
        print("merkle vectors up to date")
        return 0
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
