"""Render the minimal GitHub stats panel for the profile README.

Runs in .github/workflows/stats.yml. Public card services (github-readme-stats,
github-readme-activity-graph) are rate-limited and often render as broken
images, so the data is fetched here with the workflow token and drawn locally.

Usage: GITHUB_TOKEN=... python scripts/generate_stats.py USERNAME OUTPUT.svg
       python scripts/generate_stats.py --demo OUTPUT.svg   (sample data)
"""

import datetime as dt
import json
import os
import random
import sys
import urllib.request
from html import escape

API = "https://api.github.com/graphql"

USER_QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

YEAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def gql(token, query, variables):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if "errors" in body:
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]["user"]


def fetch(login, token):
    user = gql(token, USER_QUERY, {"login": login})
    today = dt.date.today()
    start = dt.date.fromisoformat(user["createdAt"][:10])
    days, commits = {}, 0
    year_start = start
    while year_start <= today:
        year_end = min(dt.date(year_start.year, 12, 31), today)
        cc = gql(token, YEAR_QUERY, {
            "login": login,
            "from": f"{year_start}T00:00:00Z",
            "to": f"{year_end}T23:59:59Z",
        })["contributionsCollection"]
        commits += cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
        for week in cc["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
        year_start = dt.date(year_start.year + 1, 1, 1)

    langs = {}
    for repo in user["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            size, color = langs.get(name, (0, None))
            langs[name] = (size + edge["size"], edge["node"]["color"] or "#c4b5fd")
    return {
        "commits": commits,
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "repos": user["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in user["repositories"]["nodes"]),
        "followers": user["followers"]["totalCount"],
        "langs": langs,
        "days": dict(sorted(days.items())),
    }


def demo():
    rnd = random.Random(3)
    today = dt.date.today()
    days = {}
    for i in range(400, -1, -1):
        d = today - dt.timedelta(days=i)
        days[d.isoformat()] = rnd.choice([0, 0, 1, 2, 3, 5, 8])
    return {
        "commits": 312, "prs": 4, "issues": 2, "repos": 11, "stars": 3, "followers": 6,
        "langs": {"Jupyter Notebook": (900000, "#DA5B0B"), "Python": (400000, "#3572A5"),
                  "HTML": (60000, "#e34c26"), "TSQL": (30000, "#e38c00"), "R": (8000, "#198CE7")},
        "days": days,
    }


def streaks(days):
    today = dt.date.today().isoformat()
    items = [(d, c) for d, c in days.items() if d <= today]
    longest = run = 0
    for _, count in items:
        run = run + 1 if count else 0
        longest = max(longest, run)
    current = 0
    for i, (d, count) in enumerate(reversed(items)):
        if count:
            current += 1
        elif i == 0:
            continue  # today may simply not have contributions yet
        else:
            break
    total = sum(c for _, c in items)
    return total, current, longest


def fmt(n):
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def days_label(n):
    return f"{n} day" if n == 1 else f"{n} days"


def render(s):
    W, H = 1000, 420
    total, cur, longest = streaks(s["days"])
    out = []
    add = out.append
    mono = "'JetBrains Mono','SFMono-Regular',Menlo,Consolas,monospace"

    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="GitHub stats">')
    add(f"""<style>
text{{font-family:{mono}}}
.k{{fill:#8b949e;font-size:11px;letter-spacing:1.5px}}
.v{{fill:#f0f6fc;font-size:30px;font-weight:700}}
.h{{fill:#22d3ee;font-size:12px;letter-spacing:2px}}
.t{{fill:#c9d1d9;font-size:13px}}
.m{{fill:#6e7681;font-size:11px}}
</style>""")
    add(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10" fill="#0d1117" stroke="#30363d"/>')

    # KPI row
    kpis = [("COMMITS", fmt(s["commits"])), ("CONTRIBUTIONS", fmt(total)),
            ("REPOSITORIES", fmt(s["repos"])), ("PULL REQUESTS", fmt(s["prs"])),
            ("CURRENT STREAK", days_label(cur)), ("LONGEST STREAK", days_label(longest))]
    cw = (W - 48) / len(kpis)
    for i, (k, v) in enumerate(kpis):
        x = 24 + i * cw
        if i:
            add(f'<line x1="{x:.1f}" y1="30" x2="{x:.1f}" y2="98" stroke="#21262d"/>')
        add(f'<text class="k" x="{x + 14:.1f}" y="46">{k}</text>')
        size = 30 if len(v) < 8 else 22
        add(f'<text class="v" x="{x + 14:.1f}" y="86" style="font-size:{size}px">{v}</text>')
    add(f'<line x1="24" y1="124" x2="{W - 24}" y2="124" stroke="#21262d"/>')

    # languages
    add('<text class="h" x="38" y="156">TOP LANGUAGES</text>')
    langs = sorted(s["langs"].items(), key=lambda kv: -kv[1][0])[:5]
    lang_total = sum(v[0] for _, v in langs) or 1
    for i, (name, (size, _)) in enumerate(langs):
        y = 190 + i * 40
        pct = 100 * size / lang_total
        add(f'<text class="t" x="38" y="{y}">{escape(name)}</text>')
        add(f'<text class="m" x="440" y="{y}" text-anchor="end">{pct:.1f}%</text>')
        add(f'<rect x="38" y="{y + 9}" width="402" height="4" rx="2" fill="#21262d"/>')
        add(f'<rect x="38" y="{y + 9}" width="{max(402 * pct / 100, 3):.1f}" height="4" rx="2" '
            'fill="#22d3ee"/>')
    if not langs:
        add('<text class="m" x="38" y="190">No language data yet</text>')

    add(f'<line x1="490" y1="146" x2="490" y2="{H - 30}" stroke="#21262d"/>')

    # activity: last 30 days as columns
    add('<text class="h" x="520" y="156">ACTIVITY · LAST 30 DAYS</text>')
    last = list(s["days"].items())[-30:]
    peak = max([c for _, c in last] + [1])
    gx, gy, gw, gh = 520, 180, 440, 176
    bw = gw / max(len(last), 1)
    for i, (_, c) in enumerate(last):
        h = gh * c / peak
        x = gx + i * bw
        if c:
            add(f'<rect x="{x + 1.5:.1f}" y="{gy + gh - h:.1f}" width="{bw - 3:.1f}" height="{h:.1f}" '
                'rx="1.5" fill="#22d3ee"/>')
        else:
            add(f'<rect x="{x + 1.5:.1f}" y="{gy + gh - 2}" width="{bw - 3:.1f}" height="2" fill="#21262d"/>')
    if last:
        add(f'<text class="m" x="{gx}" y="{gy + gh + 22}">{last[0][0]}</text>')
        add(f'<text class="m" x="{gx + gw}" y="{gy + gh + 22}" text-anchor="end">{last[-1][0]}</text>')
        add(f'<text class="m" x="{gx + gw}" y="{gy - 6}" text-anchor="end">max {peak}/day</text>')
    add("</svg>")
    return "\n".join(out)


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    who, path = sys.argv[1], sys.argv[2]
    data = demo() if who == "--demo" else fetch(who, os.environ["GITHUB_TOKEN"])
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(render(data))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
