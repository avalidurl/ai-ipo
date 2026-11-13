#!/usr/bin/env python3
"""Pull IPO forecasts for five private AI companies and write data.json.

Venues ask different questions. This script does not blend them.
Polymarket and Manifold have open CORS; Kalshi does not,
so the page reads this file instead of calling them from the browser.
Metaculus was dropped: its official API requires an account token.
"""

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

OUT = "data.json"
UA = "ai-ipo-forecasts/1.0 (+https://github.com/avalidurl/ai-ipo; https://gokhanturhan.com/ai-ipo/)"

COMPANIES = [
    {
        "id": "openai",
        "name": "OpenAI",
        "poly_event": "openai-ipo-by",
        "kalshi_series": "KXIPOOPENAI",
        "manifold_id": "plzUIl06Oc",
    },
    {
        "id": "anthropic",
        "name": "Anthropic",
        "poly_event": "anthropic-ipo-by",
        "kalshi_series": "KXIPOANTHROPIC",
        "manifold_id": "0Ityc29NlO",
    },
    {
        "id": "xai",
        "name": "xAI",
        "poly_event": None,
        "poly_search": "xAI IPO",
        "kalshi_series": "KXIPOXAI",
        "manifold_id": None,
    },
    {
        "id": "databricks",
        "name": "Databricks",
        "poly_event": "databricks-ipo-closing-market-cap-20260630152322605",
        "kalshi_series": "KXIPODATABRICKS",
        "manifold_id": "u2qut2EPP5",
    },
    {
        "id": "perplexity",
        "name": "Perplexity",
        "poly_event": "perplexity-ipo-closing-market-cap",
        "kalshi_series": "KXIPOPERPLEXITY",
        "manifold_id": None,
    },
]

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def get(url, accept="application/json"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=45) as res:
        return res.read().decode("utf-8", "replace")


def pct(p):
    return f"{p * 100:.1f}%"


def fmt_date(d):
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def parse_date(text):
    m = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})",
        text,
        re.I,
    )
    if not m:
        return None
    month = MONTHS[m.group(1).lower().rstrip(".")]
    return datetime(int(m.group(3)), month, int(m.group(2)), tzinfo=timezone.utc)


def is_eoy_2026(d):
    return (d.year, d.month, d.day) in {(2026, 12, 31), (2027, 1, 1)}


def summarize_ladder(points, kind):
    """points: date, p, quote. kind is 'by' or 'before'."""
    points = sorted((pt for pt in points if pt["date"] and pt["p"] is not None), key=lambda pt: pt["date"])
    if not points:
        return None
    focus = next((pt for pt in points if pt["p"] >= 0.5), points[-1])
    word = "before" if kind == "before" else "by"
    lines = [focus["quote"]]
    eoy = next((pt for pt in points if is_eoy_2026(pt["date"])), None)
    if eoy and eoy is not focus:
        lines.append(f"{pct(eoy['p'])} {word} {fmt_date(eoy['date'])}")
    return {
        "headline": f"{pct(focus['p'])} {word} {fmt_date(focus['date'])}",
        "lines": lines,
        "href": focus.get("href"),
    }


def cell(name, headline, lines, href):
    return {"name": name, "headline": headline, "lines": [ln for ln in lines if ln], "href": href}


def empty(name, href, why):
    return cell(name, "No open market", [why], href)


def failed(name, href, why):
    return cell(name, "Unavailable", [why], href)


def poly_price(market):
    raw = market.get("outcomePrices")
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not raw:
        return None
    return float(raw[0])


def polymarket(company):
    href = "https://polymarket.com"
    slug = company.get("poly_event")
    if not slug and company.get("poly_search"):
        found = polymarket_search(company)
        if not found:
            return empty("Polymarket", href, "No Polymarket event titled as this company's IPO.")
        slug = found
    if not slug:
        return empty("Polymarket", href, "No IPO event on Polymarket.")
    href = f"https://polymarket.com/event/{slug}"
    data = json.loads(get(f"https://gamma-api.polymarket.com/events?slug={slug}"))
    event = data[0] if isinstance(data, list) else data
    markets = [m for m in (event.get("markets") or []) if not m.get("closed")]
    ladder = []
    complement = None
    for market in markets:
        question = market.get("question") or ""
        price = poly_price(market)
        when = parse_date(question)
        lower = question.lower()
        if when and "not ipo" not in lower and "ipo" in lower:
            ladder.append({"date": when, "p": price, "quote": question, "href": href})
        elif "not ipo by" in lower and price is not None:
            complement = (question, price)
    if ladder:
        summary = summarize_ladder(ladder, "by")
        summary["name"] = "Polymarket"
        summary["href"] = href
        return summary
    if complement:
        question, price = complement
        others = []
        for market in markets:
            q = (market.get("question") or "").lower()
            if "not ipo by" in q:
                continue
            p = poly_price(market)
            if p is not None:
                others.append(p)
        total = price + sum(others)
        when = parse_date(question)
        if 0.9 <= total <= 1.15 and when:
            return cell(
                "Polymarket",
                f"{pct(1 - price)} by {fmt_date(when)}",
                [
                    question,
                    "Taken from the complement of that bucket. The event's buckets sum to about 1.",
                ],
                href,
            )
        return cell(
            "Polymarket",
            "No clean price",
            [
                question,
                f"The buckets on this event sum to {total:.2f}, so the printed yes-price is not a usable probability.",
            ],
            href,
        )
    return empty("Polymarket", href, "The event has no open IPO-timing contract.")


def polymarket_search(company):
    query = company["poly_search"]
    data = json.loads(get("https://gamma-api.polymarket.com/public-search?q=" + urllib.parse.quote(query)))
    name = company["name"].lower()
    for event in data.get("events") or []:
        title = (event.get("title") or "").lower()
        if name in title and "ipo" in title:
            return event.get("slug")
    return None


def kalshi_price(market):
    def num(key):
        raw = market.get(key)
        if raw is None or raw == "":
            return None
        return float(raw)

    bid, ask, last = num("yes_bid_dollars"), num("yes_ask_dollars"), num("last_price_dollars")
    if bid is not None and ask is not None and 0 <= bid <= ask <= 1 and (ask - bid) <= 0.25 and not (bid == 0 and ask >= 0.9):
        return (bid + ask) / 2
    if last is not None and 0 < last < 1:
        return last
    if bid is not None and ask is not None and ask > bid:
        return (bid + ask) / 2
    return last


def kalshi(company):
    series = company["kalshi_series"]
    href = f"https://kalshi.com/markets/{series.lower()}"
    data = json.loads(get(
        f"https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker={series}&limit=100&status=open"
    ))
    markets = data.get("markets") or []
    if not markets:
        return empty("Kalshi", "https://kalshi.com", "No open series for an announced IPO.")
    points = []
    for market in markets:
        label = market.get("yes_sub_title") or market.get("subtitle") or market.get("title") or ""
        when = parse_date(label)
        price = kalshi_price(market)
        if when and price is not None:
            points.append({"date": when, "p": price, "quote": label, "href": href})
    summary = summarize_ladder(points, "before")
    if not summary:
        return empty("Kalshi", href, "Series is open, but none of the strikes have a usable price.")
    summary["lines"].insert(0, "Chance the company has officially announced an IPO before that date.")
    summary["name"] = "Kalshi"
    summary["href"] = href
    return summary


def manifold(company):
    mid = company.get("manifold_id")
    href = "https://manifold.markets"
    if not mid:
        return empty("Manifold", "https://manifold.markets/search?s=" + urllib.parse.quote(company["name"] + " IPO"), "No standalone IPO market.")
    market = json.loads(get(f"https://api.manifold.markets/v0/market/{mid}"))
    href = market.get("url") or href
    question = market.get("question") or ""
    if market.get("isResolved"):
        return empty("Manifold", href, "The tracked market has resolved.")
    kind = market.get("outcomeType")
    if kind == "BINARY":
        p = market.get("probability")
        if p is None:
            return failed("Manifold", href, "Binary market returned no probability.")
        return cell("Manifold", pct(p), [question], href)
    answers = market.get("answers") or []
    exclusive = bool(market.get("shouldAnswersSumToOne"))
    buckets = []
    for answer in answers:
        text = answer.get("text") or ""
        p = answer.get("probability")
        if p is None:
            continue
        buckets.append((text, float(p)))
    if not buckets:
        return empty("Manifold", href, "Market has no priced answers.")
    if exclusive:
        total = 0
        median = buckets[-1][0]
        for text, p in buckets:
            total += p
            if total >= 0.5:
                median = text
                break
        top_text, top_p = max(buckets, key=lambda item: item[1])
        return cell(
            "Manifold",
            median,
            [question, f"{pct(top_p)} of the probability sits on {top_text}."],
            href,
        )
    return cell("Manifold", pct(max(p for _, p in buckets)), [question], href)


def safe(name, href, fn):
    try:
        return fn()
    except Exception as exc:
        return failed(name, href, f"{type(exc).__name__}: {exc}")


def main():
    companies = []
    for company in COMPANIES:
        venues = [
            safe("Polymarket", "https://polymarket.com", lambda c=company: polymarket(c)),
            safe("Kalshi", "https://kalshi.com", lambda c=company: kalshi(c)),
            safe("Manifold", "https://manifold.markets", lambda c=company: manifold(c)),
        ]
        companies.append({"id": company["id"], "name": company["name"], "venues": venues})
    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "companies": companies,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    print(f"wrote {OUT} at {payload['updated']}")
    for company in companies:
        bits = [f"{v['name']}: {v['headline']}" for v in company["venues"]]
        print(company["name"] + " — " + " | ".join(bits))


if __name__ == "__main__":
    main()
