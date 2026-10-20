"""Benchmark tasks: 20 templates x 2 instantiations = 40 tasks, each with 4 phrasings (A canonical, B casual,
C paraphrase, D terse). Templates t01-t10 are the DEV split (used to tune router thresholds); t11-t20 are the
TEST split (never looked at while tuning). Gold answers are computed directly from world data, independently
of the router. 'chain' is the reference tool sequence the baselines (oracle agents) execute."""
from __future__ import annotations

import fnmatch
import random
from dataclasses import dataclass
from typing import Callable

from ligand.world import World, REPOS

P = lambda n: ("p", n)
L = lambda v: ("lit", v)
PREV = lambda f: ("prev", f)
PICK = lambda out, match, par: ("pick", out, match, par)


@dataclass
class Template:
    tid: str
    split: str
    phr: list
    have: dict
    want: list
    sample: Callable
    gold: Callable
    chain: list


def _pick(world, tid, cands, k):
    cands = list(cands)
    rng = random.Random(f"{world.seed}-{tid}")
    rng.shuffle(cands)
    return cands[k % len(cands)]


def _wild(world, pattern):
    out = []
    for p, f in world.files.items():
        base = p.rsplit("/", 1)[-1]
        if any(c in pattern for c in "*?["):
            ok = fnmatch.fnmatch(base, pattern) or fnmatch.fnmatch(p, pattern)
        else:
            ok = pattern.lower() in p.lower()
        if ok:
            out.append(f)
    return out


def build_templates() -> list[Template]:
    T = []

    def add(*a):
        T.append(Template(*a))

    # ---------------- DEV
    add("t01", "dev",
        ["Get the title of pull request {number} in repository {repo}", "what is PR #{number} on {repo} called?",
         "name of change request {number} in the {repo} codebase", "{repo} pr {number} title"],
        {"repo": "{repo}", "number": "{number}"}, [["title"], ["title"], ["pr_title"], ["title"]],
        lambda w, k: (lambda p: {"repo": p["repo"], "number": p["number"]})(_pick(w, "t01", w.prs, k)),
        lambda w, p: [{"title": x["title"]} for x in w.prs if x["repo"] == p["repo"] and x["number"] == p["number"]],
        [("github.get_pull_request", {"repo": P("repo"), "number": P("number")})])
    add("t02", "dev",
        ["List the open pull requests by {author} in repository {repo}", "which PRs is {author} still working on in {repo}?",
         "unfinished change requests authored by {author} for the {repo} codebase", "{repo} open prs {author}"],
        {"repo": "{repo}", "author": "{author}", "state": "open"}, [["number", "title"], ["number", "title"], ["pr_number", "pr_title"], ["number", "title"]],
        lambda w, k: _pick(w, "t02", sorted({(x["repo"], x["author"]) for x in w.prs if x["state"] == "open"}), k) and
        (lambda c: {"repo": c[0], "author": c[1]})(_pick(w, "t02", sorted({(x["repo"], x["author"]) for x in w.prs if x["state"] == "open"}), k)),
        lambda w, p: [{"number": x["number"], "title": x["title"]} for x in w.prs if x["repo"] == p["repo"] and x["author"] == p["author"] and x["state"] == "open"],
        [("github.list_pull_requests", {"repo": P("repo"), "state": L("open"), "author": P("author")})])
    add("t03", "dev",
        ["What is the email address of the author of pull request {number} in {repo}?", "email of whoever wrote PR #{number} on {repo}",
         "contact mail for the person behind change request {number} in {repo}", "{repo} pr {number} author email"],
        {"repo": "{repo}", "number": "{number}"}, [["email"], ["email"], ["author_email"], ["email"]],
        lambda w, k: (lambda p: {"repo": p["repo"], "number": p["number"]})(_pick(w, "t03", w.prs, k)),
        lambda w, p: [{"email": w.people[x["author"]]["email"]} for x in w.prs if x["repo"] == p["repo"] and x["number"] == p["number"]],
        [("github.get_pull_request", {"repo": P("repo"), "number": P("number")}), ("github.get_github_user", {"login": PREV("author")})])
    add("t04", "dev",
        ["List issues in {repo} assigned to {assignee} with the label {label}", "{assignee}'s {label} issues in {repo}?",
         "tickets in the {repo} codebase handed to {assignee} tagged {label}", "{repo} issues {assignee} {label}"],
        {"repo": "{repo}", "assignee": "{assignee}", "label": "{label}"}, [["number", "title"], ["number", "title"], ["issue_number", "issue_title"], ["number", "title"]],
        lambda w, k: (lambda c: {"repo": c[0], "assignee": c[1], "label": c[2]})(
            _pick(w, "t04", sorted({(i["repo"], i["assignee"], lb) for i in w.issues if i["assignee"] for lb in i["labels"]}), k)),
        lambda w, p: [{"number": i["number"], "title": i["title"]} for i in w.issues if i["repo"] == p["repo"] and i["assignee"] == p["assignee"] and p["label"] in i["labels"]],
        [("github.list_issues", {"repo": P("repo"), "assignee": P("assignee"), "label": P("label")})])
    add("t05", "dev",
        ["List the commits by {author} in repository {repo}", "what has {author} committed to {repo}?",
         "code changes pushed by {author} into {repo}", "{repo} commits {author}"],
        {"repo": "{repo}", "author": "{author}"}, [["sha", "message"], ["sha", "message"], ["commit_sha", "commit_message"], ["sha", "message"]],
        lambda w, k: (lambda c: {"repo": c[0], "author": c[1]})(
            _pick(w, "t05", sorted({(c["repo"], c["author"]) for c in w.commits if 1 <= sum(1 for d in w.commits if d["repo"] == c["repo"] and d["author"] == c["author"]) <= 4}), k)),
        lambda w, p: [{"sha": c["sha"], "message": c["message"]} for c in w.commits if c["repo"] == p["repo"] and c["author"] == p["author"]],
        [("github.list_commits", {"repo": P("repo"), "author": P("author")})])
    add("t06", "dev",
        ["Which people posted slack messages mentioning {kw}? Give names and message text", "who in slack talked about {kw}",
         "staff who brought up {kw} in chat, with what they said", "slack {kw} who said what"],
        {"query": "{kw}"}, [["name", "text"], ["name", "text"], ["name", "message"], ["name", "text"]],
        lambda w, k: {"kw": _pick(w, "t06", [x for x in ["outage", "renewal", "migration", "pilot", "rollback", "offsite", "demo"]
                                              if 1 <= sum(1 for m in w.messages if x in m["text"].lower()) <= 6], k)},
        lambda w, p: [{"name": w.people[w.slack_to_login[m["user_id"]]]["name"], "text": m["text"]} for m in w.messages if p["kw"] in m["text"].lower()],
        [("slack.search_messages", {"query": P("kw")}), ("slack.get_user_profile", {"user_id": PREV("user_id")})])
    add("t07", "dev",
        ["List the calendar events on {date} for attendee {attendee}", "what meetings does {attendee} have on {date}?",
         "on {date}, which appointments is {attendee} scheduled for, and when do they begin", "calendar {date} {attendee}"],
        {"attendee": "{attendee}", "date": "{date}"}, [["title", "start"], ["title", "start"], ["title", "start_time"], ["title", "start"]],
        lambda w, k: (lambda c: {"attendee": c[0], "date": c[1]})(_pick(w, "t07", sorted({(a, e["date"]) for e in w.events for a in e["attendees"]}), k)),
        lambda w, p: [{"title": e["title"], "start": e["start"]} for e in w.events if e["date"] == p["date"] and p["attendee"] in e["attendees"]],
        [("calendar.list_events", {"date": P("date"), "attendee": P("attendee")})])
    add("t08", "dev",
        ["List the CRM deals in the {stage} stage with company and amount", "which deals are at {stage} right now and how big?",
         "opportunities currently sitting in {stage}: customer and value", "deals {stage}"],
        {"stage": "{stage}"}, [["company", "amount"], ["company", "amount"], ["company_name", "deal_amount"], ["company", "amount"]],
        lambda w, k: {"stage": _pick(w, "t08", sorted({d["stage"] for d in w.deals}), k)},
        lambda w, p: [{"company": d["company"], "amount": d["amount"]} for d in w.deals if d["stage"] == p["stage"]],
        [("crm.list_deals", {"stage": P("stage")})])
    add("t09", "dev",
        ["What is the email address of the primary contact on the {company} deal?", "email for the person we're talking to at {company} about the deal",
         "mail of the main point of contact in the {company} opportunity", "{company} deal contact email"],
        {"company": "{company}"}, [["email"], ["email"], ["contact_email"], ["email"]],
        lambda w, k: {"company": _pick(w, "t09", sorted(c["name"] for c in w.companies if sum(1 for d in w.deals if d["company"] == c["name"]) == 1), k)},
        lambda w, p: [{"email": next(c["email"] for c in w.contacts if c["contact_id"] == d["contact_id"])} for d in w.deals if d["company"] == p["company"]],
        [("crm.list_deals", {"company": P("company")}), ("crm.get_contact", {"contact_id": PREV("contact_id")})])
    add("t10", "dev",
        ["Find files matching {pattern} and show their path and size", "which files match {pattern}? how big are they",
         "locate documents named like {pattern}, report location and size in bytes", "files {pattern} size"],
        {"pattern": "{pattern}"}, [["path", "size"], ["path", "size"], ["file_path", "size_bytes"], ["path", "size"]],
        lambda w, k: {"pattern": _pick(w, "t10", [x for x in ["*.md", "runbook", "*.csv", "*.tf", "q3", "*.sh", "handbook", "*.tsx"] if 1 <= len(_wild(w, x)) <= 6], k)},
        lambda w, p: [{"path": f["path"], "size": f["size"]} for f in _wild(w, p["pattern"])],
        [("files.search_files", {"pattern": P("pattern")})])
    # ---------------- TEST
    add("t11", "test",
        ["List the titles of pages in the {db} database with status {status}", "which {db} pages are {status}?",
         "entries of the {db} workspace table that are {status}, titles only", "notion {db} {status} titles"],
        {"database_name": "{db}", "status": "{status}"}, [["title"], ["title"], ["page_title"], ["title"]],
        lambda w, k: (lambda c: {"db": c[0], "status": c[1]})(_pick(w, "t11", sorted({(p["database"], p["status"]) for p in w.pages}), k)),
        lambda w, p: [{"title": x["title"]} for x in w.pages if x["database"] == p["db"] and x["status"] == p["status"]],
        [("notion.list_databases", {}), ("notion.query_database", {"database_id": PICK("database_id", "name", "db"), "status": P("status")})])
    add("t12", "test",
        ["Who owns the notion page about {title}? Give their email address", "owner email for the {title} page",
         "mail of the person responsible for the document titled {title}", "notion {title} owner email"],
        {"query": "{title}"}, [["owner_email"], ["owner_email"], ["email"], ["owner_email"]],
        lambda w, k: {"title": _pick(w, "t12", sorted(p["title"] for p in w.pages), k)},
        lambda w, p: [{"owner_email": x["owner_email"]} for x in w.pages if p["title"].lower() in x["title"].lower()],
        [("notion.search_pages", {"query": P("title")}), ("notion.get_page", {"page_id": PREV("page_id")})])
    add("t13", "test",
        ["Find free one hour slots for {attendee} on {date}", "when is {attendee} free on {date}?",
         "open time windows for {attendee} during {date}", "free slots {attendee} {date}"],
        {"attendee": "{attendee}", "date": "{date}"}, [["start", "end"], ["start", "end"], ["start_time", "end_time"], ["start", "end"]],
        lambda w, k: (lambda c: {"attendee": c[0], "date": c[1]})(_pick(w, "t13", sorted({(a, e["date"]) for e in w.events for a in e["attendees"]}), k)),
        lambda w, p: [{"start": f"{h:02d}:00", "end": f"{h + 1:02d}:00"} for h in range(9, 17)
                      if h not in {int(e["start"][:2]) for e in w.events if e["date"] == p["date"] and p["attendee"] in e["attendees"]}],
        [("calendar.find_free_slots", {"attendee": P("attendee"), "date": P("date")})])
    add("t14", "test",
        ["Which room is the {title} meeting in and when does it start?", "where is {title} happening and at what time",
         "meeting place and start time for {title}", "{title} room start"],
        {"query": "{title}"}, [["room", "start"], ["room", "start"], ["room", "start_time"], ["room", "start"]],
        lambda w, k: {"title": _pick(w, "t14", sorted(e["title"] for e in w.events if sum(1 for f in w.events if e["title"].lower() in f["title"].lower()) == 1), k)},
        lambda w, p: [{"room": e["room"], "start": e["start"]} for e in w.events if p["title"].lower() in e["title"].lower()],
        [("calendar.search_events", {"query": P("title")}), ("calendar.get_event", {"event_id": PREV("event_id")})])
    add("t15", "test",
        ["List the CRM contacts who work at {company} with name and email", "who do we know at {company}? names and emails",
         "people employed by {company} in our address book: full name and mail", "{company} contacts name email"],
        {"company": "{company}"}, [["name", "email"], ["name", "email"], ["contact_name", "email"], ["name", "email"]],
        lambda w, k: {"company": _pick(w, "t15", sorted(c["name"] for c in w.companies), k)},
        lambda w, p: [{"name": c["name"], "email": c["email"]} for c in w.contacts if c["company"] == p["company"]],
        [("crm.list_contacts", {"company": P("company")})])
    add("t16", "test",
        ["What is the value and stage of the deals with {company}?", "how much is the {company} deal worth and where is it in the pipeline",
         "size and pipeline position of the opportunity with {company}", "{company} deal amount stage"],
        {"company": "{company}"}, [["amount", "stage"], ["amount", "stage"], ["deal_amount", "stage"], ["amount", "stage"]],
        lambda w, k: {"company": _pick(w, "t16", sorted(c["name"] for c in w.companies), k)},
        lambda w, p: [{"amount": d["amount"], "stage": d["stage"]} for d in w.deals if d["company"] == p["company"]],
        [("crm.list_deals", {"company": P("company")})])
    add("t17", "test",
        ["What is the email address of the person assigned to issue {number} in {repo}?", "email of the assignee of issue #{number} on {repo}",
         "contact mail for whoever owns ticket {number} of the {repo} codebase", "{repo} issue {number} assignee email"],
        {"repo": "{repo}", "number": "{number}"}, [["email"], ["email"], ["email"], ["email"]],
        lambda w, k: (lambda p: {"repo": p["repo"], "number": p["number"]})(_pick(w, "t17", [i for i in w.issues if i["assignee"]], k)),
        lambda w, p: [{"email": w.people[i["assignee"]]["email"]} for i in w.issues if i["repo"] == p["repo"] and i["number"] == p["number"]],
        [("github.get_issue", {"repo": P("repo"), "number": P("number")}), ("github.get_github_user", {"login": PREV("assignee")})])
    add("t18", "test",
        ["Show the most recent messages in the {channel} slack channel with timestamps", "what's been said lately in #{channel}?",
         "latest chatter in the {channel} chat room, with times", "slack {channel} recent messages"],
        {"channel": "{channel}"}, [["ts", "text"], ["ts", "text"], ["timestamp", "text"], ["ts", "text"]],
        lambda w, k: {"channel": _pick(w, "t18", [c["name"] for c in w.channels], k)},
        lambda w, p: [{"ts": m["ts"], "text": m["text"]} for m in sorted([m for m in w.messages if m["channel"] == p["channel"]], key=lambda m: m["ts"], reverse=True)[:5]],
        [("slack.get_channel_history", {"channel": P("channel")})])
    add("t19", "test",
        ["Read the file {path} and return its content", "what's in {path}?", "open {path} and give me the text inside", "cat {path}"],
        {"path": "{path}"}, [["content"], ["content"], ["file_content"], ["content"]],
        lambda w, k: {"path": _pick(w, "t19", sorted(p for p in w.files if p.startswith(("/docs", "/notes", "/reports"))), k)},
        lambda w, p: [{"content": w.files[p["path"]]["content"]}],
        [("files.read_file", {"path": P("path")})])
    add("t20", "test",
        ["What is the primary programming language of repository {repo}?", "what language is {repo} written in",
         "main coding language used by the {repo} project", "{repo} language"],
        {"repo": "{repo}"}, [["language"], ["language"], ["language"], ["language"]],
        lambda w, k: {"repo": _pick(w, "t20", REPOS, k)},
        lambda w, p: [{"language": r["language"]} for r in w.repos if r["full_name"] == p["repo"]],
        [("github.get_repository", {"repo": P("repo")})])
    # ---------------- TEST2: written BEFORE the v2 engine existed; never used for tuning or diagnosis
    add("t21", "test2",
        ["What is the status of the notion page titled {title}?", "is the {title} page draft or done?",
         "progress state of the document called {title}", "notion {title} status"],
        {"query": "{title}"}, [["status"], ["status"], ["state"], ["status"]],
        lambda w, k: {"title": _pick(w, "t21", sorted(p["title"] for p in w.pages), k)},
        lambda w, p: [{"status": x["status"]} for x in w.pages if p["title"].lower() in x["title"].lower()],
        [("notion.search_pages", {"query": P("title")}), ("notion.get_page", {"page_id": PREV("page_id")})])
    add("t22", "test2",
        ["Who is assigned to issue {number} in {repo}? Give their github login", "who owns issue #{number} on {repo}?",
         "the person handling ticket {number} of the {repo} codebase: login", "{repo} issue {number} assignee"],
        {"repo": "{repo}", "number": "{number}"}, [["assignee"], ["assignee"], ["login"], ["assignee"]],
        lambda w, k: (lambda i: {"repo": i["repo"], "number": i["number"]})(_pick(w, "t22", [i for i in w.issues if i["assignee"]], k)),
        lambda w, p: [{"assignee": i["assignee"]} for i in w.issues if i["repo"] == p["repo"] and i["number"] == p["number"]],
        [("github.get_issue", {"repo": P("repo"), "number": P("number")})])
    add("t23", "test2",
        ["List the branches of repository {repo} with their head sha", "what branches does {repo} have?",
         "git branches in the {repo} project and their latest commit", "{repo} branches sha"],
        {"repo": "{repo}"}, [["name", "sha"], ["name", "sha"], ["branch", "sha"], ["name", "sha"]],
        lambda w, k: {"repo": _pick(w, "t23", REPOS, k)},
        lambda w, p: [{"name": "main", "sha": "a1b2c3d"}, {"name": "release", "sha": "d4e5f6a"}, {"name": "dev", "sha": "0f9e8d7"}],
        [("github.list_branches", {"repo": P("repo")})])
    add("t24", "test2",
        ["What is the phone number of {name} at {company}?", "phone for {name} from {company}",
         "how do I call {name} who works at {company}", "{company} {name} phone"],
        {"company": "{company}", "name": "{name}"}, [["phone"], ["phone"], ["phone_number"], ["phone"]],
        lambda w, k: (lambda c: {"company": c["company"], "name": c["name"]})(_pick(w, "t24", sorted(w.contacts, key=lambda c: c["contact_id"]), k)),
        lambda w, p: [{"phone": c["phone"]} for c in w.contacts if c["company"] == p["company"] and c["name"] == p["name"]],
        [("crm.list_contacts", {"company": P("company")})])
    add("t25", "test2",
        ["What industry is {company} in and how many employees does it have?", "{company}: industry and headcount?",
         "business sector and staff size of {company}", "company {company} industry employees"],
        {"company": "{company}"}, [["industry", "employees"], ["industry", "employees"], ["industry", "employee_count"], ["industry", "employees"]],
        lambda w, k: {"company": _pick(w, "t25", sorted(c["name"] for c in w.companies), k)},
        lambda w, p: [{"industry": c["industry"], "employees": c["employees"]} for c in w.companies if c["name"] == p["company"]],
        [("crm.get_company", {"company": P("company")})])
    add("t26", "test2",
        ["Who organized the {title} meeting? Give their email", "who is running {title}",
         "organizer of the event called {title}, as an email address", "{title} organizer"],
        {"query": "{title}"}, [["organizer"], ["organizer"], ["organizer_email"], ["organizer"]],
        lambda w, k: {"title": _pick(w, "t26", sorted(e["title"] for e in w.events if sum(1 for f in w.events if e["title"].lower() in f["title"].lower()) == 1), k)},
        lambda w, p: [{"organizer": e["organizer"]} for e in w.events if p["title"].lower() in e["title"].lower()],
        [("calendar.search_events", {"query": P("title")}), ("calendar.get_event", {"event_id": PREV("event_id")})])
    add("t27", "test2",
        ["What are the name and job title of slack user {user_id}?", "who is {user_id} and what is their job title",
         "full name and job title of the slack member {user_id}", "slack {user_id} name title"],
        {"user_id": "{user_id}"}, [["name", "title"], ["name", "title"], ["name", "job_title"], ["name", "title"]],
        lambda w, k: {"user_id": _pick(w, "t27", sorted(p["slack_id"] for p in w.people.values()), k)},
        lambda w, p: [{"name": w.people[w.slack_to_login[p["user_id"]]]["name"], "title": w.people[w.slack_to_login[p["user_id"]]]["title"]}],
        [("slack.get_user_profile", {"user_id": P("user_id")})])
    add("t28", "test2",
        ["List the deals owned by {owner_email} with company and stage", "what deals is {owner_email} handling and where are they",
         "opportunities assigned to {owner_email}: customer and pipeline position", "deals {owner_email} company stage"],
        {"owner_email": "{owner_email}"}, [["company", "stage"], ["company", "stage"], ["company_name", "stage"], ["company", "stage"]],
        lambda w, k: {"owner_email": _pick(w, "t28", sorted({d["owner_email"] for d in w.deals}), k)},
        lambda w, p: [{"company": d["company"], "stage": d["stage"]} for d in w.deals if d["owner_email"] == p["owner_email"]],
        [("crm.list_deals", {"owner_email": P("owner_email")})])
    add("t29", "test2",
        ["How many stars does repository {repo} have?", "star count of {repo}",
         "popularity of the {repo} project in github stars", "{repo} stars"],
        {"repo": "{repo}"}, [["stars"], ["stars"], ["stars"], ["stars"]],
        lambda w, k: {"repo": _pick(w, "t29", REPOS, k)},
        lambda w, p: [{"stars": r["stars"]} for r in w.repos if r["full_name"] == p["repo"]],
        [("github.get_repository", {"repo": P("repo")})])
    add("t30", "test2",
        ["List the commits in {repo} made since {since} with sha and message", "what changed in {repo} after {since}?",
         "code changes pushed into {repo} on or after {since}", "{repo} commits since {since}"],
        {"repo": "{repo}", "since": "{since}"}, [["sha", "message"], ["sha", "message"], ["commit_sha", "commit_message"], ["sha", "message"]],
        lambda w, k: (lambda c: {"repo": c[0], "since": c[1]})(_pick(w, "t30", [(r, d) for r in REPOS for d in ("2026-10-08", "2026-10-12", "2026-10-15")
                                                                                if 1 <= sum(1 for c in w.commits if c["repo"] == r and c["date"] >= d) <= 8], k)),
        lambda w, p: [{"sha": c["sha"], "message": c["message"]} for c in w.commits if c["repo"] == p["repo"] and c["date"] >= p["since"]],
        [("github.list_commits", {"repo": P("repo"), "since": P("since")})])
    return T


def make_tasks(world: World) -> list[dict]:
    tasks = []
    for t in build_templates():
        for k in range(2):
            p = t.sample(world, k)
            gold = t.gold(world, p)
            assert gold, f"empty gold for {t.tid} {p}"
            phr = []
            for goal, want in zip(t.phr, t.want):
                have = {key: (p[v[1:-1]] if v.startswith("{") else v) for key, v in t.have.items()}
                phr.append({"goal": goal.format(**p), "have": have, "want": want})
            tasks.append({"id": f"{t.tid}.{k}", "tid": t.tid, "split": t.split, "k": k, "params": p, "phr": phr,
                          "canon": t.want[0], "gold": gold, "chain": t.chain})
    return tasks


def norm_rows(rows, keys) -> list:
    out = {tuple(str(r.get(k)) for k in keys) for r in rows}
    return sorted(out)


def judge(task, phr_idx, rows) -> bool:
    want = task["phr"][phr_idx]["want"]
    return norm_rows(rows, want) == norm_rows(task["gold"], task["canon"])


def run_gold_chain(tmap: dict, task: dict):
    """Execute the reference chain with an oracle agent. Returns list of steps; each step = list of (fq, args, result)."""
    p = task["params"]
    steps, prev_items = [], None
    for si, (fq, argmap) in enumerate(task["chain"]):
        tool = tmap[fq]
        calls_args = []
        if si == 0 or not any(v[0] == "prev" for v in argmap.values()):
            a = {}
            for k, v in argmap.items():
                a[k] = p[v[1]] if v[0] == "p" else v[1]
            calls_args = [a]
        else:
            for it in prev_items[:12]:
                a = {}
                for k, v in argmap.items():
                    a[k] = p[v[1]] if v[0] == "p" else (it.get(v[1]) if v[0] == "prev" else v[1])
                calls_args.append(a)
        # 'pick' semantics: choose the matching item of the previous result
        for k, v in list(argmap.items()):
            if v[0] == "pick":
                match = next(it for it in prev_items if str(it.get(v[2])).lower() == str(p[v[3]]).lower())
                for a in calls_args:
                    a[k] = match[v[1]]
                for kk, vv in argmap.items():
                    if vv[0] == "p":
                        for a in calls_args:
                            a[kk] = p[vv[1]]
        step = []
        items_all = []
        for a in calls_args:
            res = tool.fn(a)
            wrapped = {"items": res} if tool.kind == "list" else res
            step.append((fq, a, wrapped))
            items_all.extend(res if tool.kind == "list" else ([res] if res else []))
        steps.append(step)
        prev_items = items_all
    return steps
