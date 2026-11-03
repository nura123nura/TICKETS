#!/usr/bin/env python3
"""DORA метрикалары: GitHub API -> есептеу -> matplotlib дашборды.

Нақты репозиторий:  GITHUB_TOKEN=... python scripts/dora.py --repo OWNER/REPO --days 90
Демо (API-сыз):     python scripts/dora.py --demo

Анықтамалар:
  Деплой          = жарияланған GitHub Release (v* тегі).
  Lead time       = PR-дегі бірінші коммит -> келесі релиздің жариялануы.
  Сәтсіз деплой   = релизден кейін 48 сағат ішінде "incident" issue ашылса
                    немесе "hotfix"/"revert" PR біріксе.
  MTTR            = "incident" issue-дің ашылуы -> жабылуы.
"""
import argparse
import json
import os
import random
import statistics
from datetime import datetime, timedelta, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

API = "https://api.github.com"
FAIL_WINDOW = timedelta(hours=48)


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


# ---------------------------------------------------------------- деректер
def gh_get(session, path, **params):
    out, page = [], 1
    while True:
        r = session.get(f"{API}{path}", params={**params, "per_page": 100, "page": page})
        r.raise_for_status()
        chunk = r.json()
        out += chunk
        if len(chunk) < 100:
            return out
        page += 1


def fetch_real(repo, since):
    import requests
    s = requests.Session()
    s.headers["Accept"] = "application/vnd.github+json"
    if os.getenv("GITHUB_TOKEN"):
        s.headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    releases = sorted(parse(r["published_at"]) for r in gh_get(s, f"/repos/{repo}/releases")
                      if not r["draft"] and r["published_at"])
    prs, hotfixes = [], []
    for p in gh_get(s, f"/repos/{repo}/pulls", state="closed", base="main"):
        if not p["merged_at"]:
            continue
        merged = parse(p["merged_at"])
        if any(w in p["title"].lower() for w in ("hotfix", "revert")):
            hotfixes.append(merged)
        commits = gh_get(s, f"/repos/{repo}/pulls/{p['number']}/commits")
        first = min(parse(c["commit"]["author"]["date"]) for c in commits)
        prs.append((first, merged))
    incidents = []
    for i in gh_get(s, f"/repos/{repo}/issues", state="all", labels="incident"):
        if "pull_request" not in i:
            closed = parse(i["closed_at"]) if i["closed_at"] else None
            incidents.append((parse(i["created_at"]), closed))
    return {"releases": [r for r in releases if r >= since], "prs": prs,
            "hotfixes": hotfixes, "incidents": incidents}


def fetch_demo(now, days):
    """Демо-деректер (НАҚТЫ ЕМЕС). Тек дашбордтың жұмысын көрсету үшін."""
    rnd = random.Random(42)
    releases, t = [], now - timedelta(days=days)
    while t < now:
        t += timedelta(days=rnd.choice([3, 4, 5, 7, 9]), hours=rnd.randint(0, 8))
        if t < now:
            releases.append(t)
    prs, incidents, hotfixes = [], [], []
    prev = now - timedelta(days=days)
    for r in releases:
        for _ in range(rnd.randint(2, 5)):
            merged = prev + (r - prev) * rnd.random()
            prs.append((merged - timedelta(hours=rnd.uniform(6, 70)), merged))
        prev = r
    for r in rnd.sample(releases, k=max(1, len(releases) // 6)):
        c = r + timedelta(hours=rnd.uniform(1, 30))
        incidents.append((c, c + timedelta(hours=rnd.uniform(0.7, 6))))
        hotfixes.append(c + timedelta(hours=1))
    return {"releases": releases, "prs": prs, "hotfixes": hotfixes, "incidents": incidents}


# ---------------------------------------------------------------- есептеу
def classify(df_per_day, lead_h, cfr, mttr_h):
    def pick(v, rules):
        for limit, name in rules:
            if v <= limit:
                return name
        return "Төмен"
    return {
        "deployment_frequency": ("Элита" if df_per_day >= 1 else "Жоғары" if df_per_day >= 1 / 7
                                 else "Орташа" if df_per_day >= 1 / 30 else "Төмен"),
        "lead_time": pick(lead_h, [(24, "Элита"), (168, "Жоғары"), (720, "Орташа")]),
        "change_failure_rate": pick(cfr, [(0.05, "Элита"), (0.10, "Жоғары"), (0.15, "Орташа")]),
        "mttr": pick(mttr_h, [(1, "Элита"), (24, "Жоғары"), (168, "Орташа")]),
    }


def compute(data, days):
    rel = data["releases"]
    leads = []
    for first, merged in data["prs"]:
        nxt = next((r for r in rel if r >= merged), None)
        if nxt:
            leads.append((nxt - first).total_seconds() / 3600)
    failed = [r for r in rel
              if any(r <= c <= r + FAIL_WINDOW for c, _ in data["incidents"])
              or any(r <= h <= r + FAIL_WINDOW for h in data["hotfixes"])]
    rest = [(c2 - c1).total_seconds() / 3600 for c1, c2 in data["incidents"] if c2]
    df = len(rel) / days
    lead = statistics.median(leads) if leads else float("nan")
    cfr = len(failed) / len(rel) if rel else float("nan")
    mttr = statistics.median(rest) if rest else 0.0
    return {"period_days": days, "deployments": len(rel),
            "deploys_per_week": round(df * 7, 2), "lead_time_hours_median": round(lead, 1),
            "change_failure_rate": round(cfr, 3), "failed_deployments": len(failed),
            "mttr_hours_median": round(mttr, 2),
            "levels": classify(df, lead, cfr, mttr)}, leads, failed, rest


# ---------------------------------------------------------------- дашборд
def plot(data, m, leads, failed, rest, now, days, title, out):
    fig, ax = plt.subplots(2, 2, figsize=(13, 8))
    fig.suptitle(title, fontsize=14, fontweight="bold")
    weeks = days // 7 + 1
    counts = [0] * weeks
    for r in data["releases"]:
        counts[min(weeks - 1, (r - (now - timedelta(days=days))).days // 7)] += 1
    ax[0][0].bar(range(1, weeks + 1), counts, color="#2a7fff")
    lv = m["levels"]
    ax[0][0].set(title=f"Деплой жиілігі: {m['deploys_per_week']}/апта — "
                       f"{lv['deployment_frequency']}",
                 xlabel="Апта", ylabel="Релиз саны")
    ax[0][1].plot(range(1, len(leads) + 1), leads, marker="o", color="#27ae60")
    ax[0][1].axhline(m["lead_time_hours_median"], ls="--", color="gray")
    ax[0][1].set(title=f"Lead time: медиана {m['lead_time_hours_median']} сағ — "
                       f"{lv['lead_time']}",
                 xlabel="PR реті", ylabel="Сағат")
    ok = len(data["releases"]) - len(failed)
    ax[1][0].pie([ok, len(failed)], labels=["Сәтті", "Сәтсіз"], autopct="%1.0f%%",
                 colors=["#27ae60", "#e74c3c"], startangle=90)
    ax[1][0].set_title(f"Өзгерістердің сәтсіздік үлесі: {m['change_failure_rate']:.0%} — "
                       f"{m['levels']['change_failure_rate']}")
    ax[1][1].bar(range(1, len(rest) + 1), rest, color="#e67e22")
    ax[1][1].set(title=f"MTTR: медиана {m['mttr_hours_median']} сағ — {m['levels']['mttr']}",
                 xlabel="Инцидент реті", ylabel="Сағат")
    fig.tight_layout()
    fig.savefig(out, dpi=130)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default="docs")
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    if a.demo:
        data, title = fetch_demo(now, a.days), "DORA дашборды (ДЕМО-деректер)"
    elif a.repo:
        data, title = fetch_real(a.repo, now - timedelta(days=a.days)), f"DORA дашборды: {a.repo}"
    else:
        ap.error("--repo OWNER/REPO немесе --demo көрсетіңіз")
    m, leads, failed, rest = compute(data, a.days)
    os.makedirs(a.out, exist_ok=True)
    with open(f"{a.out}/dora_metrics.json", "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    plot(data, m, leads, failed, rest, now, a.days, title, f"{a.out}/dora_dashboard.png")
    print(json.dumps(m, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
