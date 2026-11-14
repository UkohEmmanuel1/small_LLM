#!/usr/bin/env python3
"""
live.py - connect your model (gpt.py) to live information from the internet.

  collect   fetch fresh articles from RSS/Atom feeds -> append to a training corpus (deduplicated)
  ask       retrieve live context (Wikipedia + your collected corpus) and answer with your model
  loop      collect on a schedule and continue training whenever enough new data has arrived

Examples:
  python live.py collect --feeds feeds.txt --data data/live.txt
  python live.py ask "what is mixture of experts" --out out --data data/live.txt
  python live.py loop --feeds feeds.txt --data data/live.txt --out out --every 3600

Only uses the standard library (plus torch, via gpt.py, for `ask` and `loop`).
Respect each site's terms of service and robots.txt; prefer feeds and APIs over scraping pages.
"""
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from html.parser import HTMLParser

EOT = "<|endoftext|>"
UA = {"User-Agent": "Mozilla/5.0 (compatible; MyLLMBot/0.1; personal research)"}
HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------
# Fetching + cleaning
# --------------------------------------------------------------------------
def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        charset = r.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg"}

    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(re.sub(r"\s+", " ", data.strip()))


def html_to_text(html, min_line=0):
    p = _TextExtractor()
    try:
        p.feed(html)
    except Exception:
        pass
    lines = [l for l in p.parts if len(l) >= min_line]
    return "\n".join(lines).strip()


def parse_feed(xml_text):
    """Parse RSS 2.0 or Atom into [{title, link, summary}]."""
    root = ET.fromstring(xml_text)
    items = []
    for el in root.iter():
        if el.tag.split("}")[-1] not in ("item", "entry"):
            continue
        title = link = summary = ""
        for c in el:
            t = c.tag.split("}")[-1]
            if t == "title":
                title = (c.text or "").strip()
            elif t == "link" and not link:
                link = c.attrib.get("href") or (c.text or "").strip()
            elif t in ("description", "summary", "content"):
                summary = html_to_text(c.text or "")
        items.append({"title": title, "link": link, "summary": summary})
    return items


# --------------------------------------------------------------------------
# collect
# --------------------------------------------------------------------------
def collect(feeds_path, data_path, full=False):
    os.makedirs(os.path.dirname(data_path) or ".", exist_ok=True)
    seen_path = data_path + ".seen.json"
    seen = set(json.load(open(seen_path))) if os.path.exists(seen_path) else set()
    feeds = [l.strip() for l in open(feeds_path) if l.strip() and not l.startswith("#")]

    added = chars = 0
    with open(data_path, "a", encoding="utf-8") as out:
        for url in feeds:
            try:
                items = parse_feed(http_get(url))
            except Exception as e:
                print(f"  ! {url}: {e}")
                continue
            for it in items:
                key = hashlib.sha1((it["link"] or it["title"]).encode()).hexdigest()
                if key in seen:
                    continue
                seen.add(key)
                body = it["summary"]
                if full and it["link"]:
                    try:
                        body = html_to_text(http_get(it["link"]), min_line=40) or body
                    except Exception:
                        pass
                if len(body) < 120:
                    continue
                doc = f"{it['title']}\n\n{body}\n{EOT}\n"
                out.write(doc)
                added += 1
                chars += len(doc)
    json.dump(sorted(seen), open(seen_path, "w"))
    return added, chars


def cmd_collect(a):
    added, chars = collect(a.feeds, a.data, a.full)
    print(f"collected {added} new documents ({chars:,} chars) -> {a.data}")


# --------------------------------------------------------------------------
# retrieval (live web + local corpus)
# --------------------------------------------------------------------------
def wiki_search(query, n=3):
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "generator": "search", "gsrsearch": query, "gsrlimit": n,
        "prop": "extracts", "exintro": 1, "explaintext": 1, "format": "json",
    })
    pages = json.loads(http_get(url)).get("query", {}).get("pages", {}).values()
    pages = sorted(pages, key=lambda p: p.get("index", 0))
    return [(f"wikipedia: {p['title']}", p.get("extract", "")) for p in pages if p.get("extract")]


def _tokens(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def top_local(query, data_path, k=3):
    """Tiny TF-IDF retrieval over the collected corpus."""
    docs = [d.strip() for d in open(data_path, encoding="utf-8").read().split(EOT) if d.strip()]
    if not docs:
        return []
    toks = [Counter(_tokens(d)) for d in docs]
    df = Counter(t for c in toks for t in c)
    q = set(_tokens(query))
    scores = []
    for i, c in enumerate(toks):
        s = sum((1 + math.log(c[t])) * math.log(1 + len(docs) / df[t]) for t in q if c[t])
        scores.append((s, i))
    scores.sort(reverse=True)
    return [("corpus: " + docs[i].split("\n", 1)[0][:80], docs[i]) for s, i in scores[:k] if s > 0]


def cmd_ask(a):
    sources = []
    if not a.no_web:
        try:
            sources += wiki_search(a.query, a.k)
        except Exception as e:
            print(f"(web lookup failed: {e})")
    if os.path.exists(a.data):
        sources += top_local(a.query, a.data, a.k)

    print("=== live sources retrieved ===")
    for name, text in sources:
        print(f"- {name}\n    {text[:300].replace(chr(10), ' ')}...")
    if not sources:
        print("(none)")

    import torch
    from gpt import GPT, Config, load_tokenizer, pick_device

    device = pick_device()
    ck = torch.load(os.path.join(a.out, "ckpt.pt"), map_location=device)
    cfg = Config(**ck["config"])
    model = GPT(cfg).to(device)
    model.load_state_dict(ck["model"])
    model.eval()
    tok = load_tokenizer(a.out)

    q_ids = tok.encode(f"\n\nQ: {a.query}\nA:")
    budget = cfg.block_size - a.tokens - len(q_ids)
    context = "\n\n".join(t[:600] for _, t in sources)
    ctx_ids = tok.encode(context)[:budget] if budget > 0 else []
    ids = ctx_ids + q_ids
    idx = torch.tensor([ids], dtype=torch.long, device=device)
    out = model.generate(idx, a.tokens, a.temperature, a.top_k)[0].tolist()
    print("\n=== model output ===")
    print(tok.decode(out[len(ids):]))
    print(f"\n(model context window: {cfg.block_size} tokens; used {len(ctx_ids)} for retrieved context)")


# --------------------------------------------------------------------------
# loop: collect -> continue training
# --------------------------------------------------------------------------
def ckpt_iter(out_dir):
    p = os.path.join(out_dir, "ckpt.pt")
    if not os.path.exists(p):
        return None
    import torch
    return torch.load(p, map_location="cpu")["iter"]


def cmd_loop(a):
    pending_chars = 0
    while True:
        print(f"\n[{time.strftime('%H:%M:%S')}] collecting ...")
        added, chars = collect(a.feeds, a.data, a.full)
        pending_chars += chars
        corpus_size = os.path.getsize(a.data) if os.path.exists(a.data) else 0
        print(f"  +{added} docs, pending {pending_chars:,} chars, corpus {corpus_size:,} bytes")

        if pending_chars >= a.min_new_chars and corpus_size >= a.min_corpus:
            cur = ckpt_iter(a.out)
            cmd = [sys.executable, os.path.join(HERE, "gpt.py"), "train",
                   "--data", a.data, "--out", a.out, "--eval_interval", "100"]
            if cur is None:  # first training run: byte-level BPE so new text never has unknown characters
                cmd += ["--tokenizer", "bpe", "--size", a.size, "--max_iters", str(a.steps)]
            else:            # continue from the checkpoint with a gentle learning rate
                cmd += ["--resume", "--reset_best", "--lr", "1e-4", "--warmup", "0",
                        "--max_iters", str(cur + a.steps)]
            print("  training:", " ".join(cmd))
            subprocess.run(cmd, check=False)
            pending_chars = 0
        if a.once:
            break
        time.sleep(a.every)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect")
    c.add_argument("--feeds", default="feeds.txt")
    c.add_argument("--data", default="data/live.txt")
    c.add_argument("--full", action="store_true", help="fetch full article pages, not just feed summaries")
    c.set_defaults(fn=cmd_collect)

    q = sub.add_parser("ask")
    q.add_argument("query")
    q.add_argument("--out", default="out")
    q.add_argument("--data", default="data/live.txt")
    q.add_argument("--k", type=int, default=3, help="snippets per source")
    q.add_argument("--no_web", action="store_true")
    q.add_argument("--tokens", type=int, default=80)
    q.add_argument("--temperature", type=float, default=0.7)
    q.add_argument("--top_k", type=int, default=40)
    q.set_defaults(fn=cmd_ask)

    l = sub.add_parser("loop")
    l.add_argument("--feeds", default="feeds.txt")
    l.add_argument("--data", default="data/live.txt")
    l.add_argument("--out", default="out")
    l.add_argument("--size", default="small", choices=["tiny", "small", "medium"])
    l.add_argument("--every", type=int, default=3600, help="seconds between collection rounds")
    l.add_argument("--steps", type=int, default=500, help="training steps per round")
    l.add_argument("--min_new_chars", type=int, default=200_000, help="train only after this much new text")
    l.add_argument("--min_corpus", type=int, default=500_000, help="don't train until corpus has this many bytes")
    l.add_argument("--full", action="store_true")
    l.add_argument("--once", action="store_true", help="run a single round and exit (good for cron)")
    l.set_defaults(fn=cmd_loop)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
