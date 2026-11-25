//! Claim-list (merkle) verification, exactly as specified in
//! `docs/spec/merkle.md`. Programs call [`verify_claim`], which recomputes
//! the leaf from the claim's own fields (never accept a leaf hash from the
//! caller) and returns an error to propagate with `?` when the check fails.

/// Prefix byte for leaf hashes.
pub const LEAF_PREFIX: u8 = 0x00;
/// Prefix byte for internal node hashes.
pub const NODE_PREFIX: u8 = 0x01;
/// Longest proof accepted (enough for 2^24 entries).
pub const MAX_PROOF_LEN: usize = 24;

/// What a list is for. Each kind has its own domain label, so an entry from
/// one kind of list is never accepted by another.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Domain {
    /// Raise program: guaranteed deposit amounts. `distribution` is the
    /// Raise account; `index` is always 0.
    Guaranteed,
    /// Claims program: legacy tranche releases. `distribution` is the Raise
    /// account; `index` is the release number.
    LegacyTranche,
    /// Claims program: weekly drops. `distribution` is that week's
    /// distributor account; `index` is always 0.
    WeeklyDrop,
}

const GUARANTEED: &[u8] = b"percolator-dao-launch/guaranteed/v1";
const LEGACY_TRANCHE: &[u8] = b"percolator-dao-launch/legacy-tranche/v1";
const WEEKLY_DROP: &[u8] = b"percolator-dao-launch/weekly-drop/v1";

/// Length byte for a domain label, checked at compile time.
#[allow(clippy::cast_possible_truncation)] // guarded by the assert: 0 < len < 256
const fn len_byte(tag: &[u8]) -> u8 {
    assert!(!tag.is_empty() && tag.len() < 256);
    tag.len() as u8
}

const GUARANTEED_LEN: u8 = len_byte(GUARANTEED);
const LEGACY_TRANCHE_LEN: u8 = len_byte(LEGACY_TRANCHE);
const WEEKLY_DROP_LEN: u8 = len_byte(WEEKLY_DROP);

impl Domain {
    /// The ASCII domain label hashed into every leaf.
    #[must_use]
    pub const fn tag(self) -> &'static [u8] {
        match self {
            Domain::Guaranteed => GUARANTEED,
            Domain::LegacyTranche => LEGACY_TRANCHE,
            Domain::WeeklyDrop => WEEKLY_DROP,
        }
    }

    const fn tag_len(self) -> u8 {
        match self {
            Domain::Guaranteed => GUARANTEED_LEN,
            Domain::LegacyTranche => LEGACY_TRANCHE_LEN,
            Domain::WeeklyDrop => WEEKLY_DROP_LEN,
        }
    }
}

/// The leaf hash of one entry.
#[must_use = "this only computes the leaf hash; it checks nothing"]
pub fn leaf(
    domain: Domain,
    distribution: &[u8; 32],
    wallet: &[u8; 32],
    amount: u64,
    index: u32,
) -> [u8; 32] {
    leaf_hash(domain, distribution, wallet, amount, index)
}

#[cfg(not(kani))]
fn leaf_hash(
    domain: Domain,
    distribution: &[u8; 32],
    wallet: &[u8; 32],
    amount: u64,
    index: u32,
) -> [u8; 32] {
    solana_program::hash::hashv(&[
        &[LEAF_PREFIX],
        &[domain.tag_len()],
        domain.tag(),
        distribution,
        wallet,
        &amount.to_le_bytes(),
        &index.to_le_bytes(),
    ])
    .to_bytes()
}

/// Combines two hashes. Order-independent: the smaller hash goes first.
#[must_use = "this only computes the combined hash; it checks nothing"]
pub fn node(a: &[u8; 32], b: &[u8; 32]) -> [u8; 32] {
    let (low, high) = if a <= b { (a, b) } else { (b, a) };
    node_hash(low, high)
}

#[cfg(not(kani))]
fn node_hash(low: &[u8; 32], high: &[u8; 32]) -> [u8; 32] {
    solana_program::hash::hashv(&[&[NODE_PREFIX], low, high]).to_bytes()
}

// Kani cannot reason about SHA-256, so proofs use these cheap fixed-size
// stand-ins. They are deterministic and depend on every input field, and the
// node stand-in depends on argument order, so the proofs about the
// surrounding logic stay meaningful. Never compiled into real builds.
//
// cargo-mutants ignores `cfg`, so mutants in Kani-only code, which tests
// never compile, would all count as missed. Every `#[cfg(kani)]` item is
// therefore followed by `#[cfg_attr(test, mutants::skip)]`, and CI checks
// that pairing. There is no `mutants` crate, so the line breaks the test
// build if copied onto real code (and `cargo kani --tests`, which is unused).

#[cfg(kani)]
#[cfg_attr(test, mutants::skip)]
fn leaf_hash(
    domain: Domain,
    distribution: &[u8; 32],
    wallet: &[u8; 32],
    amount: u64,
    index: u32,
) -> [u8; 32] {
    let amount = amount.to_le_bytes();
    let index = index.to_le_bytes();
    let tag = domain.tag_len();
    core::array::from_fn(|i| {
        distribution[i] ^ wallet[i].rotate_left(1) ^ amount[i & 7] ^ index[i & 3] ^ tag
    })
}

#[cfg(kani)]
#[cfg_attr(test, mutants::skip)]
fn node_hash(low: &[u8; 32], high: &[u8; 32]) -> [u8; 32] {
    core::array::from_fn(|i| low[i] ^ high[i].rotate_left(1) ^ NODE_PREFIX)
}

/// Why a claim was refused.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ClaimError {
    /// The proof is longer than [`MAX_PROOF_LEN`].
    ProofTooLong,
    /// The entry is not on the list with this root.
    NotOnList,
}

/// Whether `proof` leads from `leaf` to `root`, for this module's tests and
/// proofs. Private: programs must use [`verify_claim`], so the leaf is always
/// recomputed from the claim's fields, never taken from the caller.
#[must_use = "the proof is valid only if this returns true"]
fn verify_proof(proof: &[[u8; 32]], root: &[u8; 32], leaf: [u8; 32]) -> bool {
    if proof.len() > MAX_PROOF_LEN {
        return false;
    }
    let mut hash = leaf;
    for sibling in proof {
        hash = node(&hash, sibling);
    }
    hash == *root
}

/// Checks that the entry (`wallet` is owed `amount` for release `index`) is
/// on the list with `root`. `distribution` must come from the account being
/// claimed against and `wallet` from the signer.
///
/// Returns an error rather than a bool, so the natural call is
/// `verify_claim(..)?`, which stops the instruction when the check fails and
/// leaves no `if` to get the wrong way round. Ignoring the result fails to
/// build (and `let _ = ...` fails clippy). One escape remains on Rust 1.78:
/// `verify_claim(..).ok()` stored in a variable that is never read. Reject
/// it in review.
///
/// ```compile_fail
/// #![deny(unused_must_use)]
/// use dao_common::merkle::{verify_claim, Domain};
/// verify_claim(Domain::WeeklyDrop, &[1; 32], &[2; 32], 1_000, 0, &[], &[3; 32]);
/// ```
///
/// ```
/// #![deny(unused_must_use)]
/// use dao_common::merkle::{verify_claim, ClaimError, Domain};
/// fn claim() -> Result<(), ClaimError> {
///     verify_claim(Domain::WeeklyDrop, &[1; 32], &[2; 32], 1_000, 0, &[], &[3; 32])?;
///     // ...pay the claim
///     Ok(())
/// }
/// assert_eq!(claim(), Err(ClaimError::NotOnList));
/// ```
pub fn verify_claim(
    domain: Domain,
    distribution: &[u8; 32],
    wallet: &[u8; 32],
    amount: u64,
    index: u32,
    proof: &[[u8; 32]],
    root: &[u8; 32],
) -> Result<(), ClaimError> {
    if proof.len() > MAX_PROOF_LEN {
        return Err(ClaimError::ProofTooLong);
    }
    if verify_proof(
        proof,
        root,
        leaf(domain, distribution, wallet, amount, index),
    ) {
        Ok(())
    } else {
        Err(ClaimError::NotOnList)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;
    use solana_program::pubkey::Pubkey;
    use std::str::FromStr;

    const VECTORS: &str = include_str!("../../../docs/spec/merkle-vectors.json");

    fn vectors() -> Value {
        serde_json::from_str(VECTORS).expect("vectors are valid JSON")
    }

    fn hex32(text: &str) -> [u8; 32] {
        assert_eq!(text.len(), 64, "a 32-byte hash is 64 hex characters");
        let mut out = [0u8; 32];
        for (byte, pair) in out.iter_mut().zip(text.as_bytes().chunks(2)) {
            let pair = std::str::from_utf8(pair).expect("hex is ASCII");
            *byte = u8::from_str_radix(pair, 16).expect("valid hex");
        }
        out
    }

    fn key(text: &str) -> [u8; 32] {
        Pubkey::from_str(text).expect("valid public key").to_bytes()
    }

    fn proof(value: &Value) -> Vec<[u8; 32]> {
        value
            .as_array()
            .expect("proof is a list")
            .iter()
            .map(|h| hex32(h.as_str().expect("hash is a string")))
            .collect()
    }

    fn domain(tag: &str) -> Domain {
        [
            Domain::Guaranteed,
            Domain::LegacyTranche,
            Domain::WeeklyDrop,
        ]
        .into_iter()
        .find(|d| d.tag() == tag.as_bytes())
        .expect("known domain")
    }

    #[test]
    fn domain_labels_match_the_spec() {
        let v = vectors();
        let domains = &v["domains"];
        assert_eq!(domains["guaranteed"], "percolator-dao-launch/guaranteed/v1");
        for (name, d) in [
            ("guaranteed", Domain::Guaranteed),
            ("legacy-tranche", Domain::LegacyTranche),
            ("weekly-drop", Domain::WeeklyDrop),
        ] {
            assert_eq!(domains[name].as_str().map(str::as_bytes), Some(d.tag()));
        }
        assert_eq!(v["max_proof_len"], MAX_PROOF_LEN);
        assert_eq!(v["leaf_prefix"], "00");
        assert_eq!(v["node_prefix"], "01");
    }

    #[test]
    fn every_vector_entry_verifies() {
        let v = vectors();
        let cases = v["cases"].as_array().expect("cases");
        assert!(cases.len() >= 6);
        for case in cases {
            let d = domain(case["domain"].as_str().expect("domain"));
            let distribution = key(case["distribution"].as_str().expect("distribution"));
            let root = hex32(case["root"].as_str().expect("root"));
            for entry in case["entries"].as_array().expect("entries") {
                let wallet = key(entry["wallet"].as_str().expect("wallet"));
                let amount: u64 = entry["amount"]
                    .as_str()
                    .expect("amount")
                    .parse()
                    .expect("u64");
                let index = u32::try_from(entry["index"].as_u64().expect("index")).expect("u32");
                let expected = hex32(entry["leaf"].as_str().expect("leaf"));
                assert_eq!(leaf(d, &distribution, &wallet, amount, index), expected);
                let p = proof(&entry["proof"]);
                assert_eq!(
                    verify_claim(d, &distribution, &wallet, amount, index, &p, &root),
                    Ok(()),
                    "{}",
                    case["name"]
                );
            }
        }
    }

    #[test]
    fn every_must_fail_vector_fails() {
        let v = vectors();
        let bad = v["must_fail"].as_array().expect("must_fail");
        assert!(bad.len() >= 6);
        for case in bad {
            let root = hex32(case["root"].as_str().expect("root"));
            let candidate = hex32(case["leaf"].as_str().expect("leaf"));
            assert!(
                !verify_proof(&proof(&case["proof"]), &root, candidate),
                "{}",
                case["why"]
            );
        }
    }

    #[test]
    fn length_limit_vectors() {
        let v = vectors();
        let long = &v["over_limit"];
        assert!(v["must_fail"].as_array().expect("must_fail").contains(long));
        for (case, len, accepted) in [
            (&v["at_limit"], MAX_PROOF_LEN, true),
            (long, MAX_PROOF_LEN + 1, false),
        ] {
            let p = proof(&case["proof"]);
            let candidate = hex32(case["leaf"].as_str().expect("leaf"));
            let root = hex32(case["root"].as_str().expect("root"));
            assert_eq!(p.len(), len);
            // The root is the one the proof leads to, so only the length
            // check can reject the longer proof.
            let folded = p.iter().fold(candidate, |h, s| node(&h, s));
            assert_eq!(folded, root);
            assert_eq!(verify_proof(&p, &root, candidate), accepted);
        }
    }

    #[test]
    fn node_is_order_independent() {
        let a = [1u8; 32];
        let b = [2u8; 32];
        assert_eq!(node(&a, &b), node(&b, &a));
        assert_ne!(node(&a, &b), node(&a, &a));
    }

    #[test]
    fn single_entry_list_needs_no_proof() {
        let l = leaf(Domain::WeeklyDrop, &[3u8; 32], &[4u8; 32], 5, 0);
        assert!(verify_proof(&[], &l, l));
    }

    #[test]
    fn proofs_over_the_limit_are_rejected() {
        let l = leaf(Domain::WeeklyDrop, &[3u8; 32], &[4u8; 32], 5, 0);
        let long = vec![l; MAX_PROOF_LEN + 1];
        let mut root = l;
        for sibling in &long {
            root = node(&root, sibling);
        }
        // Would verify if length were not checked.
        assert!(!verify_proof(&long, &root, l));
        let ok = vec![l; MAX_PROOF_LEN];
        let mut root = l;
        for sibling in &ok {
            root = node(&root, sibling);
        }
        assert!(verify_proof(&ok, &root, l));
    }

    #[test]
    fn wrong_wallet_amount_or_index_fails() {
        let dist = [9u8; 32];
        let a = leaf(Domain::LegacyTranche, &dist, &[1u8; 32], 100, 0);
        let b = leaf(Domain::LegacyTranche, &dist, &[2u8; 32], 200, 0);
        let root = node(&a, &b);
        let p = [b];
        let check = |domain, dist: &[u8; 32], wallet: &[u8; 32], amount, index| {
            verify_claim(domain, dist, wallet, amount, index, &p, &root)
        };
        assert_eq!(
            check(Domain::LegacyTranche, &dist, &[1u8; 32], 100, 0),
            Ok(())
        );
        let refused = Err(ClaimError::NotOnList);
        assert_eq!(
            check(Domain::LegacyTranche, &dist, &[3u8; 32], 100, 0),
            refused
        );
        assert_eq!(
            check(Domain::LegacyTranche, &dist, &[1u8; 32], 101, 0),
            refused
        );
        assert_eq!(
            check(Domain::LegacyTranche, &dist, &[1u8; 32], 100, 1),
            refused
        );
        assert_eq!(
            check(Domain::WeeklyDrop, &dist, &[1u8; 32], 100, 0),
            refused
        );
        assert_eq!(
            check(Domain::LegacyTranche, &[8u8; 32], &[1u8; 32], 100, 0),
            refused
        );
    }

    #[test]
    fn proof_of_exactly_the_limit_is_accepted() {
        let l = leaf(Domain::WeeklyDrop, &[3u8; 32], &[4u8; 32], 5, 0);
        let full = vec![l; MAX_PROOF_LEN];
        let mut root = l;
        for sibling in &full {
            root = node(&root, sibling);
        }
        assert_eq!(
            verify_claim(
                Domain::WeeklyDrop,
                &[3u8; 32],
                &[4u8; 32],
                5,
                0,
                &full,
                &root
            ),
            Ok(())
        );
    }

    #[test]
    fn overlong_proof_is_refused_as_too_long() {
        let l = leaf(Domain::WeeklyDrop, &[3u8; 32], &[4u8; 32], 5, 0);
        let long = vec![l; MAX_PROOF_LEN + 1];
        let mut root = l;
        for sibling in &long {
            root = node(&root, sibling);
        }
        assert_eq!(
            verify_claim(
                Domain::WeeklyDrop,
                &[3u8; 32],
                &[4u8; 32],
                5,
                0,
                &long,
                &root
            ),
            Err(ClaimError::ProofTooLong)
        );
    }
}

/// Kani proofs: these hold for every possible input, not just examples.
/// Run with `cargo kani` (Linux). The hash is the stand-in above.
///
/// Every harness ends with `kani::cover!` checks that CI requires to be met
/// (see the kani workflow), showing its cases are really reached. A cover
/// only shows the code before it is reachable, so covers come last, and
/// both outcomes are covered where there are two. Skipped by mutation
/// testing like the stand-ins above.
#[cfg(kani)]
#[cfg_attr(test, mutants::skip)]
mod proofs {
    use super::*;

    /// Verifies a symbolic proof of exactly `N` steps: never panics, and
    /// both outcomes are reachable. Every step runs the same code, so short
    /// fixed lengths cover the loop; the length limit has its own proof and
    /// unit tests run full 24-step proofs. (A symbolic length, or 24 symbolic
    /// steps, takes Kani far too long.)
    fn check_verify_proof<const N: usize>() {
        let siblings: [[u8; 32]; N] = kani::any();
        let root: [u8; 32] = kani::any();
        let candidate: [u8; 32] = kani::any();
        let accepted = verify_proof(&siblings, &root, candidate);
        kani::cover!(accepted, "some proof is accepted");
        kani::cover!(!accepted, "some proof is rejected");
    }

    #[kani::proof]
    #[kani::unwind(34)]
    fn verify_proof_never_panics_1_step() {
        check_verify_proof::<1>();
    }

    #[kani::proof]
    #[kani::unwind(34)]
    fn verify_proof_never_panics_4_steps() {
        check_verify_proof::<4>();
    }

    /// A proof longer than the limit is always rejected, whatever it holds.
    #[kani::proof]
    #[kani::unwind(34)]
    fn proofs_over_the_limit_always_rejected() {
        let siblings: [[u8; 32]; MAX_PROOF_LEN + 1] = kani::any();
        let root: [u8; 32] = kani::any();
        let candidate: [u8; 32] = kani::any();
        assert!(!verify_proof(&siblings, &root, candidate));
        kani::cover!(true, "the end is reached");
    }

    /// Combining two hashes gives the same result in either order.
    #[kani::proof]
    fn node_is_order_independent() {
        let a: [u8; 32] = kani::any();
        let b: [u8; 32] = kani::any();
        assert_eq!(node(&a, &b), node(&b, &a));
        kani::cover!(a != b, "distinct inputs are covered");
    }

    /// With no proof, an entry is accepted exactly when it is the root.
    #[kani::proof]
    fn empty_proof_accepts_only_the_root() {
        let root: [u8; 32] = kani::any();
        let candidate: [u8; 32] = kani::any();
        let accepted = verify_proof(&[], &root, candidate);
        assert_eq!(accepted, candidate == root);
        kani::cover!(accepted, "some entry is accepted");
        kani::cover!(!accepted, "some entry is rejected");
    }

    /// verify_claim never panics for any claim fields, with a 4-step proof.
    #[kani::proof]
    #[kani::unwind(34)]
    fn verify_claim_never_panics() {
        let domain = match kani::any::<u8>() {
            0 => Domain::Guaranteed,
            1 => Domain::LegacyTranche,
            _ => Domain::WeeklyDrop,
        };
        let siblings: [[u8; 32]; 4] = kani::any();
        let result = verify_claim(
            domain,
            &kani::any(),
            &kani::any(),
            kani::any(),
            kani::any(),
            &siblings,
            &kani::any(),
        );
        kani::cover!(result.is_ok(), "some claim is accepted");
        kani::cover!(
            result == Err(ClaimError::NotOnList),
            "some claim is rejected"
        );
    }
}
