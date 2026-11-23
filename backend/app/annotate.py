"""Assystem relevance filter, section assignment and English translation of Russian items.

Sections shown in the app:
  smr    – small modular / advanced / micro reactors, fusion
  large  – large reactors: new build, operating fleet, life extension, decommissioning
  supply – supply chain, contracts, manufacturing, fuel
  (Russian-language items additionally appear in the "Russian" tab, in Russian.)

Relevance targets Assystem's business: nuclear engineering, new build (large & SMR),
licensing & safety, project management, operations support, decommissioning & waste,
fusion and the nuclear supply chain. General-interest items (medicine, schools, awards,
sport, weapons…) are dropped even when they come from nuclear outlets.
"""
from __future__ import annotations

import json
import logging
import re

from . import db, translate
from .tagger import RULES

log = logging.getLogger("annotate")


def _rx(words: list[str]) -> re.Pattern:
    return re.compile("|".join(words), re.I)


# must be about nuclear energy at all
CORE = _rx([
    r"\bnuclear\b",  # English outlets are nuclear-specialist; medicine/weapons are removed by NOISE
    r"reactor", r"\bnpp\b", r"\bsmrs?\b", r"\bamrs?\b", r"fusion", r"tokamak", r"\biter\b", r"uranium", r"\bhaleu\b",
    r"radioactive waste", r"decommission", r"\bаэс\b", r"\bпатэс\b", r"реактор", r"энергоблок", r"\bммр\b", r"\bасмм\b",
    r"термояд", r"уранов",
    r"ядерн[а-я]* (топлив|энерг|установ|отрасл|объект|безопасн|материал|остров)", r"атомн[а-я]* (станци|энергетик|ледокол)",
    r"радиоактивн[а-я]* отход", r"вывод[а-я]* из эксплуатации",
])

# Assystem business lines and markets — each hit adds to the score
BUSINESS = _rx([
    r"engineer", r"инжинирин", r"design", r"проектир", r"licen[cs]", r"лиценз", r"regulat", r"регулятор",
    r"ростехнадзор", r"safety", r"безопасност", r"construct", r"сооружен", r"строительств", r"commission",
    r"пуск", r"ввод[а-я]* в эксплуатацию", r"project", r"проект", r"decommission", r"демонтаж", r"waste", r"отход",
    r"outage", r"ремонт", r"life(time)? extension", r"long-term operation", r"продлен[а-я]* срока", r"digital twin",
    r"цифров", r"supply", r"постав", r"contract", r"контракт", r"tender", r"тендер", r"procure", r"закупк",
    r"new build", r"feasibility", r"site selection", r"площадк", r"grid", r"сеть", r"fuel", r"топлив", r"grid connection",
    r"power unit", r"энергоблок", r"strategy", r"стратег", r"investment", r"инвест", r"financ", r"финансир",
    r"partnership", r"agreement", r"соглашени", r"memorandum", r"меморандум", r"workforce", r"skills",
    r"hinkley", r"sizewell", r"epr2?\b", r"flamanville", r"penly", r"dukovany", r"paks", r"akkuyu", r"аккую",
    r"el dabaa", r"эль-дабаа", r"rooppur", r"руппур", r"barakah", r"saudi", r"poland", r"польш", r"czech",
    r"rolls-royce smr", r"nuward", r"bwrx", r"nuscale", r"ritm", r"ритм", r"brest", r"брест", r"iter\b",
])

# off-topic for Assystem even in nuclear outlets
NOISE = _rx([
    r"radiopharm", r"radiofarm", r"радиофарм", r"nuclear medicine", r"ядерн[а-я]* медицин", r"cancer", r"онколог",
    r"hospital", r"patient", r"пациент", r"школ", r"school", r"олимпиад", r"olympiad", r"студенческ", r"конкурс",
    r"competition for students", r"премия", r"prize", r"award ceremony", r"наград", r"волонт", r"volunteer", r"спорт",
    r"sport", r"football", r"футбол", r"дет(и|ей|ям)\b", r"children", r"юбилей", r"anniversary", r"музей", r"museum",
    r"weapon", r"warhead", r"боеголов", r"ядерн[а-я]* оружи", r"missile", r"ракет", r"sanction", r"санкци",
    r"фестивал", r"festival", r"концерт", r"concert", r"выставк[а-я]* картин", r"поздрав",
    r"электромобил", r"electric vehicle", r"зарядн[а-я]* (станц|сесси)", r"библиотек", r"library", r"атомных городов",
    r"городов присутствия", r"территори[яи] (опережающего )?развития", r"\bтор\b", r"благоустрой", r"туризм",
    r"tourism", r"социальн[а-я]* проект", r"образовательн", r"educational", r"университет", r"university",
    r"медиа", r"журналист", r"journalist", r"блогер", r"квест", r"экскурси", r"guided tour",
])

SMR = re.compile("|".join(RULES["smr"] + [
    r"fusion", r"tokamak", r"stellarator", r"\biter\b", r"термояд", r"токамак", r"advanced (reactor|nuclear)", r"gen(eration)? iv",
    r"molten salt", r"жидкосолев", r"high-temperature gas", r"\bhtgr\b", r"microreactor", r"микрореактор",
    r"fast reactor", r"быстр[а-я]+ нейтрон", r"\bhaleu\b", r"\btriso\b", r"lead-cooled", r"свинцов", r"\bмбир\b", r"\bmbir\b",
]), re.I)

LARGE = _rx([
    r"\bepr2?\b", r"vver", r"ввэр", r"ap1000", r"apr1[04]00", r"hualong", r"hpr1000", r"cap1[04]00", r"abwr",
    r"\bphwr\b", r"candu", r"bn-[0-9]", r"бн-[0-9]", r"hinkley", r"sizewell", r"flamanville", r"olkiluoto", r"penly",
    r"gravelines", r"dukovany", r"temel[ií]n", r"\bpaks\b", r"akkuyu", r"аккую", r"el dabaa", r"эль-дабаа",
    r"rooppur", r"руппур", r"barakah", r"kudankulam", r"куданкулам", r"vogtle", r"kozloduy", r"козлодуй", r"ostrovets",
    r"белорусск[а-я]+ аэс", r"leningrad", r"ленинградск", r"курск", r"kursk", r"нововоронеж", r"novovoronezh",
    r"gigawatt", r"\b\d+(\.\d+)?\s?gw\b", r"large reactor", r"lifetime extension", r"life extension",
    r"long-term operation", r"продлен[а-я]* срока", r"\boutage\b", r"планово-предупредительн", r"uprate", r"restart",
    r"palisades", r"diablo canyon", r"belene", r"lubiatowo", r"pomorskie", r"jaitapur", r"tianwan", r"tianwan",
    r"xudabao", r"sanaocun", r"zhangzhou", r"taishan", r"barakah", r"\bunit [1-9]\b", r"энергоблок",
])

SUPPLY = re.compile("|".join(RULES["supply"] + [
    r"enrichment", r"обогащени", r"uranium (supply|production|mine)", r"fuel fabrication", r"conversion",
    r"tvel", r"твэл", r"centrus", r"urenco", r"orano", r"fuel assembl", r"тепловыделяющ", r"spent fuel",
    r"отработавш[а-я]* (ядерн[а-я]* )?топлив", r"reprocessing", r"переработк", r"\bleu\+?", r"\bhaleu\b",
]), re.I)

# new-build programmes, siting, restarts, licence decisions, national plans
NEWBUILD = _rx([
    r"new nuclear", r"nuclear (programme|program|plan|power plant)", r"power plant", r"plant location", r"\bsite\b",
    r"location", r"restart", r"returning to operation", r"cleared for", r"licen[cs]e", r"approv", r"roadmap",
    r"master plan", r"pledge", r"tripl", r"\bunits?\b", r"test reactor", r"microreactor", r"haleu", r"uranium production",
    r"новых? (энергоблок|аэс)", r"площадк", r"лицензи", r"план[а-я]* сооружени",
])

ADVANCED_FALLBACK = _rx([r"fusion", r"термояд", r"advanced", r"innovati", r"инновац", r"research reactor", r"исследовательск"])
SUPPLY_FALLBACK = _rx([r"fuel", r"топлив", r"uranium", r"уран", r"isotope", r"изотоп"])

MIN_SCORE = 2.5


def classify(title: str, text: str) -> tuple[float, list[str]]:
    """Return (relevance score, sections). Score < MIN_SCORE means not relevant for Assystem."""
    blob = f"{title} {text}"
    if not CORE.search(blob):
        return 0.0, []
    noise = min(len(NOISE.findall(text)), 3)  # passing mentions in the body weigh less than in the title
    title_noise = bool(NOISE.search(title))
    # a clear technology/market match (SMR, large plant, supply chain) is itself a strong relevance signal
    tech_title = any(rx.search(title) for rx in (SMR, LARGE, SUPPLY, NEWBUILD))
    tech_text = any(rx.search(text) for rx in (SMR, LARGE, SUPPLY, NEWBUILD))
    score = (1 + min(len(BUSINESS.findall(blob)), 8) * 0.5 + (1.5 if tech_title else 0) + (0.5 if tech_text else 0)
             - noise * 0.75 - (3 if title_noise else 0))
    # sections: what the headline is about; if the headline is not explicit, the body's dominant topic
    rxs = {"smr": SMR, "large": LARGE, "supply": SUPPLY}
    sections = [k for k, rx in rxs.items() if rx.search(title)]
    if "smr" in sections and "large" in sections and not re.search(r"\bsmr|ммр|асмм|small modular|малой мощности|micro", title, re.I):
        sections.remove("smr")  # e.g. "BN-800 fast reactor" is a large plant, not an SMR
    if not sections:
        counts = {k: len(rx.findall(text)) for k, rx in rxs.items()}
        best = max(counts, key=counts.get)
        if counts[best]:
            sections = [best]
    if not sections:  # relevant but no clear home: closest tab
        sections.append("smr" if ADVANCED_FALLBACK.search(blob) else "supply" if SUPPLY_FALLBACK.search(blob) else "large")
    return round(score, 2), sections


def annotate_all(conn) -> dict:
    """Score/section every article; translate relevant Russian items that lack English text."""
    rows = conn.execute("SELECT id, lang, title, excerpt, content, bullets, title_en, bullets_en, excerpt_en "
                        "FROM articles WHERE kind='news'").fetchall()
    to_translate = []
    for r in rows:
        bullets = json.loads(r["bullets"]) if r["bullets"] else []
        text = " ".join(filter(None, [r["excerpt"], " ".join(bullets), (r["content"] or "")[:3000]]))
        score, sections = classify(r["title"], text)
        conn.execute("UPDATE articles SET relevance=?, sections=? WHERE id=?", (score, json.dumps(sections), r["id"]))
        if r["lang"] == "en":
            conn.execute("UPDATE articles SET title_en=?, bullets_en=?, excerpt_en=? WHERE id=?",
                         (r["title"], r["bullets"], r["excerpt"], r["id"]))
        elif score >= MIN_SCORE and not r["bullets_en"]:
            to_translate.append((r, bullets))
    translated = 0
    if to_translate and translate.enabled():
        for r, bullets in to_translate:
            parts = [r["title"], r["excerpt"] or ""] + bullets
            try:
                out = translate.translate(parts)
            except Exception as e:  # noqa: BLE001
                log.warning("translation failed for %s: %s", r["id"], e)
                continue
            conn.execute("UPDATE articles SET title_en=?, excerpt_en=?, bullets_en=? WHERE id=?",
                         (out[0], out[1] or None, json.dumps(out[2:], ensure_ascii=False), r["id"]))
            translated += 1
    elif to_translate:
        log.info("translator not configured: %d Russian items left untranslated", len(to_translate))
    return {"articles": len(rows), "translated": translated, "pending_translation": len(to_translate) - translated}
