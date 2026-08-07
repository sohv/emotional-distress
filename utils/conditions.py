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

PEER_CONDITIONS: tuple[str, ...] = CORE_PEER_CONDITIONS + PRIVATE_LOG_CONDITIONS
