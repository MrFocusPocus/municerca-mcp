"""Build one static report.html from evals/results/*.json.

Every number comes from a result file written by `evals.run`. Nothing is hard coded.
Usage: uv run python scripts/report.py [--baseline v0] [--candidate v1]
"""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "evals" / "results"
TRACES = ROOT / "traces"

CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--muted:#666;--line:#ddd;--ok:#1a7f37;--bad:#b42318;--bar:#e8e8e8}
@media (prefers-color-scheme: dark){:root{--bg:#141414;--fg:#eee;--muted:#999;--line:#333;
--ok:#4ac26b;--bad:#f97066;--bar:#2a2a2a}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:980px;
margin:2rem auto;padding:0 16px}
h1{font-size:1.5rem;margin-bottom:.2rem}h2{font-size:1.1rem;margin-top:2rem}
table{border-collapse:collapse;width:100%;margin:.5rem 0}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:.85rem}
.num{text-align:right;font-variant-numeric:tabular-nums}
.muted{color:var(--muted);font-size:.85rem}.ok{color:var(--ok)}.bad{color:var(--bad)}
.bar{background:var(--bar);height:10px;border-radius:5px;min-width:120px}
.bar i{display:block;height:10px;border-radius:5px;background:var(--ok)}
.big{font-size:2rem;font-weight:700}
.cards{display:flex;gap:16px;flex-wrap:wrap}
.card{border:1px solid var(--line);border-radius:8px;padding:12px 16px;flex:1;min-width:220px}
code{font-size:.85em}
"""


def percentile(values: list[int], p: float) -> int:
    """Nearest rank percentile."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def stats(run: dict[str, Any]) -> dict[str, Any]:
    cases = run["cases"]
    n = len(cases)
    agent_costs = [c["agent_cost_usd"] for c in cases if c["agent_cost_usd"] is not None]
    return {
        "p50": percentile([c["latency_ms"] for c in cases], 50),
        "p95": percentile([c["latency_ms"] for c in cases], 95),
        "avg_in": round(sum(c["input_tokens"] for c in cases) / n),
        "avg_out": round(sum(c["output_tokens"] for c in cases) / n),
        "usd_per_conversation": sum(agent_costs) / len(agent_costs) if agent_costs else None,
    }


def esc(value: object) -> str:
    return html.escape(str(value))


def pct(rate: float) -> str:
    return f"{rate:.0%}"


def bar(rate: float) -> str:
    return f'<div class="bar"><i style="width:{rate * 100:.0f}%"></i></div>'


def trace_lines(run: dict[str, Any]) -> str:
    label = run["meta"]["label"]
    stamp = run["meta"]["started_at"].replace("-", "").replace(":", "").replace("+0000", "Z")
    path = TRACES / f"{label}-{stamp}.jsonl"
    if not path.exists():
        return "trace file not present locally"
    return f"{sum(1 for _ in path.open(encoding='utf-8'))} trace lines in traces/{path.name}"


def run_card(run: dict[str, Any]) -> str:
    meta, summary, s = run["meta"], run["summary"], stats(run)
    ok = summary["pass_rate"] >= meta["threshold"]
    cost_note = "" if summary["cost_known"] else " (incomplete)"
    usd = "unknown" if s["usd_per_conversation"] is None else f"{s['usd_per_conversation']:.5f}"
    return f"""<div class="card">
<div class="muted">{esc(meta["label"])} · prompt {esc(meta["prompt_version"])} ·
commit <code>{esc(meta["git_sha"])}</code></div>
<div class="big {"ok" if ok else "bad"}">{pct(summary["pass_rate"])}</div>
<div>{summary["passed"]}/{summary["total"]} cases passed, threshold {pct(meta["threshold"])}:
<b class="{"ok" if ok else "bad"}">{"OK" if ok else "below"}</b></div>
<table>
<tr><td>Latency p50 / p95</td><td class="num">{s["p50"]} ms / {s["p95"]} ms</td></tr>
<tr><td>Avg tokens in / out</td><td class="num">{s["avg_in"]} / {s["avg_out"]}</td></tr>
<tr><td>USD per conversation (agent)</td><td class="num">{usd}</td></tr>
<tr><td>Total run cost (agent + judge)</td>
<td class="num">USD {summary["total_cost_usd"]:.4f}{cost_note}</td></tr>
</table>
<div class="muted">agent {esc(meta["agent_model"])}, judge {esc(meta["judge_model"])},
provider {esc(meta["provider_host"])}<br>{esc(meta["started_at"])} · {esc(trace_lines(run))}</div>
</div>"""


def build(runs: dict[str, dict[str, Any]], baseline: str, candidate: str) -> str:
    base, cand = runs[baseline], runs[candidate]
    categories = sorted(set(base["summary"]["by_category"]) | set(cand["summary"]["by_category"]))
    rows = []
    for cat in categories:
        b = base["summary"]["by_category"].get(cat)
        c = cand["summary"]["by_category"].get(cat)
        cells = "".join(
            f'<td class="num">{x["passed"]}/{x["total"]}</td><td>{bar(x["pass_rate"])}</td>'
            if x
            else "<td></td><td></td>"
            for x in (b, c)
        )
        rows.append(f"<tr><td>{esc(cat)}</td>{cells}</tr>")
    bs, cs = base["summary"], cand["summary"]
    rows.append(
        f'<tr><td><b>overall</b></td><td class="num"><b>{bs["passed"]}/{bs["total"]}</b></td>'
        f'<td>{bar(bs["pass_rate"])}</td><td class="num"><b>{cs["passed"]}/{cs["total"]}</b></td>'
        f"<td>{bar(cs['pass_rate'])}</td></tr>"
    )

    base_cases = {c["id"]: c for c in base["cases"]}
    flipped, regressed, still = [], [], []
    for c in cand["cases"]:
        before = base_cases.get(c["id"])
        if before is None:
            continue
        if not before["passed"] and c["passed"]:
            flipped.append(
                f"<tr><td>{esc(c['id'])}</td><td>{esc(c['category'])}</td>"
                f"<td>{esc(', '.join(before['failed_checks']))}</td></tr>"
            )
        elif before["passed"] and not c["passed"]:
            regressed.append(c)
        if not c["passed"]:
            still.append(
                f"<tr><td>{esc(c['id'])}</td><td>{esc(c['category'])}</td>"
                f"<td>{esc(', '.join(c['failed_checks']))}</td>"
                f"<td>{esc(c['judge_reason'] or '')}</td></tr>"
            )
    regress_note = (
        "none"
        if not regressed
        else ", ".join(f"{c['id']} ({', '.join(c['failed_checks'])})" for c in regressed)
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>municerca-mcp eval report</title><style>{CSS}</style></head><body>
<h1>municerca-mcp eval report: {esc(baseline)} vs {esc(candidate)}</h1>
<div class="muted">Generated by scripts/report.py from evals/results/{esc(baseline)}.json and
evals/results/{esc(candidate)}.json. Every number below was produced by a real run.</div>
<div class="cards" style="margin-top:1rem">{run_card(base)}{run_card(cand)}</div>

<h2>Pass rate by category</h2>
<table><tr><th>Category</th><th class="num">{esc(baseline)}</th><th></th>
<th class="num">{esc(candidate)}</th><th></th></tr>{"".join(rows)}</table>

<h2>Cases that flipped from fail to pass ({len(flipped)})</h2>
<table><tr><th>Case</th><th>Category</th><th>Checks that failed in {esc(baseline)}</th></tr>
{"".join(flipped)}</table>
<p>Regressions (pass in {esc(baseline)}, fail in {esc(candidate)}): {esc(regress_note)}</p>

<h2>Still failing in {esc(candidate)} ({len(still)})</h2>
<table><tr><th>Case</th><th>Category</th><th>Failed checks</th><th>Judge reason</th></tr>
{"".join(still)}</table>

<h2>How to read this</h2>
<ul>
<li>A case passes only if every deterministic check passes and, where the case asks for it,
the groundedness judge passes. The judge never runs on a case that already failed.</li>
<li>Latency is wall clock per conversation including MCP server startup, measured with
concurrent cases, so it overstates single conversation latency.</li>
<li>Cost uses list prices for uncached input tokens, so it is an upper bound.</li>
<li>Each run is a single sample. LLM runs vary, so small differences are not significant.</li>
</ul></body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="v0")
    parser.add_argument("--candidate", default="v1")
    parser.add_argument("--out", type=Path, default=ROOT / "report.html")
    args = parser.parse_args()
    runs = {p.stem: json.loads(p.read_text("utf-8")) for p in sorted(RESULTS.glob("*.json"))}
    for label in (args.baseline, args.candidate):
        if label not in runs:
            raise SystemExit(f"missing evals/results/{label}.json")
    args.out.write_text(build(runs, args.baseline, args.candidate), "utf-8")
    print(f"wrote {args.out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
