"""Supply chain: open and recently awarded nuclear-sector tenders from free official procurement databases.

- EU: TED (Tenders Electronic Daily) search API — filtered to nuclear-specific CPV codes
  or known nuclear buyers, because a plain "nuclear" text search also returns hospital
  radiopharmaceuticals and unrelated notices.
- UK: Contracts Finder search API — several nuclear keywords and buyer names.
IAEA tenders are published on UNGM, which does not allow automated searching, so the
app links to it instead.
"""
from __future__ import annotations

import asyncio
import html
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from .sources import HTTP

log = logging.getLogger("tenders")

LOOKBACK_DAYS = 75

# CPV codes that are nuclear by definition
NUCLEAR_CPV = {
    "09340000": "Nuclear fuel", "09341000": "Nuclear fuel", "09342000": "Nuclear fuel",
    "42150000": "Reactors & parts", "42151000": "Reactors & parts", "42152000": "Reactors & parts",
    "45251110": "Plant construction",
    "90521000": "Radioactive waste", "90521100": "Radioactive waste", "90521200": "Radioactive waste",
    "90521300": "Radioactive waste", "90521400": "Radioactive waste", "90521410": "Radioactive waste",
    "90521420": "Radioactive waste", "90521500": "Radioactive waste", "90521510": "Radioactive waste",
    "90521520": "Radioactive waste",
}

# Buyers whose procurement is essentially all nuclear (matched in TED's buyer-name field)
NUCLEAR_BUYERS_EU = [
    "Teollisuuden Voima", "Posiva", "Fennovoima", "Svensk Kärnbränslehantering", "Forsmarks Kraftgrupp",
    "Ringhals", "Elektrárna Dukovany", "Elektrárna Temelín", "Polskie Elektrownie Jądrowe", "Paks II",
    "Paksi Atomerőmű", "Slovenské elektrárne", "JAVYS", "Kozloduy", "Nuclearelectrica",
    "Nuklearna elektrarna Krško", "ENRESA", "SOGIN", "énergie atomique", "ANDRA", "Orano", "Framatome",
    "Fusion for Energy", "ITER Organization", "SCK CEN", "COVRA", "Ignalina", "Bundesgesellschaft für Endlagerung",
    "Zwischenlagerung", "Kerntechnische Entsorgung", "EWN Entsorgungswerk",
]

UK_KEYWORDS = ["nuclear", "Sellafield", "decommissioning", "radioactive", "reactor", "fusion energy",
               "Sizewell", "Hinkley Point", "UKAEA", "Nuclear Restoration Services", "AWE", "Dounreay"]

# medical isotopes/radiopharmaceuticals share codes and words with nuclear power — drop them
MEDICAL = re.compile(r"radiofarm|radiopharm|radiofármac|радиофарм|\bfdg\b|psma|lutet|gallium|technet|brachy|"
                     r"hospital|klinik|szpital|nemocnic|bolni|болниц|ziekenhuis|spital|sjukhus|ospedal|medic|"
                     r"oncolog|onkolo|patient|leczni", re.I)
# words for "nuclear" in EU languages: required when only the plant-construction code matched
NUCLEAR_WORD = re.compile(r"nuclear|nucléaire|nucleare|jądrow|jadern|jadrov|kern|atom|nukle|ядрен|πυρην|"
                          r"ydinvoima|kärnkraft|reactor|reaktor", re.I)

TED_OPEN_TYPES = "cn-standard cn-social cn-desg pin-cfc-standard pin-cfc-social pin-only pin-rtl can-standard can-social"


def _first(d) -> str:
    """TED multilingual fields: {"eng": "...", "fra": "..."} or {"fra": ["..."]}."""
    if not d:
        return ""
    if isinstance(d, dict):
        v = d.get("eng") or d.get("ENG") or next(iter(d.values()))
    else:
        v = d
    if isinstance(v, list):
        v = v[0] if v else ""
    return str(v)


def _date(s: str | None) -> str | None:
    if not s:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else None


def _category(cpvs: list[str], text: str) -> str:
    for c in cpvs:
        if c in NUCLEAR_CPV:
            return NUCLEAR_CPV[c]
    t = text.lower()
    rules = [("Radioactive waste", r"waste|decommission|démantèlement|dismantl|endlager|repository"),
             ("Fusion", r"fusion|tokamak|iter\b"),
             ("Plant construction", r"construct|civil works|building|bau"),
             ("Nuclear fuel", r"\bfuel\b|uranium|enrich"),
             ("Engineering & services", r"engineer|design|consult|study|services|support"),
             ("Equipment", r"supply|equipment|pump|valve|crane|cable|instrument")]
    for name, rx in rules:
        if re.search(rx, t):
            return name
    return "Other"


async def fetch_ted(client: httpx.AsyncClient) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d")
    cpv = " ".join(NUCLEAR_CPV)
    buyers = " ".join(f'"{b}"' for b in NUCLEAR_BUYERS_EU)
    query = (f"(classification-cpv IN ({cpv}) OR buyer-name~({buyers})) "
             f"AND PD>={since} AND notice-type IN ({TED_OPEN_TYPES})")
    fields = ["publication-number", "notice-title", "publication-date", "buyer-name", "buyer-country",
              "deadline-receipt-tender-date-lot", "classification-cpv", "notice-type"]
    out, page = [], 1
    while page <= 5:
        r = await client.post("https://api.ted.europa.eu/v3/notices/search",
                              json={"query": query, "fields": fields, "limit": 100, "page": page})
        r.raise_for_status()
        notices = r.json().get("notices", [])
        for n in notices:
            pub = n["publication-number"]
            title = _first(n.get("notice-title"))
            # TED English titles look like "Country – CPV label – original title"
            parts = [p.strip() for p in title.split(" – ")]
            short = parts[-1] if len(parts) >= 3 else title
            buyer = _first(n.get("buyer-name"))
            blob = f"{title} {buyer}"
            cpvs_set = set(n.get("classification-cpv") or [])
            known_buyer = any(b.lower() in buyer.lower() for b in NUCLEAR_BUYERS_EU)
            if MEDICAL.search(blob):
                continue
            if not known_buyer and not (cpvs_set & (set(NUCLEAR_CPV) - {"45251110"})) and not NUCLEAR_WORD.search(blob):
                continue  # matched only via the construction code, with no nuclear wording: likely misfiled
            deadlines = sorted(filter(None, (_date(d) for d in (n.get("deadline-receipt-tender-date-lot") or []))))
            cpvs = list(dict.fromkeys(n.get("classification-cpv") or []))
            out.append({
                "id": f"ted-{pub}",
                "source": "EU · TED",
                "region": "EU",
                "title": html.unescape(short),
                "subject": parts[1] if len(parts) >= 3 else None,
                "buyer": buyer,
                "country": (n.get("buyer-country") or [""])[0],
                "published": _date(n.get("publication-date")),
                "deadline": deadlines[0] if deadlines else None,
                "kind": ("Awarded" if n.get("notice-type", "").startswith("can")
                         else "Prior information" if n.get("notice-type", "").startswith("pin-only") else "Tender"),
                "category": _category(cpvs, title),
                "value": None,
                "url": f"https://ted.europa.eu/en/notice/-/detail/{pub}",
            })
        if len(notices) < 100:
            break
        page += 1
        await asyncio.sleep(1.5)  # TED rate-limits rapid requests
    return out


async def fetch_uk(client: httpx.AsyncClient) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    seen, out = set(), []
    for kw in UK_KEYWORDS:
        await asyncio.sleep(2)  # Contracts Finder rate-limits bursts
        for attempt in range(3):
            r = await client.post(
                "https://www.contractsfinder.service.gov.uk/api/rest/2/search_notices/json",
                json={"searchCriteria": {"types": ["Contract", "Pipeline", "EarlyEngagement", "Opportunity"],
                                     "statuses": ["Open", "Awarded"], "keyword": kw, "publishedFrom": since}, "size": 100})
            if r.status_code != 429:
                break
            await asyncio.sleep(20 * (attempt + 1))
        r.raise_for_status()
        for hit in r.json().get("noticeList", []):
            i = hit["item"]
            if i["id"] in seen:
                continue
            text = f"{i.get('title', '')} {i.get('description', '')} {i.get('organisationName', '')}"
            # keyword search is broad ("reactor", "fusion"): require a nuclear signal in the notice itself
            if not re.search(r"nuclear|sellafield|radioactiv|reactor|fusion|sizewell|hinkley|ukaea|atomic|"
                             r"dounreay|magnox|\bsmr\b", text, re.I):
                continue
            seen.add(i["id"])
            ptype = i.get("noticeType") or ""
            out.append({
                "id": f"uk-{i['id']}",
                "source": "UK · Contracts Finder",
                "region": "UK",
                "title": html.unescape(i.get("title", "")).strip(),
                "subject": None,
                "buyer": i.get("organisationName", ""),
                "country": "GBR",
                "published": _date(i.get("publishedDate")),
                "deadline": _date(i.get("deadlineDate")),
                "kind": ("Awarded" if i.get("noticeStatus") == "Awarded"
                         else "Early engagement" if ptype in ("EarlyEngagement", "Pipeline") else "Tender"),
                "category": _category([], text),
                "value": i.get("valueHigh") or i.get("valueLow") or None,
                "url": f"https://www.contractsfinder.service.gov.uk/Notice/{i['id']}",
            })
    return out


async def fetch_all() -> dict:
    results, errors = [], {}
    async with httpx.AsyncClient(**HTTP) as client:
        for name, fn in (("EU · TED", fetch_ted), ("UK · Contracts Finder", fetch_uk)):
            try:
                results += await fn(client)
            except Exception as e:  # noqa: BLE001 — one registry down must not stop the other
                log.warning("tenders %s failed: %s", name, e)
                errors[name] = str(e)[:200]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # keep open items (no deadline = still listed as open) and prior-information notices
    results = [t for t in results if t["kind"] == "Awarded" or not t["deadline"] or t["deadline"] >= today]
    results.sort(key=lambda t: t["published"] or "", reverse=True)
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tenders": results, "errors": errors}


if __name__ == "__main__":
    data = asyncio.run(fetch_all())
    print(len(data["tenders"]), data["errors"])
    for t in data["tenders"][:25]:
        print(t["published"], t["country"], t["category"], "|", t["title"][:60], "|", t["buyer"][:35], "|", t["deadline"])
