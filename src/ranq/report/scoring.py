"""Versioned policy for the detected-issue score, not an SEO ranking prediction."""

SCORING_VERSION = "2"
SCORE_NOTE = (
    "Deprecated legacy penalty score, retained only for JSON/API compatibility. "
    "It is not a validated grade. Use assessment, findings and coverage instead."
)
