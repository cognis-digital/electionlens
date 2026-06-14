"""Core analysis engine for ELECTIONLENS.

Detects coordination/amplification footprints in a corpus of timestamped posts.
All logic is real and deterministic; no network, no third-party deps.

Signals computed:
  1. Copypasta amplification -- near-identical text reposted by many accounts.
  2. Burst timing            -- accounts posting in tight synchronized windows.
  3. Account clustering       -- accounts sharing the same message fingerprints.
  4. Narrative spikes         -- hashtags/keywords surging in a short window.
  5. Per-account risk         -- composite suspicion score per account.

Input records (JSON list or JSONL), each:
  {"id":..., "account":..., "timestamp": ISO8601, "text":..., "hashtags":[...]}
hashtags optional (extracted from text if absent).
"""
from __future__ import annotations

import json
import re
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from collections import defaultdict, Counter
from typing import Any

_WORD_RE = re.compile(r"[a-z0-9']+")
_HASHTAG_RE = re.compile(r"#(\w+)")
_URL_RE = re.compile(r"https?://\S+")


class AnalysisError(Exception):
    """Raised on malformed input."""


@dataclass
class Post:
    id: str
    account: str
    timestamp: datetime
    text: str
    hashtags: list[str] = field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        """Normalized content fingerprint (strips urls, mentions, casing,
        punctuation) so near-identical copypasta collapses to one key."""
        t = _URL_RE.sub("", self.text.lower())
        t = re.sub(r"@\w+", "", t)
        words = _WORD_RE.findall(t)
        return " ".join(words)


@dataclass
class AccountStats:
    account: str
    post_count: int
    distinct_fingerprints: int
    duplicate_ratio: float
    burst_membership: int
    risk_score: float
    flags: list[str]


@dataclass
class NarrativeCluster:
    fingerprint: str
    sample_text: str
    account_count: int
    post_count: int
    accounts: list[str]
    first_seen: str
    last_seen: str
    span_seconds: float


@dataclass
class Findings:
    post_count: int
    account_count: int
    window_start: str
    window_end: str
    coordination_index: float
    risk_level: str
    copypasta_clusters: list[NarrativeCluster]
    burst_windows: list[dict]
    narrative_spikes: list[dict]
    top_accounts: list[AccountStats]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def _parse_ts(raw: str) -> datetime:
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as e:
        raise AnalysisError(f"bad timestamp: {raw!r}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_posts(raw: str) -> list[Post]:
    """Parse a JSON array or JSONL string into Post objects."""
    raw = raw.strip()
    if not raw:
        raise AnalysisError("empty input")
    records: list[dict]
    if raw[0] == "[":
        try:
            records = json.loads(raw)
        except json.JSONDecodeError as e:
            raise AnalysisError(f"invalid JSON: {e}") from e
        if not isinstance(records, list):
            raise AnalysisError("JSON input must be an array, not an object")
    else:
        records = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise AnalysisError(f"invalid JSONL line: {e}") from e
    if not isinstance(records, list):
        raise AnalysisError("input must be a JSON array or JSONL")
    posts: list[Post] = []
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            raise AnalysisError(f"record {i} is not an object")
        try:
            text = str(r.get("text", ""))
            tags = r.get("hashtags")
            if not tags:
                tags = [m.lower() for m in _HASHTAG_RE.findall(text)]
            else:
                tags = [str(t).lstrip("#").lower() for t in tags]
            posts.append(Post(
                id=str(r.get("id", f"post-{i}")),
                account=str(r["account"]),
                timestamp=_parse_ts(str(r["timestamp"])),
                text=text,
                hashtags=tags,
            ))
        except KeyError as e:
            raise AnalysisError(f"record {i} missing field {e}") from e
    if not posts:
        raise AnalysisError("no usable posts found")
    return posts


def _copypasta_clusters(posts: list[Post], min_accounts: int) -> list[NarrativeCluster]:
    by_fp: dict[str, list[Post]] = defaultdict(list)
    for p in posts:
        fp = p.fingerprint
        if len(fp) < 8:  # ignore trivially short text
            continue
        by_fp[fp].append(p)
    clusters: list[NarrativeCluster] = []
    for fp, group in by_fp.items():
        accounts = sorted({p.account for p in group})
        if len(accounts) < min_accounts:
            continue
        ts = sorted(p.timestamp for p in group)
        span = (ts[-1] - ts[0]).total_seconds()
        clusters.append(NarrativeCluster(
            fingerprint=fp[:80],
            sample_text=group[0].text,
            account_count=len(accounts),
            post_count=len(group),
            accounts=accounts[:25],
            first_seen=ts[0].isoformat(),
            last_seen=ts[-1].isoformat(),
            span_seconds=span,
        ))
    clusters.sort(key=lambda c: (c.account_count, c.post_count), reverse=True)
    return clusters


def _burst_windows(posts: list[Post], window_sec: int, min_accounts: int) -> list[dict]:
    """Sliding fixed-grid buckets; flag buckets where many distinct accounts
    fire near-simultaneously (synchronized amplification)."""
    buckets: dict[int, list[Post]] = defaultdict(list)
    for p in posts:
        key = int(p.timestamp.timestamp()) // window_sec
        buckets[key].append(p)
    out: list[dict] = []
    for key, group in buckets.items():
        accounts = {p.account for p in group}
        if len(accounts) < min_accounts:
            continue
        start = datetime.fromtimestamp(key * window_sec, tz=timezone.utc)
        end = datetime.fromtimestamp((key + 1) * window_sec, tz=timezone.utc)
        # synchronization = how concentrated the distinct fingerprints are
        fps = Counter(p.fingerprint for p in group)
        dominant = fps.most_common(1)[0][1] / len(group)
        out.append({
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "account_count": len(accounts),
            "post_count": len(group),
            "dominant_message_share": round(dominant, 3),
        })
    out.sort(key=lambda w: (w["account_count"], w["post_count"]), reverse=True)
    return out


def _narrative_spikes(posts: list[Post], window_sec: int) -> list[dict]:
    """Per-hashtag rate spike detection vs the tag's own baseline."""
    by_tag: dict[str, list[datetime]] = defaultdict(list)
    for p in posts:
        for tag in p.hashtags:
            by_tag[tag].append(p.timestamp)
    spikes: list[dict] = []
    for tag, times in by_tag.items():
        if len(times) < 4:
            continue
        times.sort()
        buckets: Counter = Counter(int(t.timestamp()) // window_sec for t in times)
        counts = list(buckets.values())
        mean = sum(counts) / len(counts)
        peak = max(counts)
        # spike ratio of peak bucket over mean bucket activity
        ratio = peak / mean if mean else float(peak)
        if ratio >= 2.0 and peak >= 3:
            peak_key = max(buckets, key=lambda k: buckets[k])
            start = datetime.fromtimestamp(peak_key * window_sec, tz=timezone.utc)
            spikes.append({
                "hashtag": tag,
                "total_mentions": len(times),
                "peak_count": peak,
                "spike_ratio": round(ratio, 2),
                "peak_window_start": start.isoformat(),
            })
    spikes.sort(key=lambda s: s["spike_ratio"], reverse=True)
    return spikes


def _account_stats(posts: list[Post], burst_windows: list[dict],
                   window_sec: int) -> list[AccountStats]:
    by_acct: dict[str, list[Post]] = defaultdict(list)
    for p in posts:
        by_acct[p.account].append(p)
    # map which buckets are bursty
    bursty_keys = set()
    for w in burst_windows:
        start = _parse_ts(w["window_start"])
        bursty_keys.add(int(start.timestamp()) // window_sec)
    stats: list[AccountStats] = []
    for acct, group in by_acct.items():
        fps = {p.fingerprint for p in group}
        n = len(group)
        dup_ratio = 1.0 - (len(fps) / n) if n else 0.0
        burst_member = sum(
            1 for p in group
            if int(p.timestamp.timestamp()) // window_sec in bursty_keys
        )
        flags: list[str] = []
        if dup_ratio >= 0.5 and n >= 3:
            flags.append("high_self_duplication")
        if burst_member >= 2:
            flags.append("burst_participant")
        if n >= 10:
            flags.append("high_volume")
        # composite risk: duplication + burst participation + volume
        risk = (
            0.5 * dup_ratio
            + 0.35 * min(1.0, burst_member / 3.0)
            + 0.15 * min(1.0, math.log1p(n) / math.log(20))
        )
        stats.append(AccountStats(
            account=acct,
            post_count=n,
            distinct_fingerprints=len(fps),
            duplicate_ratio=round(dup_ratio, 3),
            burst_membership=burst_member,
            risk_score=round(risk, 3),
            flags=flags,
        ))
    stats.sort(key=lambda s: s.risk_score, reverse=True)
    return stats


def analyze(posts: list[Post], *, window_sec: int = 120,
            min_cluster_accounts: int = 3,
            min_burst_accounts: int = 4) -> Findings:
    """Run the full coordination analysis over a corpus of posts."""
    if not posts:
        raise AnalysisError("no posts to analyze")
    if not isinstance(window_sec, int) or window_sec < 1:
        raise AnalysisError(
            f"window_sec must be a positive integer, got {window_sec!r}"
        )
    if not isinstance(min_cluster_accounts, int) or min_cluster_accounts < 1:
        raise AnalysisError(
            "min_cluster_accounts must be a positive integer, "
            f"got {min_cluster_accounts!r}"
        )
    if not isinstance(min_burst_accounts, int) or min_burst_accounts < 1:
        raise AnalysisError(
            "min_burst_accounts must be a positive integer, "
            f"got {min_burst_accounts!r}"
        )
    times = sorted(p.timestamp for p in posts)
    accounts = {p.account for p in posts}

    clusters = _copypasta_clusters(posts, min_cluster_accounts)
    bursts = _burst_windows(posts, window_sec, min_burst_accounts)
    spikes = _narrative_spikes(posts, window_sec)
    acct_stats = _account_stats(posts, bursts, window_sec)

    # coordination index in [0,1]: blends fraction of posts in copypasta
    # clusters, fraction of accounts that are burst participants, and the
    # mean risk of the top decile of accounts.
    posts_in_clusters = sum(c.post_count for c in clusters)
    cluster_frac = posts_in_clusters / len(posts)
    burst_accounts = {a for s in acct_stats for a in [s.account]
                      if s.burst_membership >= 1}
    burst_frac = len(burst_accounts) / len(accounts)
    top_n = max(1, len(acct_stats) // 10)
    top_risk = sum(s.risk_score for s in acct_stats[:top_n]) / top_n
    coordination_index = round(
        0.45 * cluster_frac + 0.30 * burst_frac + 0.25 * top_risk, 3
    )
    if coordination_index >= 0.6:
        level = "CRITICAL"
    elif coordination_index >= 0.4:
        level = "ELEVATED"
    elif coordination_index >= 0.2:
        level = "GUARDED"
    else:
        level = "LOW"

    return Findings(
        post_count=len(posts),
        account_count=len(accounts),
        window_start=times[0].isoformat(),
        window_end=times[-1].isoformat(),
        coordination_index=coordination_index,
        risk_level=level,
        copypasta_clusters=clusters[:20],
        burst_windows=bursts[:20],
        narrative_spikes=spikes[:20],
        top_accounts=acct_stats[:20],
    )
