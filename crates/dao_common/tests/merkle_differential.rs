//! Differential test between the Rust verifier and the TypeScript claim-list
//! code (scripts/lib/merkle.ts). Run by CI through
//! scripts/merkle-differential.ts; not part of the normal test run:
//!
//!   DIFF_IN=<typescript lists.json> DIFF_OUT=<rust lists.json> DIFF_SEED=<n> \
//!     cargo test -p dao_common --test merkle_differential -- --ignored
//!
//! Rust rebuilds every TypeScript list and must get the same root and
//! proofs, and accept every proof. It then writes its own random lists for
//! TypeScript to check the same way.

use dao_common::merkle::{leaf, node, verify_claim, Domain};
use serde_json::{json, Value};
use solana_program::pubkey::Pubkey;
use std::collections::HashMap;
use std::str::FromStr;

type Hash = [u8; 32];

const DOMAINS: [Domain; 3] = [
    Domain::Guaranteed,
    Domain::LegacyTranche,
    Domain::WeeklyDrop,
];

/// Test-only tree builder, independent of the TypeScript one.
fn build(
    domain: Domain,
    distribution: &Hash,
    entries: &[(Hash, u64, u32)],
) -> (Hash, HashMap<Hash, Vec<Hash>>) {
    let mut leaves: Vec<Hash> = entries
        .iter()
        .map(|(wallet, amount, index)| leaf(domain, distribution, wallet, *amount, *index))
        .collect();
    leaves.sort();
    let mut proofs: HashMap<Hash, Vec<Hash>> = leaves.iter().map(|l| (*l, Vec::new())).collect();
    let mut level: Vec<(Hash, Vec<Hash>)> = leaves.iter().map(|l| (*l, vec![*l])).collect();
    while level.len() > 1 {
        let mut above = Vec::new();
        let mut items = level.into_iter();
        loop {
            match (items.next(), items.next()) {
                (Some((left, mut left_members)), Some((right, right_members))) => {
                    for m in &left_members {
                        proofs.get_mut(m).expect("leaf").push(right);
                    }
                    for m in &right_members {
                        proofs.get_mut(m).expect("leaf").push(left);
                    }
                    left_members.extend(right_members);
                    above.push((node(&left, &right), left_members));
                }
                (Some(odd), None) => {
                    above.push(odd); // odd one out moves up unchanged
                    break;
                }
                _ => break,
            }
        }
        level = above;
    }
    let root = level.first().expect("non-empty list").0;
    (root, proofs)
}

/// Small seeded generator (xorshift64*) so failures are reproducible.
struct Rng(u64);

impl Rng {
    fn next(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x.wrapping_shr(12);
        x ^= x.wrapping_shl(25);
        x ^= x.wrapping_shr(27);
        self.0 = x;
        x.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }

    fn below(&mut self, n: u64) -> u64 {
        self.next().checked_rem(n).unwrap_or(0)
    }

    fn hash(&mut self) -> Hash {
        let mut out = [0u8; 32];
        for chunk in out.chunks_mut(8) {
            chunk.copy_from_slice(&self.next().to_le_bytes());
        }
        out
    }
}

fn hex(bytes: &Hash) -> String {
    use std::fmt::Write;
    bytes.iter().fold(String::with_capacity(64), |mut out, b| {
        write!(out, "{b:02x}").expect("write to String");
        out
    })
}

fn unhex(text: &str) -> Hash {
    let mut out = [0u8; 32];
    for (byte, pair) in out.iter_mut().zip(text.as_bytes().chunks(2)) {
        *byte = u8::from_str_radix(std::str::from_utf8(pair).expect("ascii"), 16).expect("hex");
    }
    out
}

fn key(text: &str) -> Hash {
    Pubkey::from_str(text).expect("public key").to_bytes()
}

fn domain_of(tag: &str) -> Domain {
    DOMAINS
        .into_iter()
        .find(|d| d.tag() == tag.as_bytes())
        .expect("known domain")
}

fn check_typescript_lists(path: &str) -> usize {
    let text = std::fs::read_to_string(path).expect("read TypeScript lists");
    let file: Value = serde_json::from_str(&text).expect("JSON");
    assert_eq!(file["producer"], "typescript");
    let lists = file["lists"].as_array().expect("lists");
    assert!(!lists.is_empty());
    let mut checked = 0usize;
    for list in lists {
        let domain = domain_of(list["domain"].as_str().expect("domain"));
        let distribution = key(list["distribution"].as_str().expect("distribution"));
        let entries: Vec<(Hash, u64, u32)> = list["entries"]
            .as_array()
            .expect("entries")
            .iter()
            .map(|e| {
                (
                    key(e["wallet"].as_str().expect("wallet")),
                    e["amount"].as_str().expect("amount").parse().expect("u64"),
                    u32::try_from(e["index"].as_u64().expect("index")).expect("u32"),
                )
            })
            .collect();
        let (root, proofs) = build(domain, &distribution, &entries);
        assert_eq!(
            hex(&root),
            list["root"],
            "root differs for a TypeScript list"
        );
        for (e, (wallet, amount, index)) in list["entries"]
            .as_array()
            .expect("entries")
            .iter()
            .zip(&entries)
        {
            let l = leaf(domain, &distribution, wallet, *amount, *index);
            assert_eq!(hex(&l), e["leaf"], "leaf differs");
            let ts_proof: Vec<Hash> = e["proof"]
                .as_array()
                .expect("proof")
                .iter()
                .map(|p| unhex(p.as_str().expect("hash")))
                .collect();
            assert_eq!(
                proofs.get(&l).expect("leaf in tree"),
                &ts_proof,
                "proof differs"
            );
            assert_eq!(
                verify_claim(
                    domain,
                    &distribution,
                    wallet,
                    *amount,
                    *index,
                    &ts_proof,
                    &root
                ),
                Ok(())
            );
            checked = checked.checked_add(1).expect("count");
        }
    }
    checked
}

fn write_rust_lists(path: &str, seed: u64) {
    // A different stream from TypeScript's, so Rust's lists are new ones.
    let mut rng = Rng((seed ^ 0x9E37_79B9_7F4A_7C15) | 1);
    let mut lists = Vec::new();
    for n in 0..200u64 {
        // Mostly small lists, some large ones, and every size class covered.
        let size = if n.checked_rem(25) == Some(0) {
            rng.below(1000).saturating_add(500)
        } else {
            rng.below(40).saturating_add(1)
        };
        let domain = DOMAINS[usize::try_from(rng.below(3)).expect("index")];
        let distribution = rng.hash();
        let mut entries = Vec::new();
        for _ in 0..size {
            let amount = match rng.below(10) {
                0 => u64::MAX,
                1 => 1,
                _ => rng.next().max(1),
            };
            let index = match rng.below(4) {
                0 => u32::MAX,
                1 => 0,
                _ => u32::try_from(rng.below(8)).expect("small"),
            };
            entries.push((rng.hash(), amount, index));
        }
        let (root, proofs) = build(domain, &distribution, &entries);
        let out_entries: Vec<Value> = entries
            .iter()
            .map(|(wallet, amount, index)| {
                let l = leaf(domain, &distribution, wallet, *amount, *index);
                json!({
                    "wallet": Pubkey::new_from_array(*wallet).to_string(),
                    "amount": amount.to_string(),
                    "index": index,
                    "leaf": hex(&l),
                    "proof": proofs[&l].iter().map(hex).collect::<Vec<_>>(),
                })
            })
            .collect();
        lists.push(json!({
            "domain": std::str::from_utf8(domain.tag()).expect("ascii"),
            "distribution": Pubkey::new_from_array(distribution).to_string(),
            "root": hex(&root),
            "entries": out_entries,
        }));
    }
    let file = json!({ "producer": "rust", "seed": seed.to_string(), "lists": lists });
    std::fs::write(path, serde_json::to_string(&file).expect("JSON")).expect("write Rust lists");
}

#[test]
#[ignore = "run by scripts/merkle-differential.ts"]
fn differential_with_typescript() {
    let input = std::env::var("DIFF_IN").expect("DIFF_IN: TypeScript lists to check");
    let output = std::env::var("DIFF_OUT").expect("DIFF_OUT: where to write Rust lists");
    let seed: u64 = std::env::var("DIFF_SEED")
        .expect("DIFF_SEED")
        .parse()
        .expect("u64 seed");
    let checked = check_typescript_lists(&input);
    println!("rust checked {checked} TypeScript entries");
    write_rust_lists(&output, seed);
}
