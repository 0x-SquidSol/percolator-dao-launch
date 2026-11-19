//! Shared helpers for the experiment's on-chain programs.
//!
//! Experimental and unaudited: see the repository README. Helpers are added
//! here one at a time, each with its own tests.
#![forbid(unsafe_code)]

#[cfg(test)]
mod tests {
    /// Placeholder proving the workspace builds and runs tests. Replaced by
    /// real tests as helpers are added.
    #[test]
    fn workspace_builds_and_runs_tests() {
        assert_eq!(env!("CARGO_PKG_NAME"), "dao_common");
    }
}
