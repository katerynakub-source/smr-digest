"""Source definitions and parsers (RSS + site-specific HTML scrapers)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (compatible; SMR-Digest/1.0; +news aggregator)"
HTTP = dict(headers={"User-Agent": UA}, timeout=25, follow_redirects=True)

BUILTIN_SOURCES = [
    dict(slug="wnn", name="World Nuclear News", url="https://www.world-nuclear-news.org/rss",
         homepage="https://www.world-nuclear-news.org", kind="rss", parser="rss", lang="en"),
    dict(slug="nucnet", name="NucNet", url="https://www.nucnet.org/feed.rss",
         homepage="https://www.nucnet.org", kind="rss", parser="rss", lang="en"),
    dict(slug="atomic-energy", name="Atomic Energy 2.0 (RU)", url="https://www.atomic-energy.ru/news/rss.xml",
         homepage="https://www.atomic-energy.ru", kind="rss", parser="rss", lang="ru"),
    dict(slug="wna", name="World Nuclear Association", url="https://world-nuclear.org/news-and-media",
         homepage="https://world-nuclear.org", kind="html", parser="wna", lang="en"),
    dict(slug="ec-smr", name="European Commission · SMR",
         url="https://energy.ec.europa.eu/topics/nuclear-energy/small-modular-reactors_en",
         homepage="https://energy.ec.europa.eu", kind="html", parser="ec_smr", lang="en"),
    dict(slug="nauka-rosatom", name="Rosatom Science (CAIR)", url="https://naukarosatom.ru/news/",
         homepage="https://naukarosatom.ru", kind="html", parser="nauka", lang="ru"),
    # IAEA ARIS is a reactor database, not a news feed: it backs the project catalog (see catalog.py).
]


@dataclass
class RawItem:
    url: str
    title: str
    published_at: datetime
    excerpt: str = ""
    content: str = ""
    image: str | None = None
    lang: str = "en"
    extra: dict = field(default_factory=dict)


# ---------- helpers ----------

def html_to_text(html: str) -> str:
    """Convert HTML to readable plain text with paragraph breaks."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "figure", "iframe", "noscript"]):
        t.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    blocks = []
    for el in soup.find_all(["p", "li", "h2", "h3", "h4", "blockquote"]):
        txt = el.get_text(" ", strip=True)
        if txt:
            blocks.append(("• " if el.name == "li" else "") + txt)
    text = "\n\n".join(blocks) if blocks else soup.get_text("\n", strip=True)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def first_image(html: str, base: str) -> str | None:
    if not html:
        return None
    img = BeautifulSoup(html, "html.parser").find("img")
    if img and img.get("src"):
        return urljoin(base, img["src"])
    return None


def to_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


RU_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6, "июля": 7,
    "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
EN_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}


async def fetch(client: httpx.AsyncClient, url: str) -> httpx.Response:
    r = await client.get(url)
    r.raise_for_status()
    return r


# ---------- parsers ----------

async def parse_rss(client: httpx.AsyncClient, src: dict) -> list[RawItem]:
    r = await fetch(client, src["url"])
    feed = feedparser.parse(r.content)
    items = []
    for e in feed.entries[:60]:
        link = e.get("link")
        title = (e.get("title") or "").strip()
        if not link or not title:
            continue
        dt = None
        for key in ("published_parsed", "updated_parsed"):
            if e.get(key):
                dt = datetime(*e[key][:6], tzinfo=timezone.utc)
                break
        if dt is None and e.get("published"):
            try:
                dt = parsedate_to_datetime(e["published"])
            except (TypeError, ValueError):
                pass
        summary_html = e.get("summary", "")
        full_html = ""
        # WNN puts the full article in <wnn:fullText>; content:encoded is mapped to e.content
        if e.get("wnn_fulltext"):
            full_html = e["wnn_fulltext"]
        elif e.get("content"):
            full_html = e["content"][0].get("value", "")
        image = None
        if e.get("media_content"):
            image = e["media_content"][0].get("url")
        elif e.get("enclosures"):
            enc = [x for x in e["enclosures"] if x.get("type", "").startswith("image")]
            image = enc[0].get("href") if enc else None
        image = image or first_image(full_html or summary_html, link)
        items.append(RawItem(
            url=link, title=title, published_at=to_utc(dt),
            excerpt=html_to_text(summary_html)[:600],
            content=html_to_text(full_html), image=image, lang=src["lang"],
        ))
    return items


async def parse_nauka(client: httpx.AsyncClient, src: dict) -> list[RawItem]:
    r = await fetch(client, src["url"])
    soup = BeautifulSoup(r.text, "html.parser")
    items, seen = [], set()
    for a in soup.select("a.news-title"):
        href = urljoin(src["url"], a.get("href", ""))
        if href in seen:
            continue
        seen.add(href)
        dt = None
        holder = a.find_parent(class_=["news-item", "news-main-item"]) or a.find_parent("div")
        date_el = holder.select_one(".news-date") if holder else None
        if date_el:
            day = date_el.find("b")
            rest = date_el.find("span")
            if day and rest:
                parts = rest.get_text(" ", strip=True).split()
                if len(parts) >= 2 and parts[0].lower() in RU_MONTHS:
                    dt = datetime(int(parts[1]), RU_MONTHS[parts[0].lower()], int(day.get_text(strip=True)),
                                  9, 0, tzinfo=timezone.utc)
        img = holder.find("img") if holder else None
        items.append(RawItem(
            url=href, title=a.get_text(" ", strip=True), published_at=to_utc(dt),
            image=urljoin(src["url"], img["src"]) if img and img.get("src") else None, lang="ru",
        ))
    return items


async def parse_ec_smr(client: httpx.AsyncClient, src: dict) -> list[RawItem]:
    """EC SMR topic page lists dated news as `<li>Type: <a>Title</a> (10 March 2026)</li>`."""
    r = await fetch(client, src["url"])
    soup = BeautifulSoup(r.text, "html.parser")
    items = []
    for li in soup.find_all("li"):
        a = li.find("a")
        m = re.search(r"\((\d{1,2}) ([A-Za-z]+) (\d{4})\)\s*$", li.get_text(" ", strip=True))
        if not a or not m or m.group(2).lower() not in EN_MONTHS:
            continue
        dt = datetime(int(m.group(3)), EN_MONTHS[m.group(2).lower()], int(m.group(1)), 9, tzinfo=timezone.utc)
        kind = li.get_text(" ", strip=True).split(":")[0]
        items.append(RawItem(
            url=urljoin(src["url"], a["href"]), title=a.get_text(" ", strip=True),
            published_at=dt, excerpt=f"{kind} · European Commission, SMR policy page", lang="en",
        ))
    return items


async def parse_wna(client: httpx.AsyncClient, src: dict) -> list[RawItem]:
    """WNA news hub: cards with .news_box_title. Many link to WNN (deduplicated later)."""
    r = await fetch(client, src["url"])
    soup = BeautifulSoup(r.text, "html.parser")
    items, seen = [], set()
    for title_el in soup.select(".news_box_title"):
        card = title_el.find_parent(class_="row") or title_el.parent
        a = card.find("a", href=True) if card else None
        if not a:
            continue
        href = urljoin(src["url"], a["href"])
        if href in seen:
            continue
        seen.add(href)
        text = card.get_text(" ", strip=True)
        m = re.search(r"(\d{1,2}) ([A-Za-z]+) (\d{4})", text)
        if not m or m.group(2).lower() not in EN_MONTHS:
            continue  # undated cards are publications/promos, not news
        dt = datetime(int(m.group(3)), EN_MONTHS[m.group(2).lower()], int(m.group(1)), 9, tzinfo=timezone.utc)
        bg = card.select_one("[style*=background-image]")
        img = None
        if bg:
            mm = re.search(r"url\('?([^')]+)", bg["style"])
            img = urljoin(src["url"], mm.group(1)) if mm else None
        items.append(RawItem(url=href, title=title_el.get_text(" ", strip=True),
                             published_at=dt, image=img, lang="en"))
    return items


async def parse_generic(client: httpx.AsyncClient, src: dict) -> list[RawItem]:
    """User-added site without RSS: collect article-looking links from the page."""
    r = await fetch(client, src["url"])
    soup = BeautifulSoup(r.text, "html.parser")
    host = urlparse(src["url"]).netloc
    items, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(src["url"], a["href"]).split("#")[0]
        title = a.get_text(" ", strip=True)
        path = urlparse(href).path
        if (urlparse(href).netloc != host or href in seen or len(title) < 35
                or path.count("/") < 2 or re.search(r"/(tag|category|page|author)/", path)):
            continue
        seen.add(href)
        items.append(RawItem(url=href, title=title, published_at=datetime.now(timezone.utc), lang=src["lang"]))
        if len(items) >= 30:
            break
    return items


PARSERS = {"rss": parse_rss, "nauka": parse_nauka, "ec_smr": parse_ec_smr,
           "wna": parse_wna, "generic": parse_generic}


async def discover(url: str) -> dict:
    """Inspect a user-supplied URL: is it a feed, or a page that links to one?"""
    async with httpx.AsyncClient(**HTTP) as client:
        r = await fetch(client, url)
        ctype = r.headers.get("content-type", "")
        parsed = feedparser.parse(r.content)
        if parsed.entries and ("xml" in ctype or "rss" in ctype or parsed.version):
            return dict(kind="rss", parser="rss", url=str(r.url),
                        name=parsed.feed.get("title") or urlparse(url).netloc,
                        lang=(parsed.feed.get("language") or "en")[:2])
        soup = BeautifulSoup(r.text, "html.parser")
        link = soup.find("link", attrs={"type": re.compile(r"(rss|atom)\+xml")})
        name = (soup.title.get_text(strip=True) if soup.title else urlparse(url).netloc)[:80]
        lang = (soup.html.get("lang") if soup.html else "en") or "en"
        if link and link.get("href"):
            return dict(kind="rss", parser="rss", url=urljoin(str(r.url), link["href"]), name=name, lang=lang[:2])
        return dict(kind="html", parser="generic", url=str(r.url), name=name, lang=lang[:2])


async def fetch_article_text(url: str) -> tuple[str, str | None]:
    """Readability-lite extraction for items whose feed lacks full text."""
    async with httpx.AsyncClient(**HTTP) as client:
        r = await fetch(client, url)
    if "pdf" in r.headers.get("content-type", ""):
        from .documents import pdf_bytes_to_text
        return pdf_bytes_to_text(r.content), None
    soup = BeautifulSoup(r.text, "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
        t.decompose()
    og = soup.find("meta", property="og:image")
    image = urljoin(url, og["content"]) if og and og.get("content") else None
    candidates = soup.select("article, main, .article-body, .news-detail, .ecl-container, .content, #content")
    best, best_len = None, 0
    for el in candidates or [soup.body or soup]:
        n = sum(len(p.get_text(strip=True)) for p in el.find_all("p"))
        if n > best_len:
            best, best_len = el, n
    return html_to_text(str(best)) if best else "", image
