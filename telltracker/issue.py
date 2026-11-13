"""The daily GitHub Issue: titled with the date, listing what moved most since the previous run."""
import json
import re
import subprocess

from .moves import compare

TITLE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_MOVES = 20     # how many of the biggest moves the issue lists
MAX_LISTED = 30    # appeared / gone items listed before "and N more"
UNITS = {"is_open": "", "snow_depth_in": " in", "forecast_snow_72h_in": " in"}
LABEL = {"is_open": "status", "snow_depth_in": "snow depth", "forecast_snow_72h_in": "72-hour snow forecast"}


def _num(x):
    return str(int(x)) if x == int(x) else f"{x:.1f}"


def describe(m):
    if m["field"] == "is_open":
        return f"{m['old_status'] or 'closed'} → {m['new_status'] or 'open'}"
    sign = "+" if m["delta"] > 0 else ""
    return f"{LABEL[m['field']]} {_num(m['old'])} → {_num(m['new'])}{UNITS[m['field']]} ({sign}{_num(m['delta'])})"


def render_issue(day, rows, status):
    """Return (title, body). The title is the date, so every day has its own issue."""
    ch = compare(rows, day)
    failed = [s["name"] for s in status["sources"] if not s["ok"]]
    lines = [
        f"Run at {status['run_time']}", "",
        f"- Items tracked: **{status['items']}**",
        f"- Appeared: **{len(ch['appeared'])}**, gone: **{len(ch['gone'])}**",
        f"- Items that moved: **{len(ch['moves'])}**",
        f"- Days with a successful run: **{status['days_with_success']}**",
        f"- Sources that failed: {', '.join(failed) if failed else 'none'}", "",
    ]
    if not ch["previous"]:
        lines += ["This is the first run of every source, so there is no previous run to compare with yet.", ""]
    elif not (ch["moves"] or ch["appeared"] or ch["gone"]):
        lines += ["Nothing moved since the previous run.", ""]
    lines += [f"## Biggest moves ({len(ch['moves'])})", ""]
    if ch["moves"]:
        for m in ch["moves"][:MAX_MOVES]:
            lines.append(f"- **{m['item']}** ({m['category']}): {describe(m)}  · score {m['score']:.2f}")
        if len(ch["moves"]) > MAX_MOVES:
            lines.append(f"- …and {len(ch['moves']) - MAX_MOVES} smaller moves (see `data/history.csv`)")
    else:
        lines.append("None.")
    for heading, items in (("Appeared", ch["appeared"]), ("Gone", ch["gone"])):
        lines += ["", f"## {heading} ({len(items)})", ""]
        if not items:
            lines.append("None.")
        for r in items[:MAX_LISTED]:
            lines.append(f"- {r['item']} ({r['category']})")
        if len(items) > MAX_LISTED:
            lines.append(f"- …and {len(items) - MAX_LISTED} more")
    return day, "\n".join(lines) + "\n"


def _gh(args, body=None):
    return subprocess.run(["gh", *args], input=body, text=True, encoding="utf-8",
                          capture_output=True, check=True).stdout


def publish_issue(title, body):
    """Create today's issue (or update it on a re-run) and close every earlier one."""
    issues = json.loads(_gh(["issue", "list", "--state", "all", "--limit", "200",
                             "--json", "number,title,state"]))
    today = next((i for i in issues if i["title"] == title), None)
    if today is None:
        print("opened issue:", _gh(["issue", "create", "--title", title, "--body-file", "-"], body).strip())
    else:
        _gh(["issue", "edit", str(today["number"]), "--body-file", "-"], body)
        if today["state"] != "OPEN":
            _gh(["issue", "reopen", str(today["number"])])
        print("updated issue", today["number"])
    for issue in issues:
        if issue["state"] == "OPEN" and TITLE.match(issue["title"]) and issue["title"] != title:
            _gh(["issue", "close", str(issue["number"]), "--comment", f"Superseded by {title}."])
            print("closed issue", issue["number"])
