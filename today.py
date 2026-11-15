"""
Builds dark_mode.svg and light_mode.svg for the GitHub profile README.

Static profile info lives in PROFILE below. GitHub stats are fetched from the
GraphQL API using ACCESS_TOKEN (a personal access token) if set, otherwise
GITHUB_TOKEN (the token GitHub Actions provides automatically; public data only).
If no token is available, the last values in stats_cache.json are reused.

Standard library only - no pip installs needed.
"""
import datetime as dt
import html
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
USER_NAME = os.environ.get("USER_NAME", "karanbisht-dev")
TOKEN = os.environ.get("ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
CACHE = ROOT / "stats_cache.json"

WIDTH = 60          # characters in the info panel
ART_X, INFO_X = 15, 455
Y0, DY = 30, 20

# ---------------------------------------------------------------- profile ---
# (key, value) pairs; None = blank spacer line; ("#", title) = section header
PROFILE = [
    ("Status", "Pre-Placement Offer @ Accenture"),
    ("GitHub.Uptime", "{uptime}"),
    ("Host", "Graphic Era Hill University"),
    ("Kernel", "B.Tech, Computer Science & Engineering"),
    ("Batch", "Class of 2027"),
    None,
    ("Languages.Programming", "C++, JavaScript"),
    ("Languages.Frameworks", "React, Vite, Three.js"),
    None,
    ("#", "Experience"),
    ("Accenture", "Intern -> Pre-Placement Offer"),
    ("IIT Patna", "Research Intern"),
    ("AWS Jam", "Top 3"),
    None,
    ("#", "Contact"),
    ("Email.Work", "karan.bisht.work@gmail.com"),
    ("Portfolio", "karan-bisht-portfolio-three.vercel.app"),
    ("GitHub", "karanbisht-dev"),
    None,
    ("#", "GitHub Stats"),
    # stats lines are appended in build_lines()
]

THEMES = {
    "dark": dict(bg="#161b22", text="#c9d1d9", key="#ffa657", value="#a5d6ff",
                 cc="#616e7f", add="#3fb950", dele="#f85149"),
    "light": dict(bg="#f6f8fa", text="#24292f", key="#953800", value="#0a3069",
                  cc="#c2cfde", add="#1a7f37", dele="#cf222e"),
}


# ------------------------------------------------------------------ stats ---
def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": USER_NAME},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.load(r)
    if "errors" in out:
        raise RuntimeError(out["errors"])
    return out["data"]


def fetch_stats():
    d = gql("""query($login:String!){ user(login:$login){
        id createdAt
        owned: repositories(ownerAffiliations:OWNER){ totalCount }
        all: repositories(ownerAffiliations:[OWNER,COLLABORATOR,ORGANIZATION_MEMBER]){ totalCount }
        contributionsCollection{ contributionCalendar{ totalContributions } }
    }}""", {"login": USER_NAME})["user"]
    uid, created = d["id"], d["createdAt"]

    # all-time commits, one year window at a time (API limit)
    start = dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    commits = 0
    while start < now:
        end = min(start + dt.timedelta(days=365), now)
        c = gql("""query($login:String!,$f:DateTime!,$t:DateTime!){ user(login:$login){
            contributionsCollection(from:$f,to:$t){ totalCommitContributions restrictedContributionsCount }}}""",
                {"login": USER_NAME, "f": start.isoformat(), "t": end.isoformat()})
        cc = c["user"]["contributionsCollection"]
        commits += cc["totalCommitContributions"]
        start = end

    # lines of code you authored on the default branch of non-fork repos
    add = dele = 0
    cursor = None
    while True:
        page = gql("""query($login:String!,$after:String){ user(login:$login){
            repositories(first:50, after:$after, isFork:false,
                         ownerAffiliations:[OWNER,COLLABORATOR,ORGANIZATION_MEMBER]){
              pageInfo{ hasNextPage endCursor } nodes{ nameWithOwner }}}}""",
                   {"login": USER_NAME, "after": cursor})["user"]["repositories"]
        for repo in page["nodes"]:
            a, b = loc_for_repo(repo["nameWithOwner"], uid)
            add, dele = add + a, dele + b
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    return dict(created=created, repos=d["owned"]["totalCount"],
                contributed=d["all"]["totalCount"], commits=commits,
                year=d["contributionsCollection"]["contributionCalendar"]["totalContributions"],
                add=add, dele=dele)


def loc_for_repo(name_with_owner, uid):
    owner, name = name_with_owner.split("/")
    add = dele = 0
    cursor = None
    while True:
        r = gql("""query($o:String!,$n:String!,$uid:ID!,$after:String){ repository(owner:$o,name:$n){
            defaultBranchRef{ target{ ... on Commit{
              history(first:100, after:$after, author:{id:$uid}){
                pageInfo{ hasNextPage endCursor } nodes{ additions deletions }}}}}}}""",
                {"o": owner, "n": name, "uid": uid, "after": cursor})["repository"]
        ref = r and r["defaultBranchRef"]
        if not ref:
            return add, dele
        h = ref["target"]["history"]
        for n in h["nodes"]:
            add += n["additions"]
            dele += n["deletions"]
        if not h["pageInfo"]["hasNextPage"]:
            return add, dele
        cursor = h["pageInfo"]["endCursor"]


def uptime(created_iso):
    a = dt.date.fromisoformat(created_iso[:10])
    b = dt.date.today()
    y, m, d = b.year - a.year, b.month - a.month, b.day - a.day
    if d < 0:
        m -= 1
        prev = (b.replace(day=1) - dt.timedelta(days=1))
        d += prev.day
    if m < 0:
        y -= 1
        m += 12
    p = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    return f"{p(y, 'year')}, {p(m, 'month')}, {p(d, 'day')}"


# ------------------------------------------------------------- rendering ---
def seg(text, cls=None):
    return (text, cls)


def field(key, value_segs, width=WIDTH):
    """'. Key: ...... value' padded with dots to exactly `width` chars."""
    vlen = sum(len(t) for t, _ in value_segs)
    dots = width - len(". ") - len(key) - len(": ") - 1 - vlen
    dots = max(dots, 1)
    return [seg(". ", "cc"), seg(key, "key"), seg(":", "cc"),
            seg(" " + "." * dots + " ", "cc"), *value_segs]


def header(title, width=WIDTH):
    left = f"- {title} "
    return [seg(left), seg("—" * (width - len(left) - 3) + "-—-")]


def build_lines(s):
    lines = [[seg("karan", "key"), seg("@"), seg("bisht", "key"), seg(" "),
              seg("—" * (WIDTH - len("karan@bisht ") - 3) + "-—-")]]
    for item in PROFILE:
        if item is None:
            lines.append([seg(". ", "cc")])
        elif item[0] == "#":
            lines.append(header(item[1]))
        else:
            k, v = item
            lines.append(field(k, [seg(v.format(uptime=uptime(s["created"])), "value")]))

    half = 30
    left = field("Repos", [seg(f"{s['repos']:,}", "value"), seg(" {", "cc"),
                           seg("Contributed", "key"), seg(": ", "cc"),
                           seg(f"{s['contributed']:,}", "value"), seg("}", "cc")], half)
    right = field("Commits", [seg(f"{s['commits']:,}", "value")], WIDTH - half - 3 + 2)
    lines.append(left + [seg(" | ", "cc")] + right[1:])  # drop the 2nd leading '. '
    lines.append(field("Contributions.PastYear", [seg(f"{s['year']:,}", "value")]))
    lines.append(field("Lines of Code on GitHub", [
        seg(f"{s['add'] - s['dele']:,}", "value"), seg(" ( ", "cc"),
        seg(f"{s['add']:,}++", "add"), seg(", ", "cc"),
        seg(f"{s['dele']:,}--", "dele"), seg(" )", "cc")]))
    return lines


def tspan(text, cls):
    t = html.escape(text, quote=False)
    return f'<tspan class="{cls}">{t}</tspan>' if cls else t


def render(theme, lines):
    c = THEMES[theme]
    art = (ROOT / f"ascii_{theme}.txt").read_text().rstrip("\n").split("\n")
    rows = max(len(art), len(lines))
    h = Y0 + DY * (rows - 1) + 20
    w = INFO_X + int(WIDTH * 9.6) + 20
    out = [f'<?xml version="1.0" encoding="UTF-8"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,Menlo,\'DejaVu Sans Mono\',monospace" '
           f'width="{w}px" height="{h}px" font-size="16px">',
           "<style>",
           "@font-face { src: local('Consolas'), local('Consolas Bold'); font-family: 'ConsolasFallback'; "
           "font-display: swap; -webkit-size-adjust: 109%; size-adjust: 109%; }",
           f".key {{fill: {c['key']};}} .value {{fill: {c['value']};}} .cc {{fill: {c['cc']};}} "
           f".add {{fill: {c['add']};}} .dele {{fill: {c['dele']};}}",
           "text, tspan {white-space: pre;}",
           "</style>",
           f'<rect width="{w}px" height="{h}px" fill="{c["bg"]}" rx="15"/>',
           f'<text x="{ART_X}" y="{Y0}" fill="{c["text"]}" class="ascii">']
    for i, row in enumerate(art):
        out.append(f'<tspan x="{ART_X}" y="{Y0 + DY * i}">{html.escape(row, quote=False)}</tspan>')
    out.append("</text>")
    out.append(f'<text x="{INFO_X}" y="{Y0}" fill="{c["text"]}">')
    for i, line in enumerate(lines):
        body = "".join(tspan(t, cls) for t, cls in line)
        out.append(f'<tspan x="{INFO_X}" y="{Y0 + DY * i}">{body}</tspan>')
    out.append("</text>")
    out.append("</svg>")
    (ROOT / f"{theme}_mode.svg").write_text("\n".join(out) + "\n")


def main():
    stats = json.loads(CACHE.read_text()) if CACHE.exists() else dict(
        created="2024-08-17T14:36:48Z", repos=0, contributed=0, commits=0, year=0, add=0, dele=0)
    if TOKEN:
        try:
            stats = fetch_stats()
            CACHE.write_text(json.dumps(stats, indent=2) + "\n")
        except Exception as e:  # keep last good numbers rather than failing the build
            print(f"::warning::Could not fetch stats, using cache: {e}")
    else:
        print("No token set - using cached stats.")
    lines = build_lines(stats)
    for theme in THEMES:
        render(theme, lines)
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
