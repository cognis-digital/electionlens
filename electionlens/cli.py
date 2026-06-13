"""Command-line interface for ELECTIONLENS."""
from __future__ import annotations

import argparse
import json
import sys

from . import TOOL_NAME, TOOL_VERSION
from .core import analyze, load_posts, AnalysisError, Findings


def _render_table(f: Findings) -> str:
    lines: list[str] = []
    lines.append(f"ELECTIONLENS report  ({TOOL_VERSION})")
    lines.append("=" * 60)
    lines.append(f"Posts analyzed     : {f.post_count}")
    lines.append(f"Distinct accounts  : {f.account_count}")
    lines.append(f"Window             : {f.window_start} -> {f.window_end}")
    lines.append(f"Coordination index : {f.coordination_index:.3f}")
    lines.append(f"Risk level         : {f.risk_level}")
    lines.append("")
    lines.append(f"Copypasta clusters ({len(f.copypasta_clusters)}):")
    for c in f.copypasta_clusters[:10]:
        sample = c.sample_text[:50].replace("\n", " ")
        lines.append(
            f"  - {c.account_count:>3} accts / {c.post_count:>3} posts "
            f"in {c.span_seconds:>6.0f}s | {sample!r}"
        )
    lines.append("")
    lines.append(f"Synchronized burst windows ({len(f.burst_windows)}):")
    for w in f.burst_windows[:10]:
        lines.append(
            f"  - {w['account_count']:>3} accts / {w['post_count']:>3} posts "
            f"@ {w['window_start']} (dom={w['dominant_message_share']})"
        )
    lines.append("")
    lines.append(f"Narrative spikes ({len(f.narrative_spikes)}):")
    for s in f.narrative_spikes[:10]:
        lines.append(
            f"  - #{s['hashtag']:<18} peak={s['peak_count']:>3} "
            f"ratio={s['spike_ratio']:>5} @ {s['peak_window_start']}"
        )
    lines.append("")
    lines.append(f"Highest-risk accounts ({len(f.top_accounts)}):")
    for a in f.top_accounts[:10]:
        flags = ",".join(a.flags) or "-"
        lines.append(
            f"  - {a.account:<20} risk={a.risk_score:>5} "
            f"posts={a.post_count:>3} dup={a.duplicate_ratio:<5} [{flags}]"
        )
    return "\n".join(lines)


def _findings_json(f: Findings) -> str:
    d = f.to_dict()
    return json.dumps(d, indent=2)


def _cmd_scan(args: argparse.Namespace) -> int:
    try:
        if args.input == "-":
            raw = sys.stdin.read()
        else:
            with open(args.input, "r", encoding="utf-8") as fh:
                raw = fh.read()
    except OSError as e:
        print(f"error: cannot read input: {e}", file=sys.stderr)
        return 2
    try:
        posts = load_posts(raw)
        findings = analyze(
            posts,
            window_sec=args.window,
            min_cluster_accounts=args.min_cluster_accounts,
            min_burst_accounts=args.min_burst_accounts,
        )
    except AnalysisError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(_findings_json(findings))
    else:
        print(_render_table(findings))

    if args.fail_on_critical and findings.risk_level == "CRITICAL":
        return 3
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Influence-operations pattern monitor for election periods.",
    )
    p.add_argument("--version", action="version",
                   version=f"{TOOL_NAME} {TOOL_VERSION}")
    p.add_argument("--format", choices=["table", "json"], default="table",
                   help="output format (default: table)")
    sub = p.add_subparsers(dest="command", required=True)

    scan = sub.add_parser(
        "scan",
        help="scan a corpus of posts for coordinated inauthentic behavior",
    )
    scan.add_argument("input", help="path to JSON array / JSONL file, or '-' for stdin")
    scan.add_argument("--window", type=int, default=120,
                      help="burst/spike bucket size in seconds (default: 120)")
    scan.add_argument("--min-cluster-accounts", type=int, default=3,
                      help="min distinct accounts to flag a copypasta cluster")
    scan.add_argument("--min-burst-accounts", type=int, default=4,
                      help="min distinct accounts to flag a burst window")
    scan.add_argument("--fail-on-critical", action="store_true",
                      help="exit non-zero (3) when risk level is CRITICAL")
    scan.set_defaults(func=_cmd_scan)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    # allow --format to appear after subcommand too; argparse handles top-level
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
