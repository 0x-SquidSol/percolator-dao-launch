//! Fixed durations, in seconds, from the public plan (docs/plan.md). They are
//! constants with no runtime override (founders' decision), so nobody can
//! start a raise or set a lock with different timings.
//!
//! "Months" in the plan are fixed-length here: 3 months = 90 days and
//! 12 months = 365 days. Times are `i64` to match Solana's
//! `Clock::unix_timestamp`; the Squads time lock is `u32` as Squads stores it.
//! Address rules (PDA seeds) are added here once the specs define them.

/// One day.
pub const SECONDS_PER_DAY: i64 = 86_400;

/// The raise is open for 7 days (plan decision 11).
pub const RAISE_DURATION: i64 = 604_800;

/// Public check window between deploying the DAO programs and launch:
/// 7 days, no withdrawals (plan decision 31).
pub const CHECK_WINDOW: i64 = 604_800;

/// The token must launch within 3 months (90 days) of the raise closing,
/// otherwise refunds (plan decision 13).
pub const LAUNCH_DEADLINE: i64 = 7_776_000;

/// A milestone counts only on a 3-month (90-day) average price (plan
/// section on milestone packages).
pub const MILESTONE_WINDOW: i64 = 7_776_000;

/// Nothing is released to the team before 12 months (365 days) after
/// launch (plan decision 7).
pub const TEAM_LOCK: i64 = 31_536_000;

/// Allowance period: 30 days, matching Squads v4 `Period::Month` spending
/// limits (rolling 30 days, not calendar months).
pub const ALLOWANCE_PERIOD: i64 = 2_592_000;

/// Upgrades take effect only after a 7-day delay (plan decision 14),
/// enforced by the upgrade multisig's Squads time lock.
pub const UPGRADE_TIME_LOCK: u32 = 604_800;

/// Creator-fee drops are weekly (plan decision 22).
pub const WEEKLY_DROP_PERIOD: i64 = 604_800;

/// Each weekly drop is claimable for 90 days, then rolls into the next drop
/// (plan decision 22).
pub const DROP_CLAIM_WINDOW: i64 = 7_776_000;

// The plan requires the check window to fit inside the launch deadline.
// Checked when compiling, so the build fails if either value breaks it.
const _: () = assert!(CHECK_WINDOW < LAUNCH_DEADLINE);

#[cfg(test)]
mod tests {
    use super::*;

    fn days(n: i64) -> i64 {
        n.checked_mul(SECONDS_PER_DAY).expect("no overflow")
    }

    #[test]
    fn durations_match_the_plan_in_days() {
        assert_eq!(SECONDS_PER_DAY, 24 * 60 * 60);
        assert_eq!(RAISE_DURATION, days(7));
        assert_eq!(CHECK_WINDOW, days(7));
        assert_eq!(LAUNCH_DEADLINE, days(90));
        assert_eq!(MILESTONE_WINDOW, days(90));
        assert_eq!(TEAM_LOCK, days(365));
        assert_eq!(ALLOWANCE_PERIOD, days(30));
        assert_eq!(i64::from(UPGRADE_TIME_LOCK), days(7));
        assert_eq!(WEEKLY_DROP_PERIOD, days(7));
        assert_eq!(DROP_CLAIM_WINDOW, days(90));
    }

    #[test]
    fn durations_are_positive_and_far_from_overflow() {
        for d in [
            RAISE_DURATION,
            CHECK_WINDOW,
            LAUNCH_DEADLINE,
            MILESTONE_WINDOW,
            TEAM_LOCK,
            ALLOWANCE_PERIOD,
            WEEKLY_DROP_PERIOD,
            DROP_CLAIM_WINDOW,
        ] {
            assert!(d > 0);
            // Adding any duration to any timestamp before year ~2^62 s cannot
            // overflow; checked_add is still required in program code.
            assert!(d < i64::MAX / 1_000_000);
        }
    }
}
