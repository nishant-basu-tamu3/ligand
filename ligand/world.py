"""Simulated company 'world' and 37 tools across 6 MCP-style servers.

Deterministic given a seed. Tools are intentionally overlapping / confusable
(three different 'get user' tools, four different 'search' tools, 'list' vs 'get', etc.)
and return realistically bulky records (urls, timestamps, counters) like real APIs.
"""
from __future__ import annotations

import fnmatch
import hashlib
import random
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Param:
    name: str
    desc: str
    required: bool = False
    type: str = "string"


@dataclass
class Out:
    name: str
    desc: str


@dataclass
class Tool:
    server: str
    name: str
    desc: str
    params: list[Param]
    outs: list[Out]
    kind: str  # "list" | "object"
    fn: Callable[[dict], Any]
    writes: bool = False

    @property
    def fq(self) -> str:
        return f"{self.server}.{self.name}"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {p.name: {"type": p.type, "description": p.desc} for p in self.params},
            "required": [p.name for p in self.params if p.required],
        }

    def output_schema(self) -> dict:
        props = {o.name: {"description": o.desc} for o in self.outs}
        item = {"type": "object", "properties": props}
        if self.kind == "list":
            return {"type": "object", "properties": {"items": {"type": "array", "items": item}}}
        return item

    def mcp_def(self) -> dict:
        """What an MCP client would put in the model's context for this tool."""
        return {"name": self.fq, "description": self.desc, "inputSchema": self.input_schema()}


PEOPLE = [
    ("sanjay", "Sanjay Rao", "Staff Engineer", "Bengaluru"),
    ("priya", "Priya Nair", "Engineering Manager", "Bengaluru"),
    ("mei", "Mei Tanaka", "Backend Engineer", "Tokyo"),
    ("tom", "Tom Becker", "SRE", "Berlin"),
    ("ana", "Ana Silva", "Frontend Engineer", "Lisbon"),
    ("omar", "Omar Haddad", "Data Engineer", "Dubai"),
    ("lena", "Lena Fischer", "Product Manager", "Munich"),
    ("raj", "Raj Patel", "Account Executive", "Mumbai"),
    ("chloe", "Chloe Martin", "Designer", "Paris"),
    ("dev", "Dev Sharma", "Backend Engineer", "Delhi"),
    ("nina", "Nina Petrova", "QA Engineer", "Sofia"),
    ("jack", "Jack Reilly", "Solutions Engineer", "Dublin"),
]
LOGINS = [p[0] for p in PEOPLE]
REPOS = ["acme/api", "acme/web", "acme/infra"]
REPO_LANG = {"acme/api": "Python", "acme/web": "TypeScript", "acme/infra": "HCL"}
REPO_DESC = {
    "acme/api": "Public REST API and background workers",
    "acme/web": "Customer facing web application",
    "acme/infra": "Terraform modules and deployment tooling",
}
PR_TITLES = {
    "acme/api": ["Add rate limiting middleware", "Fix pagination off by one", "Migrate auth to JWT", "Cache hot queries in Redis",
                 "Retry failed webhooks", "Add bulk export endpoint", "Remove deprecated v1 routes", "Speed up search index",
                 "Harden input validation", "Add audit log", "Upgrade ORM", "Fix timezone bug in reports", "Add health probes",
                 "Split billing worker"],
    "acme/web": ["Redesign settings page", "Fix dark mode contrast", "Lazy load dashboard charts", "Add keyboard shortcuts",
                 "Fix Safari date picker", "Migrate to React 19", "Add onboarding checklist", "Improve empty states",
                 "Reduce bundle size", "Fix infinite scroll jump", "Add CSV download", "Localize billing page", "Fix focus trap",
                 "Add session timeout modal"],
    "acme/infra": ["Add staging autoscaling", "Rotate database credentials", "Move logs to cold storage", "Add canary deploys",
                   "Fix terraform drift", "Add WAF rules", "Upgrade Kubernetes nodes", "Add cost tags", "Tighten IAM roles",
                   "Add backup verification", "Move DNS to new zone", "Add alert routing", "Fix flaky deploy job", "Add region failover"],
}
ISSUE_TITLES = ["Login fails on slow networks", "Export times out for large accounts", "Wrong totals in monthly report",
                "Webhook signature mismatch", "Search ignores accents", "Dashboard flickers on refresh", "Password reset email delayed",
                "Memory leak in worker", "Incorrect rounding in invoices", "Missing audit entries", "Slow startup in staging",
                "Broken link in onboarding email", "Duplicate notifications", "Timezone shown incorrectly"]
LABELS = ["bug", "feature", "docs", "perf", "security"]
COMMIT_MSGS = ["fix: handle null customer id", "feat: add retry with backoff", "chore: bump dependencies", "refactor: extract billing module",
               "docs: update runbook", "fix: race in job scheduler", "perf: batch database writes", "test: add integration suite",
               "feat: expose usage metrics", "fix: correct tax calculation", "ci: cache build layers", "security: rotate signing key"]
CHANNELS = [("eng", "Engineering discussion", 9), ("incidents", "Live incident coordination", 12),
            ("sales", "Deals and pipeline", 7), ("random", "Everything else", 12)]
SLACK_TEXTS = {
    "eng": ["Merged the migration branch, please pull", "Refactor of the billing module is ready for review",
            "Deploy to staging is green", "Who owns the cache layer now?", "Heads up: schema migration tonight",
            "Updated the style guide for API errors", "Tests are flaky again on CI", "New hire onboarding docs are live",
            "Reminder: code freeze on Friday", "Pairing session on the auth rewrite at 3", "Benchmark results are in the wiki",
            "Dependency upgrade landed"],
    "incidents": ["Outage in eu-west started 09:12 UTC", "Latency back to normal after rollback", "Rollback of release 4.18 complete",
                  "Postmortem draft for the outage is in Notion", "Database failover triggered automatically",
                  "Paging on call for elevated error rates", "Outage root cause: expired certificate",
                  "Mitigation applied, monitoring latency", "Customer impact limited to API traffic",
                  "Status page updated for the outage", "Alert noise reduced after tuning thresholds", "Follow ups assigned from the outage review"],
    "sales": ["Renewal for Globex closed this morning", "Pricing question from Initech about volume tiers",
              "Pilot with Umbrella starts Monday", "Need legal review on the Hooli contract", "Soylent asked for a security questionnaire",
              "Quarter end push: three deals in negotiation", "Wayne Enterprises wants a demo of reporting"],
    "random": ["Lunch at the new ramen place?", "Offsite photos are up", "Anyone watching the match tonight?",
               "Coffee machine on 3 is fixed", "Happy birthday Nina!", "Book club picks for next month", "Who left the umbrella?",
               "Team offsite agenda is posted", "Friday playlist thread", "Parking lot is closed tomorrow", "Standing desk recommendations?",
               "Bike to work week starts Monday"],
}
NOTION_DBS = [("db_roadmap", "Roadmap"), ("db_runbooks", "Runbooks"), ("db_meetings", "Meeting Notes")]
NOTION_TITLES = {
    "db_roadmap": ["Usage based billing", "Self serve onboarding", "Public API v2", "SSO and SCIM", "Mobile app beta", "Data residency"],
    "db_runbooks": ["Database failover", "Certificate rotation", "Queue backlog recovery", "Cache flush procedure", "DNS cutover", "Secrets rotation"],
    "db_meetings": ["Q4 planning notes", "Customer advisory board notes", "Architecture review notes", "Hiring sync notes",
                    "Security review notes", "Design critique notes"],
}
STATUSES = ["draft", "in progress", "done"]
EVENT_TITLES = ["Sprint planning", "Incident review", "Customer sync", "Design critique", "Roadmap review", "Quarterly business review",
                "Demo prep", "Architecture review", "Hiring panel", "Security review", "Pipeline review", "Onboarding session",
                "Retro", "Budget check in", "Vendor call"]
ROOMS = ["Aspen", "Birch", "Cedar", "Dogwood", "Elm"]
COMPANIES = [("Globex", "Manufacturing", 4200, "US"), ("Initech", "Software", 800, "US"), ("Umbrella", "Pharma", 12000, "UK"),
             ("Hooli", "Technology", 25000, "US"), ("Soylent", "Food", 3100, "CA"), ("Wayne Enterprises", "Conglomerate", 60000, "US"),
             ("Stark Industries", "Defense", 40000, "US"), ("Wonka", "Confectionery", 950, "UK")]
CONTACT_FIRST = ["Alice", "Bruno", "Carla", "Daniel", "Elena", "Farid", "Grace", "Hugo", "Isla", "Jonas", "Kira", "Leo", "Maya", "Noah",
                 "Olga", "Pavel", "Quinn", "Rosa", "Sven", "Tara", "Uma", "Victor", "Wen", "Yara"]
CONTACT_LAST = ["Adams", "Brandt", "Costa", "Dubois", "Eriksen", "Farouk", "Gomez", "Holm", "Ivanov", "Jensen", "Kaur", "Lopez", "Meyer",
                "Novak", "Ortiz", "Park", "Quist", "Rossi", "Sato", "Toure", "Ueda", "Vargas", "Wong", "Yilmaz"]
STAGES = ["lead", "qualified", "proposal", "negotiation", "closed_won", "closed_lost"]
TITLES = ["VP Engineering", "Head of Procurement", "CTO", "IT Director", "Operations Lead", "Product Owner"]
FILE_SPECS = [
    ("/docs/handbook.md", "Company handbook. Values, benefits, time off policy."),
    ("/docs/onboarding.md", "Onboarding guide. Accounts, laptops, first week checklist."),
    ("/docs/runbook-db-failover.md", "Runbook for database failover. Steps to promote the replica."),
    ("/docs/security-policy.md", "Security policy. Access reviews, key rotation, incident response."),
    ("/reports/q3-revenue.csv", "month,revenue\nJul,410\nAug,432\nSep,455"),
    ("/reports/q3-churn.csv", "month,churn\nJul,2.1\nAug,1.9\nSep,2.4"),
    ("/reports/incident-2026-10-03.md", "Incident summary. Expired certificate caused an outage for 41 minutes."),
    ("/reports/hiring-plan.md", "Hiring plan for Q4. Three backend roles and one designer."),
    ("/src/api/server.py", "def create_app():\n    app = App()\n    return app"),
    ("/src/api/auth.py", "def verify_token(token):\n    return decode(token)"),
    ("/src/web/app.tsx", "export default function App() { return <Shell /> }"),
    ("/src/web/settings.tsx", "export function Settings() { return <Panel /> }"),
    ("/infra/terraform/main.tf", "module \"vpc\" { source = \"./vpc\" }"),
    ("/infra/terraform/variables.tf", "variable \"region\" { default = \"eu-west-1\" }"),
    ("/infra/scripts/deploy.sh", "#!/bin/sh\nterraform apply -auto-approve"),
    ("/infra/scripts/rotate-keys.sh", "#!/bin/sh\naws kms rotate-key"),
    ("/notes/roadmap-draft.txt", "Roadmap draft: billing, onboarding, public API v2."),
    ("/notes/standup-2026-10-19.txt", "Standup notes. Blocked on certificate renewal."),
    ("/notes/ideas.txt", "Ideas: usage dashboards, webhook replay, audit export."),
    ("/archive/q2-report.pdf", "binary pdf placeholder"),
    ("/archive/old-handbook.md", "Old handbook content."),
    ("/archive/contracts-2025.zip", "binary zip placeholder"),
]
DATES = [f"2026-10-{d:02d}" for d in range(1, 20)]


def _sha(rng: random.Random) -> str:
    return hashlib.md5(str(rng.random()).encode()).hexdigest()[:7]


class World:
    def __init__(self, seed: int = 0):
        self.seed = seed
        rng = random.Random(seed)
        self.people = {l: {"login": l, "name": n, "title": t, "location": loc, "email": f"{l}@acme.io",
                           "slack_id": f"U{100 + i}", "company": "Acme"} for i, (l, n, t, loc) in enumerate(PEOPLE)}
        self.slack_to_login = {p["slack_id"]: l for l, p in self.people.items()}
        # github
        self.prs, self.issues, self.commits = [], [], []
        for repo in REPOS:
            titles = PR_TITLES[repo][:]
            rng.shuffle(titles)
            for i, t in enumerate(titles[:12]):
                state = rng.choice(["open", "open", "merged", "merged", "merged", "closed"])
                created = rng.choice(DATES[:14])
                pr = {"number": 100 + i * 3 + rng.randint(0, 2), "title": t, "author": rng.choice(LOGINS), "state": state,
                      "repo": repo, "created_at": created, "updated_at": rng.choice(DATES[10:]),
                      "merged_at": rng.choice(DATES[10:]) if state == "merged" else None,
                      "additions": rng.randint(3, 900), "deletions": rng.randint(0, 400), "comments": rng.randint(0, 14),
                      "reviewers": rng.sample(LOGINS, 2), "body": f"{t}. See design doc for context and rollout plan."}
                pr["url"] = f"https://api.github.example/repos/{repo}/pulls/{pr['number']}"
                self.prs.append(pr)
            seen = set()
            for i, t in enumerate(rng.sample(ISSUE_TITLES, 9)):
                n = 400 + i * 2 + rng.randint(0, 1)
                if n in seen:
                    n += 7
                seen.add(n)
                iss = {"number": n, "title": t, "state": rng.choice(["open", "open", "closed"]), "repo": repo,
                       "assignee": rng.choice(LOGINS + [None]), "labels": rng.sample(LABELS, rng.randint(1, 2)),
                       "created_at": rng.choice(DATES[:12]), "updated_at": rng.choice(DATES[10:]), "comments": rng.randint(0, 9),
                       "body": f"{t}. Reported by a customer; reproduction steps attached."}
                iss["url"] = f"https://api.github.example/repos/{repo}/issues/{n}"
                self.issues.append(iss)
            for i in range(10):
                sha = _sha(rng)
                self.commits.append({"sha": sha, "message": rng.choice(COMMIT_MSGS), "author": rng.choice(LOGINS), "repo": repo,
                                     "date": rng.choice(DATES), "url": f"https://api.github.example/repos/{repo}/commits/{sha}"})
        self.repos = [{"full_name": r, "description": REPO_DESC[r], "language": REPO_LANG[r], "stars": rng.randint(5, 900),
                      "default_branch": "main", "open_issues": rng.randint(2, 40), "updated_at": "2026-10-18"} for r in REPOS]
        # slack
        self.channels = [{"name": n, "topic": t, "members": m, "created_at": "2025-03-01"} for n, t, m in CHANNELS]
        self.messages = []
        for n, _, _ in CHANNELS:
            texts = SLACK_TEXTS[n][:]
            rng.shuffle(texts)
            for i, tx in enumerate(texts):
                uid = self.people[rng.choice(LOGINS)]["slack_id"]
                self.messages.append({"channel": n, "ts": f"{rng.choice(DATES)}T{rng.randint(8, 18):02d}:{rng.randint(0, 59):02d}",
                                      "user_id": uid, "text": tx, "reactions": rng.randint(0, 6)})
        # notion
        self.databases = [{"database_id": i, "name": n, "page_count": 6} for i, n in NOTION_DBS]
        self.pages = []
        for dbid, dbname in NOTION_DBS:
            for t in NOTION_TITLES[dbid]:
                self.pages.append({"page_id": f"pg_{rng.randint(1000, 9999)}", "title": t, "database_id": dbid, "database": dbname,
                                   "owner_email": self.people[rng.choice(LOGINS)]["email"], "status": rng.choice(STATUSES),
                                   "updated_at": rng.choice(DATES), "content": f"{t}. Owner notes and links go here."})
        # calendar
        self.events = []
        days = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"]
        used = set()
        titles = EVENT_TITLES[:]
        rng.shuffle(titles)
        for i in range(24):
            title = titles[i % len(titles)] + (f" #{i // len(titles) + 1}" if i >= len(titles) else "")
            att = [self.people[l]["email"] for l in rng.sample(LOGINS, rng.randint(2, 4))]
            date, hour = rng.choice(days), rng.randint(9, 16)
            key = (date, hour, att[0])
            if key in used:
                continue
            used.add(key)
            self.events.append({"event_id": f"ev_{200 + i}", "title": title, "date": date, "start": f"{hour:02d}:00", "end": f"{hour + 1:02d}:00",
                                "room": rng.choice(ROOMS), "organizer": att[0], "attendees": att,
                                "description": f"{title}. Agenda shared in advance."})
        # files
        self.files = {}
        for p, c in FILE_SPECS:
            self.files[p] = {"path": p, "content": c, "size": len(c) * rng.randint(3, 40), "modified": rng.choice(DATES),
                             "owner": rng.choice(LOGINS), "mime": "text/plain"}
        # crm
        self.companies = [{"name": n, "industry": i, "employees": e, "country": c} for n, i, e, c in COMPANIES]
        self.contacts = []
        k = 0
        for comp in self.companies:
            for _ in range(3):
                first, last = CONTACT_FIRST[k % 24], CONTACT_LAST[(k * 5 + 3) % 24]
                dom = comp["name"].lower().replace(" ", "") + ".com"
                self.contacts.append({"contact_id": f"c_{300 + k}", "name": f"{first} {last}", "email": f"{first.lower()}.{last.lower()}@{dom}",
                                      "phone": f"+1-555-{rng.randint(1000, 9999)}", "company": comp["name"], "title": rng.choice(TITLES)})
                k += 1
        self.deals = []
        owners = [self.people[l]["email"] for l in ("raj", "jack", "lena")]
        comps = [c["name"] for c in self.companies]
        order = comps + rng.sample(comps, 4)
        for i, cn in enumerate(order):
            ct = rng.choice([c for c in self.contacts if c["company"] == cn])
            self.deals.append({"deal_id": f"d_{500 + i}", "company": cn, "stage": rng.choice(STAGES), "amount": rng.randint(8, 400) * 1000,
                               "owner_email": rng.choice(owners), "contact_id": ct["contact_id"], "close_date": rng.choice(DATES),
                               "notes": f"Deal with {cn}. Champion identified; procurement engaged."})

    # ----------------------------------------------------------------- tools
    def tools(self) -> list[Tool]:
        W = self
        T: list[Tool] = []

        def add(server, name, desc, params, outs, kind, fn, writes=False):
            T.append(Tool(server, name, desc, params, outs, kind, fn, writes))

        P = Param
        O = Out

        def pr_outs(extra=()):
            return [O("number", "pull request number"), O("title", "pull request title"), O("author", "github login of the pull request author"),
                    O("state", "pull request state: open, closed or merged"), O("repo", "repository full name"),
                    O("created_at", "creation date"), O("updated_at", "last update date"), O("merged_at", "date the pull request was merged"),
                    O("additions", "lines added"), O("deletions", "lines removed"), O("comments", "comment count"), O("url", "api url")] + list(extra)

        def iss_outs(extra=()):
            return [O("number", "issue number"), O("title", "issue title"), O("state", "issue state: open or closed"),
                    O("assignee", "github login of the person the issue is assigned to"), O("labels", "issue labels"),
                    O("repo", "repository full name"), O("created_at", "creation date"), O("updated_at", "last update date"),
                    O("comments", "comment count"), O("url", "api url")] + list(extra)

        def strip(d, drop):
            return {k: v for k, v in d.items() if k not in drop}

        # ---- github
        add("github", "list_repositories", "List repositories owned by an organization or user.",
            [P("org", "organization or user login that owns the repositories")],
            [O("full_name", "repository full name"), O("description", "repository description"), O("language", "primary programming language"),
             O("stars", "star count"), O("default_branch", "default branch"), O("open_issues", "open issue count"), O("updated_at", "last update date")],
            "list", lambda a: [dict(r) for r in W.repos])
        add("github", "get_repository", "Get details of one repository including its primary language and description.",
            [P("repo", "repository full name like owner/name", True)],
            [O("full_name", "repository full name"), O("description", "repository description"), O("language", "primary programming language"),
             O("stars", "star count"), O("default_branch", "default branch"), O("open_issues", "open issue count"), O("updated_at", "last update date")],
            "object", lambda a: next((dict(r) for r in W.repos if r["full_name"] == a.get("repo")), {}))
        add("github", "list_branches", "List branches of a repository.",
            [P("repo", "repository full name like owner/name", True)],
            [O("name", "branch name"), O("sha", "head commit sha"), O("protected", "whether the branch is protected")],
            "list", lambda a: [{"name": "main", "sha": "a1b2c3d", "protected": True}, {"name": "release", "sha": "d4e5f6a", "protected": True},
                               {"name": "dev", "sha": "0f9e8d7", "protected": False}] if a.get("repo") in REPOS else [])
        add("github", "list_pull_requests", "List pull requests in a repository, optionally filtered by state or author.",
            [P("repo", "repository full name like owner/name", True), P("state", "pull request state: open, closed or merged"),
             P("author", "github login of the pull request author")],
            pr_outs(), "list",
            lambda a: [strip(p, {"reviewers", "body"}) for p in W.prs if p["repo"] == a.get("repo")
                       and (not a.get("state") or p["state"] == a["state"]) and (not a.get("author") or p["author"] == a["author"])])
        add("github", "get_pull_request", "Get one pull request by number, including reviewers and description.",
            [P("repo", "repository full name like owner/name", True), P("number", "pull request number", True, "integer")],
            pr_outs([O("reviewers", "github logins of reviewers"), O("body", "pull request description")]), "object",
            lambda a: next((dict(p) for p in W.prs if p["repo"] == a.get("repo") and p["number"] == int(a.get("number", -1))), {}))
        add("github", "list_issues", "List issues in a repository, optionally filtered by state, assignee or label.",
            [P("repo", "repository full name like owner/name", True), P("state", "issue state: open or closed"),
             P("assignee", "github login of the assignee"), P("label", "issue label name")],
            iss_outs(), "list",
            lambda a: [strip(i, {"body"}) for i in W.issues if i["repo"] == a.get("repo") and (not a.get("state") or i["state"] == a["state"])
                       and (not a.get("assignee") or i["assignee"] == a["assignee"]) and (not a.get("label") or a["label"] in i["labels"])])
        add("github", "get_issue", "Get one issue by number, including its description and assignee.",
            [P("repo", "repository full name like owner/name", True), P("number", "issue number", True, "integer")],
            iss_outs([O("body", "issue description")]), "object",
            lambda a: next((dict(i) for i in W.issues if i["repo"] == a.get("repo") and i["number"] == int(a.get("number", -1))), {}))
        add("github", "list_commits", "List commits in a repository, optionally by author or since a date.",
            [P("repo", "repository full name like owner/name", True), P("author", "github login of the commit author"),
             P("since", "only commits on or after this date")],
            [O("sha", "commit sha"), O("message", "commit message"), O("author", "github login of the commit author"),
             O("date", "commit date"), O("repo", "repository full name"), O("url", "api url")], "list",
            lambda a: [dict(c) for c in W.commits if c["repo"] == a.get("repo") and (not a.get("author") or c["author"] == a["author"])
                       and (not a.get("since") or c["date"] >= a["since"])])
        add("github", "search_code", "Search source code across repositories for a text query.",
            [P("query", "text to search for in code", True), P("repo", "limit to one repository")],
            [O("path", "file path of the match"), O("repo", "repository full name"), O("line", "line number"), O("snippet", "matching code snippet")],
            "list", lambda a: [{"path": p, "repo": "acme/api", "line": 12, "snippet": f["content"][:60]} for p, f in W.files.items()
                               if p.startswith("/src") and str(a.get("query", "")).lower() in f["content"].lower()])
        add("github", "get_github_user", "Get a github user profile by login: name, email, location.",
            [P("login", "github login username", True)],
            [O("login", "github login username"), O("name", "full name"), O("email", "email address"), O("location", "city"),
             O("company", "employer"), O("followers", "follower count")], "object",
            lambda a: ({k: W.people[a["login"]][k] for k in ("login", "name", "email", "location", "company")} | {"followers": 40}) if a.get("login") in W.people else {})

        # ---- slack
        add("slack", "list_channels", "List slack channels in the workspace.", [],
            [O("name", "channel name"), O("topic", "channel topic"), O("members", "member count"), O("created_at", "creation date")], "list",
            lambda a: [dict(c) for c in W.channels])
        add("slack", "get_channel_info", "Get details of a slack channel: topic and member count.",
            [P("channel", "channel name", True)],
            [O("name", "channel name"), O("topic", "channel topic"), O("members", "member count"), O("created_at", "creation date")], "object",
            lambda a: next((dict(c) for c in W.channels if c["name"] == str(a.get("channel", "")).lstrip("#")), {}))
        add("slack", "get_channel_history", "Get the most recent messages posted in a slack channel.",
            [P("channel", "channel name", True), P("limit", "maximum number of messages", False, "integer")],
            [O("ts", "message timestamp"), O("user_id", "slack user id of the author"), O("text", "message text"), O("reactions", "reaction count")],
            "list", lambda a: sorted([strip(m, {"channel"}) for m in W.messages if m["channel"] == str(a.get("channel", "")).lstrip("#")],
                                     key=lambda m: m["ts"], reverse=True)[: int(a.get("limit") or 5)])
        add("slack", "search_messages", "Search slack messages by keyword across channels.",
            [P("query", "keyword or phrase to search for", True), P("channel", "limit to one channel")],
            [O("channel", "channel name"), O("ts", "message timestamp"), O("user_id", "slack user id of the author"), O("text", "message text"),
             O("reactions", "reaction count")], "list",
            lambda a: [dict(m) for m in W.messages if str(a.get("query", "")).lower() in m["text"].lower()
                       and (not a.get("channel") or m["channel"] == str(a["channel"]).lstrip("#"))])
        add("slack", "get_user_profile", "Get a slack user profile by user id: name, email, title.",
            [P("user_id", "slack user id", True)],
            [O("user_id", "slack user id"), O("name", "full name"), O("email", "email address"), O("title", "job title"), O("timezone", "timezone")],
            "object", lambda a: ({"user_id": a["user_id"], "name": W.people[W.slack_to_login[a["user_id"]]]["name"],
                                  "email": W.people[W.slack_to_login[a["user_id"]]]["email"], "title": W.people[W.slack_to_login[a["user_id"]]]["title"],
                                  "timezone": "UTC"} if a.get("user_id") in W.slack_to_login else {}))
        add("slack", "post_message", "Post a message to a slack channel.",
            [P("channel", "channel name", True), P("text", "message text", True)], [O("ts", "message timestamp")], "object",
            lambda a: {"ts": "now"}, writes=True)

        # ---- notion
        add("notion", "search_pages", "Search notion pages by title keyword.",
            [P("query", "keyword to search for in page titles", True)],
            [O("page_id", "notion page id"), O("title", "page title"), O("database", "name of the database the page belongs to"),
             O("updated_at", "last update date")], "list",
            lambda a: [{"page_id": p["page_id"], "title": p["title"], "database": p["database"], "updated_at": p["updated_at"]}
                       for p in W.pages if str(a.get("query", "")).lower() in p["title"].lower()])
        add("notion", "get_page", "Get a notion page by id including owner, status and content.",
            [P("page_id", "notion page id", True)],
            [O("page_id", "notion page id"), O("title", "page title"), O("owner_email", "email address of the page owner"),
             O("status", "page status: draft, in progress or done"), O("updated_at", "last update date"), O("content", "page content")],
            "object", lambda a: next(({k: p[k] for k in ("page_id", "title", "owner_email", "status", "updated_at", "content")} for p in W.pages
                                      if p["page_id"] == a.get("page_id")), {}))
        add("notion", "list_databases", "List notion databases in the workspace.", [],
            [O("database_id", "notion database id"), O("name", "database name"), O("page_count", "number of pages")], "list",
            lambda a: [dict(d) for d in W.databases])
        add("notion", "query_database", "Query the pages of a notion database, optionally by status.",
            [P("database_id", "notion database id", True), P("status", "page status: draft, in progress or done")],
            [O("page_id", "notion page id"), O("title", "page title"), O("status", "page status"), O("owner_email", "email address of the page owner"),
             O("updated_at", "last update date")], "list",
            lambda a: [{k: p[k] for k in ("page_id", "title", "status", "owner_email", "updated_at")} for p in W.pages
                       if p["database_id"] == a.get("database_id") and (not a.get("status") or p["status"] == a["status"])])
        add("notion", "create_page", "Create a new notion page in a database.",
            [P("database_id", "notion database id", True), P("title", "page title", True)], [O("page_id", "notion page id")], "object",
            lambda a: {"page_id": "pg_new"}, writes=True)

        # ---- calendar
        ev_list = [O("event_id", "calendar event id"), O("title", "event title"), O("date", "event date"), O("start", "start time"),
                   O("end", "end time"), O("room", "meeting room")]
        add("calendar", "list_events", "List calendar events on a date, optionally for one attendee.",
            [P("date", "date in YYYY-MM-DD", True), P("attendee", "email address of an attendee")], ev_list, "list",
            lambda a: [{k: e[k] for k in ("event_id", "title", "date", "start", "end", "room")} for e in W.events
                       if e["date"] == a.get("date") and (not a.get("attendee") or a["attendee"] in e["attendees"])])
        add("calendar", "get_event", "Get one calendar event by id including organizer and attendees.",
            [P("event_id", "calendar event id", True)],
            ev_list + [O("organizer", "email address of the organizer"), O("attendees", "email addresses of attendees"), O("description", "event description")],
            "object", lambda a: next((dict(e) for e in W.events if e["event_id"] == a.get("event_id")), {}))
        add("calendar", "search_events", "Search calendar events by title keyword.",
            [P("query", "keyword to search for in event titles", True)],
            [O("event_id", "calendar event id"), O("title", "event title"), O("date", "event date"), O("start", "start time")], "list",
            lambda a: [{k: e[k] for k in ("event_id", "title", "date", "start")} for e in W.events if str(a.get("query", "")).lower() in e["title"].lower()])

        def free(a):
            busy = {int(e["start"][:2]) for e in W.events if e["date"] == a.get("date") and a.get("attendee") in e["attendees"]}
            return [{"start": f"{h:02d}:00", "end": f"{h + 1:02d}:00"} for h in range(9, 17) if h not in busy]
        add("calendar", "find_free_slots", "Find free one hour slots for an attendee on a date.",
            [P("attendee", "email address of the attendee", True), P("date", "date in YYYY-MM-DD", True)],
            [O("start", "slot start time"), O("end", "slot end time")], "list", free)
        add("calendar", "create_event", "Create a calendar event.",
            [P("title", "event title", True), P("date", "date in YYYY-MM-DD", True)], [O("event_id", "calendar event id")], "object",
            lambda a: {"event_id": "ev_new"}, writes=True)

        # ---- files
        def listdir(a):
            base = str(a.get("path", "/")).rstrip("/") + "/"
            seen, out = set(), []
            for p, f in W.files.items():
                if p.startswith(base):
                    rest = p[len(base):]
                    nm = rest.split("/")[0]
                    if nm in seen:
                        continue
                    seen.add(nm)
                    isdir = "/" in rest
                    out.append({"name": nm, "type": "directory" if isdir else "file", "size": 0 if isdir else f["size"], "modified": f["modified"]})
            return out
        add("files", "list_directory", "List the entries of a directory.", [P("path", "directory path", True)],
            [O("name", "entry name"), O("type", "file or directory"), O("size", "size in bytes"), O("modified", "last modified date")], "list", listdir)
        add("files", "read_file", "Read the text content of a file.", [P("path", "file path", True)],
            [O("path", "file path"), O("content", "file content"), O("size", "size in bytes"), O("modified", "last modified date")], "object",
            lambda a: {k: W.files[a["path"]][k] for k in ("path", "content", "size", "modified")} if a.get("path") in W.files else {})

        def sfiles(a):
            pat = str(a.get("pattern", ""))
            out = []
            for p, f in W.files.items():
                base = p.rsplit("/", 1)[-1]
                ok = fnmatch.fnmatch(base, pat) or fnmatch.fnmatch(p, pat) if any(c in pat for c in "*?[") else pat.lower() in p.lower()
                if ok:
                    out.append({"path": p, "size": f["size"], "modified": f["modified"]})
            return out
        add("files", "search_files", "Search for files by name pattern, for example *.md or runbook.",
            [P("pattern", "file name pattern or keyword", True), P("directory", "limit to a directory")],
            [O("path", "file path"), O("size", "size in bytes"), O("modified", "last modified date")], "list", sfiles)
        add("files", "get_file_info", "Get metadata of a file: size, modified date and owner.", [P("path", "file path", True)],
            [O("path", "file path"), O("size", "size in bytes"), O("modified", "last modified date"), O("owner", "github login of the file owner"),
             O("mime", "mime type")], "object",
            lambda a: {k: W.files[a["path"]][k] for k in ("path", "size", "modified", "owner", "mime")} if a.get("path") in W.files else {})
        add("files", "write_file", "Write text content to a file.", [P("path", "file path", True), P("content", "text to write", True)],
            [O("path", "file path")], "object", lambda a: {"path": a.get("path")}, writes=True)

        # ---- crm
        add("crm", "search_contacts", "Search CRM contacts by name or email keyword.",
            [P("query", "name or email keyword", True)],
            [O("contact_id", "crm contact id"), O("name", "contact full name"), O("email", "contact email address"), O("company", "company name")],
            "list", lambda a: [{k: c[k] for k in ("contact_id", "name", "email", "company")} for c in W.contacts
                               if str(a.get("query", "")).lower() in (c["name"] + c["email"]).lower()])
        add("crm", "get_contact", "Get a CRM contact by id: email, phone, title.", [P("contact_id", "crm contact id", True)],
            [O("contact_id", "crm contact id"), O("name", "contact full name"), O("email", "contact email address"), O("phone", "phone number"),
             O("company", "company name"), O("title", "job title")], "object",
            lambda a: next((dict(c) for c in W.contacts if c["contact_id"] == a.get("contact_id")), {}))
        add("crm", "list_contacts", "List the CRM contacts that work at a company.", [P("company", "company name", True)],
            [O("contact_id", "crm contact id"), O("name", "contact full name"), O("email", "contact email address"), O("phone", "phone number"),
             O("title", "job title")], "list",
            lambda a: [strip(c, {"company"}) for c in W.contacts if c["company"].lower() == str(a.get("company", "")).lower()])
        add("crm", "list_deals", "List CRM deals, optionally filtered by stage, owner or company.",
            [P("stage", "deal stage: lead, qualified, proposal, negotiation, closed_won or closed_lost"),
             P("owner_email", "email address of the deal owner"), P("company", "company name")],
            [O("deal_id", "crm deal id"), O("company", "company name"), O("stage", "deal stage"), O("amount", "deal amount in dollars"),
             O("owner_email", "email address of the deal owner"), O("contact_id", "crm contact id of the primary contact"), O("close_date", "expected close date")],
            "list", lambda a: [strip(d, {"notes"}) for d in W.deals if (not a.get("stage") or d["stage"] == a["stage"])
                               and (not a.get("owner_email") or d["owner_email"] == a["owner_email"])
                               and (not a.get("company") or d["company"].lower() == str(a["company"]).lower())])
        add("crm", "get_deal", "Get one CRM deal by id including notes.", [P("deal_id", "crm deal id", True)],
            [O("deal_id", "crm deal id"), O("company", "company name"), O("stage", "deal stage"), O("amount", "deal amount in dollars"),
             O("owner_email", "email address of the deal owner"), O("contact_id", "crm contact id of the primary contact"),
             O("close_date", "expected close date"), O("notes", "deal notes")], "object",
            lambda a: next((dict(d) for d in W.deals if d["deal_id"] == a.get("deal_id")), {}))
        add("crm", "get_company", "Get a company profile: industry, employee count, country.", [P("company", "company name", True)],
            [O("name", "company name"), O("industry", "industry"), O("employees", "employee count"), O("country", "country")], "object",
            lambda a: next((dict(c) for c in W.companies if c["name"].lower() == str(a.get("company", "")).lower()), {}))
        return T


def tool_map(tools: list[Tool]) -> dict[str, Tool]:
    return {t.fq: t for t in tools}
