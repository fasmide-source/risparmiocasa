#!/usr/bin/env python3
"""
RisparmioCasa - scanner giornaliero.
Cerca su Google News (RSS) le opportunità di risparmio per la famiglia,
aggiorna data/feed.json e invia una notifica push (ntfy e/o Telegram).
Solo libreria standard Python: nessuna dipendenza da installare.
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "scanner", "config.json")
FEED = os.path.join(ROOT, "data", "feed.json")
UA = "Mozilla/5.0 (RisparmioCasa scanner; uso personale)"


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def http_post_json(url, payload, timeout=20):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status


def clean(text):
    text = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def google_news(query, max_items):
    q = urllib.parse.quote(f"{query} when:2d")
    url = f"https://news.google.com/rss/search?q={q}&hl=it&gl=IT&ceid=IT:it"
    root = ET.fromstring(http_get(url))
    out = []
    for it in root.iter("item"):
        title = clean(it.findtext("title"))
        source = clean(it.findtext("source")) or ""
        # Google News aggiunge " - Fonte" in coda al titolo
        if source and title.endswith(" - " + source):
            title = title[: -(len(source) + 3)]
        try:
            pub = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc)
        except Exception:
            pub = datetime.now(timezone.utc)
        out.append({
            "title": title,
            "link": (it.findtext("link") or "").strip(),
            "source": source,
            "published": pub.isoformat(),
            "summary": clean(it.findtext("description"))[:280],
        })
        if len(out) >= max_items:
            break
    return out


def score(item, cfg):
    t = (item["title"] + " " + item["summary"]).lower()
    s = sum(2 for w in cfg["parole_bonus"] if w in t)
    if re.search(r"\b\d{1,3}\s?(%|euro|€)", t):
        s += 3  # cifre concrete di sconto / importi
    if any(x in (item["source"] or "").lower() for x in ["inps", "agenzia entrate", "mimit", "roma capitale", "regione lazio", "arera", "gazzetta ufficiale"]):
        s += 5  # fonte istituzionale
    return s


def norm_key(title):
    return re.sub(r"[^a-z0-9]", "", title.lower())[:80]


def notify(new_items, cats, cfg):
    if not new_items:
        return
    top = sorted(new_items, key=lambda x: -x["score"])[: cfg["max_notizie_nella_notifica"]]
    lines = [f"{cats[i['category']]['emoji']} {i['title']}" for i in top]
    msg = "\n".join(lines)
    title = f"RisparmioCasa: {len(new_items)} nuove opportunità"
    app_url = os.environ.get("APP_URL", "")

    topic = os.environ.get("NTFY_TOPIC")
    if topic:
        try:
            http_post_json(os.environ.get("NTFY_SERVER", "https://ntfy.sh"), {
                "topic": topic, "title": title, "message": msg,
                "tags": ["moneybag"], "click": app_url or top[0]["link"], "priority": 3,
            })
            log("Notifica ntfy inviata")
        except Exception as e:
            log("Errore ntfy:", e)

    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat:
        body = f"*{title}*\n\n" + "\n".join(f"{cats[i['category']]['emoji']} [{i['title']}]({i['link']})" for i in top)
        if app_url:
            body += f"\n\n👉 Apri l'app: {app_url}"
        try:
            http_post_json(f"https://api.telegram.org/bot{tok}/sendMessage",
                           {"chat_id": chat, "text": body, "parse_mode": "Markdown", "disable_web_page_preview": True})
            log("Notifica Telegram inviata")
        except Exception as e:
            log("Errore Telegram:", e)


def main():
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    cats = cfg["categorie"]
    try:
        old = json.load(open(FEED, encoding="utf-8"))
    except Exception:
        old = {"items": []}
    known_ids = {i["id"] for i in old.get("items", [])}
    known_titles = {norm_key(i["title"]) for i in old.get("items", [])}

    found, seen_titles = [], set()
    for cat_id, cat in cats.items():
        for q in cat["query"]:
            try:
                items = google_news(q, cfg["max_notizie_per_query"])
            except Exception as e:
                log(f"[{cat_id}] errore su '{q}': {e}")
                continue
            for it in items:
                k = norm_key(it["title"])
                if not k or k in seen_titles:
                    continue
                if any(w in it["title"].lower() for w in cfg["parole_escluse"]):
                    continue
                seen_titles.add(k)
                it["id"] = hashlib.sha1(k.encode()).hexdigest()[:12]
                it["category"] = cat_id
                it["query"] = q
                it["score"] = score(it, cfg)
                it["found"] = datetime.now(timezone.utc).isoformat()
                found.append(it)
            time.sleep(1)  # cortesia verso il servizio

    new_items = [i for i in found if i["id"] not in known_ids and norm_key(i["title"]) not in known_titles]
    limit = datetime.now(timezone.utc) - timedelta(days=cfg["giorni_archivio_feed"])
    keep = [i for i in old.get("items", []) if datetime.fromisoformat(i["found"]) > limit]
    all_items = sorted(new_items + keep, key=lambda x: x["found"], reverse=True)

    os.makedirs(os.path.dirname(FEED), exist_ok=True)
    json.dump({
        "updated": datetime.now(timezone.utc).isoformat(),
        "categories": {k: {"label": v["label"], "emoji": v["emoji"]} for k, v in cats.items()},
        "items": all_items,
    }, open(FEED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"Nuove: {len(new_items)} | Totali nel feed: {len(all_items)}")
    notify(new_items, cats, cfg)


if __name__ == "__main__":
    main()
