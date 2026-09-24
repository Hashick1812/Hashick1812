"""Render the anime-styled GitHub stats panel for the profile README.

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
    W, H = 1000, 560
    rnd = random.Random(42)
    total, cur, longest = streaks(s["days"])
    out = []
    add = out.append

    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="GitHub stats">')
    add("""<defs>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b1026"/>
<stop offset=".6" stop-color="#1b1640"/><stop offset="1" stop-color="#3a1f4d"/></linearGradient>
<radialGradient id="glow"><stop offset="0" stop-color="#ffd6e8" stop-opacity=".45"/>
<stop offset="1" stop-color="#ffd6e8" stop-opacity="0"/></radialGradient>
<linearGradient id="ttl" x1="0" x2="1"><stop offset="0" stop-color="#7dd3fc"/>
<stop offset=".5" stop-color="#c4b5fd"/><stop offset="1" stop-color="#f9a8d4"/></linearGradient>
<linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f472b6" stop-opacity=".45"/>
<stop offset="1" stop-color="#f472b6" stop-opacity="0"/></linearGradient>
<path id="petal" d="M0 0 C5 -7 13 -5 12 3 C10 10 3 12 0 7 C-3 12 -10 10 -12 3 C-13 -5 -5 -7 0 0Z" fill="#f9a8d4" opacity=".75"/>
<mask id="cres"><rect width="1000" height="560" fill="#fff"/><circle cx="938" cy="58" r="30" fill="#000"/></mask>
</defs>
<style>
text{font-family:'Segoe UI','Hiragino Sans','Noto Sans JP',Helvetica,Arial,sans-serif}
.st{fill:#e2e8f0;animation:tw 3.5s ease-in-out infinite}
@keyframes tw{0%,100%{opacity:.2}50%{opacity:1}}
.pw{animation:fall linear infinite}
@keyframes fall{0%{transform:translate(0,0) rotate(0);opacity:0}8%{opacity:1}100%{transform:translate(var(--dx),600px) rotate(300deg);opacity:.15}}
.card{fill:#0f0c29;fill-opacity:.62;stroke:#c4b5fd;stroke-opacity:.35}
.h{fill:#f9a8d4;font-size:17px;font-weight:700}
.jp{fill:#c4b5fd;font-size:12px;opacity:.85}
.lbl{fill:#cbd5e1;font-size:14px}
.val{fill:#f8fafc;font-size:15px;font-weight:700}
.big{fill:url(#ttl);font-size:34px;font-weight:800}
.small{fill:#94a3b8;font-size:12px}
.line{stroke-dasharray:3000;stroke-dashoffset:3000;animation:draw 3s ease-out forwards}
@keyframes draw{to{stroke-dashoffset:0}}
.bar{animation:grow 1.4s ease-out both;transform-box:fill-box;transform-origin:left}
@keyframes grow{from{transform:scaleX(0)}}
</style>""")
    add(f'<rect width="{W}" height="{H}" rx="18" fill="url(#sky)"/>')
    for _ in range(60):
        add(f'<circle class="st" cx="{rnd.randint(0, W)}" cy="{rnd.randint(0, H)}" '
            f'r="{rnd.choice([.7, 1, 1.3])}" style="animation-delay:{rnd.uniform(0, 4):.1f}s"/>')
    add('<circle cx="920" cy="70" r="80" fill="url(#glow)"/>'
        '<circle cx="920" cy="70" r="34" fill="#fde7f3" mask="url(#cres)"/>')
    add('<path d="M0 560 L0 520 L120 480 L230 515 L360 470 L480 515 L610 485 L740 525 L870 480 '
        'L1000 510 L1000 560Z" fill="#170f33" opacity=".9"/>')

    def card(x, y, w, h, title, jp):
        add(f'<rect class="card" x="{x}" y="{y}" width="{w}" height="{h}" rx="14"/>')
        add(f'<text class="h" x="{x + 20}" y="{y + 30}">{title} <tspan class="jp">{jp}</tspan></text>')

    # stats card
    card(24, 24, 460, 230, "🌸 GitHub Stats", "統計")
    rows = [("⭐", "Total Stars", s["stars"]), ("📝", "Total Commits", s["commits"]),
            ("🔀", "Pull Requests", s["prs"]), ("❗", "Issues", s["issues"]),
            ("📦", "Repositories", s["repos"]), ("👥", "Followers", s["followers"])]
    for i, (icon, label, value) in enumerate(rows):
        y = 78 + i * 29
        add(f'<text class="lbl" x="48" y="{y}">{icon}  {label}</text>')
        add(f'<text class="val" x="300" y="{y}">{fmt(value)}</text>')

    # languages card
    card(508, 24, 468, 230, "💻 Top Languages", "言語")
    langs = sorted(s["langs"].items(), key=lambda kv: -kv[1][0])[:6]
    lang_total = sum(v[0] for _, v in langs) or 1
    x = 532
    for name, (size, color) in langs:
        w = 420 * size / lang_total
        add(f'<rect class="bar" x="{x:.1f}" y="62" width="{max(w, 2):.1f}" height="10" fill="{color}"/>')
        x += w
    for i, (name, (size, color)) in enumerate(langs):
        cx, cy = 540 + (i % 2) * 215, 104 + (i // 2) * 44
        add(f'<circle cx="{cx}" cy="{cy - 5}" r="6" fill="{color}"/>')
        add(f'<text class="lbl" x="{cx + 14}" y="{cy}">{escape(name)}</text>')
        add(f'<text class="small" x="{cx + 14}" y="{cy + 17}">{100 * size / lang_total:.1f}%</text>')
    if not langs:
        add('<text class="small" x="532" y="110">No language data yet</text>')

    # streak card
    card(24, 272, 952, 104, "🔥 Streak", "連続")
    for i, (label, value) in enumerate([("Total Contributions", total),
                                         ("Current Streak", days_label(cur)),
                                         ("Longest Streak", days_label(longest))]):
        cx = 180 + i * 320
        add(f'<text class="big" x="{cx}" y="342" text-anchor="middle">{value}</text>')
        add(f'<text class="small" x="{cx}" y="362" text-anchor="middle">{label}</text>')

    # activity graph: last 30 days
    card(24, 390, 952, 150, "📈 Activity · last 30 days", "活動")
    last = list(s["days"].items())[-30:]
    peak = max([c for _, c in last] + [1])
    gx, gy, gw, gh = 60, 436, 890, 80
    pts = [(gx + i * gw / max(len(last) - 1, 1), gy + gh - gh * c / peak) for i, (_, c) in enumerate(last)]
    if pts:
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        add(f'<polygon points="{gx},{gy + gh} {poly} {pts[-1][0]:.1f},{gy + gh}" fill="url(#area)"/>')
        add(f'<polyline class="line" points="{poly}" fill="none" stroke="#f9a8d4" stroke-width="2.5" '
            f'stroke-linejoin="round"/>')
        for x, y in pts:
            add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.8" fill="#c4b5fd"/>')
        add(f'<text class="small" x="{gx}" y="{gy + gh + 17}">{last[0][0]}</text>')
        add(f'<text class="small" x="{gx + gw}" y="{gy + gh + 17}" text-anchor="end">{last[-1][0]}</text>')
        add(f'<text class="small" x="{gx + gw}" y="{gy - 8}" text-anchor="end">peak {peak}/day</text>')

    for _ in range(16):
        add(f'<g transform="translate({rnd.randint(20, W - 20)} -20) scale({rnd.uniform(.6, 1.2):.2f})">'
            f'<g class="pw" style="--dx:{rnd.randint(-120, 40)}px;animation-duration:{rnd.uniform(9, 16):.1f}s;'
            f'animation-delay:{-rnd.uniform(0, 16):.1f}s"><use href="#petal"/></g></g>')
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
