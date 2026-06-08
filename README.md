# ELECTIONLENS — Influence-operations pattern monitor for election periods

> Part of the **[Cognis Neural Suite](https://github.com/cognis-digital)** by [Cognis Digital](https://cognis.digital)
> MIT License · domain: `info-integrity`

[![PyPI](https://img.shields.io/pypi/v/cognis-electionlens.svg)](https://pypi.org/project/cognis-electionlens/)
[![CI](https://github.com/cognis-digital/electionlens/actions/workflows/ci.yml/badge.svg)](https://github.com/cognis-digital/electionlens/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Influence-operations pattern monitor for election periods.

## Install

```bash
pip install cognis-electionlens
```

For local development from this repo:

```bash
pip install -e .
```

## Quick start

```bash
electionlens --version
electionlens scan demos/                          # run against bundled demo
electionlens scan demos/ --format sarif --out r.sarif --fail-on high
electionlens mcp                                   # start as MCP server (Cognis.Studio / Claude Desktop / Cursor)
```

## Built-in demo scenarios

Every scenario folder includes a `SCENARIO.md` describing what it represents and what findings to expect.

- `demos/01-coordinated-cluster/` — see [`SCENARIO.md`](demos/01-coordinated-cluster/SCENARIO.md)
- `demos/02-organic-activity/` — see [`SCENARIO.md`](demos/02-organic-activity/SCENARIO.md)
- `demos/03-cross-platform-amplification/` — see [`SCENARIO.md`](demos/03-cross-platform-amplification/SCENARIO.md)

## How it fits the Cognis Neural Suite

This tool is one of 52 in the [Cognis Neural Suite](https://github.com/cognis-digital). The full suite + launcher lives at:

- Suite landing: https://cognis.digital
- All 52 repos: https://github.com/cognis-digital
- Cognis.Studio (Enterprise AI Workforce, MCP host): https://cognis.studio

Every Suite tool ships an MCP server, so Cognis.Studio agents can call them as scoped capabilities.

## License

MIT. See [LICENSE](LICENSE).

## About

**[Cognis Digital](https://cognis.digital)** — Wyoming, USA · *Making Tomorrow Better Today: Advanced Cybersecurity, AI Innovation, and Blockchain Expertise.*
