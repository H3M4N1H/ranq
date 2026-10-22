"""Versioned policy for the detected-issue score, not an SEO ranking prediction."""

SCORING_VERSION = "2"
SCORE_NOTE = (
    "Automated audit health: detected issues only, not rankings or overall website quality. "
    "Score = 100 * exp(-penalty / 100), rounded (minimum 1 for audited sites; 0 if no HTML "
    "was audited). Severity weights: critical 100, high 40, medium 15, low 5, info 0. "
    "Site-wide findings count in full; page findings use weight * (0.3 + 0.7 * affected share). "
    "Page scores exclude site-wide findings. Unmeasured checks are unknown, not passes."
)
