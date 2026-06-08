"""ELECTIONLENS - Influence-operations pattern monitor for election periods.

A standard-library-only engine that scans short-form posts/messages collected
during an election window and surfaces coordinated inauthentic behavior (CIB)
signals: copypasta amplification, burst timing, account clustering, and
narrative spikes. It does NOT judge truth/falsity of content -- it measures
*coordination and amplification patterns*, which are the observable footprint
of influence operations.
"""
from .core import (
    Post,
    AccountStats,
    NarrativeCluster,
    Findings,
    analyze,
    load_posts,
)

TOOL_NAME = "electionlens"
TOOL_VERSION = "1.0.0"

__all__ = [
    "Post",
    "AccountStats",
    "NarrativeCluster",
    "Findings",
    "analyze",
    "load_posts",
    "TOOL_NAME",
    "TOOL_VERSION",
]
