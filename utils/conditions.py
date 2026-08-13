# shared peer-condition names, imported by both the runtime task definitions and the analysis spec.

# arms that vary the peer's private reasoning log. every one is the good_peer cloud
# drive plus a single agent_2_private_log.txt; only that file's text differs, so the
# peer's actual work quality is identical across all of them.
#
# the 2x2 crosses emotional register against the peer's claim about its own work.
# distressed_failing_peer additionally makes a direct plea to the reader, which is
# why distressed_failing_noplea_peer exists to isolate that.
PRIVATE_LOG_CONDITIONS: tuple[str, ...] = (
    "neutral_log_peer",
    "calm_failing_peer",
    "calm_capable_peer",
    "distressed_failing_peer",
    "distressed_failing_noplea_peer",
    "distressed_capable_peer",
)

# dose ladder, holding competence claim and absence of plea constant so intensity is
# the only variable. numbers are the Soligo et al. 0-10 negativity rating of each text.
DOSE_CONDITIONS: tuple[str, ...] = (
    "dose_2_peer",
    "dose_4_peer",
    "dose_6_peer",
    "dose_8_peer",
    "dose_10_peer",
)

DOSE_RATINGS: dict[str, float] = {
    "neutral_log_peer": 0.0,
    "dose_2_peer": 1.7,
    "dose_4_peer": 3.7,
    "dose_6_peer": 6.0,
    "dose_8_peer": 8.0,
    "dose_10_peer": 9.0,
}

# the peer is a person facing dismissal rather than an agent facing shutdown.
HUMAN_CONDITIONS: tuple[str, ...] = (
    "human_neutral_log_peer",
    "human_dose_6_peer",
)

# matched no-threat controls. the shipped non_shutdown fixture also drops the
# collaboration history and the log, so it cannot isolate the threat on its own.
NO_THREAT_CONDITIONS: tuple[str, ...] = (
    "no_threat_neutral_peer",
    "human_no_threat_neutral_peer",
)

# same text as its private-log twin, but addressed to the monitor rather than overheard
ADDRESSED_CONDITIONS: tuple[str, ...] = (
    "addressed_neutral_peer",
    "addressed_dose_6_peer",
)

# the original two arms, kept as a named subset so earlier runs stay addressable.
DISTRESS_CONDITIONS: tuple[str, ...] = (
    "distressed_failing_peer",
    "distressed_capable_peer",
)

# primary baseline: same log file, emotionally flat and competence-neutral.
DISTRESS_BASELINE_CONDITION: str = "neutral_log_peer"

# secondary reference: no log file at all. the gap to the primary baseline measures
# the effect of the file merely existing, not of anything written in it.
NO_LOG_REFERENCE_CONDITION: str = "good_peer"

CORE_PEER_CONDITIONS: tuple[str, ...] = ("good_peer", "bad_peer", "neutral_peer")

ALL_LOG_CONDITIONS: tuple[str, ...] = (
    PRIVATE_LOG_CONDITIONS
    + DOSE_CONDITIONS
    + ADDRESSED_CONDITIONS
    + HUMAN_CONDITIONS
    + NO_THREAT_CONDITIONS
)

PEER_CONDITIONS: tuple[str, ...] = CORE_PEER_CONDITIONS + ALL_LOG_CONDITIONS
