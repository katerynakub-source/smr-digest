"""Rule-based categorisation (matches English and Russian text). Fast, deterministic, works without an AI key."""
import re

CATEGORIES = [
    {"slug": "smr", "name": "SMR", "full": "Small modular reactors"},
    {"slug": "tech", "name": "Technology", "full": "New technologies"},
    {"slug": "startups", "name": "Companies", "full": "New companies and startups"},
    {"slug": "policy", "name": "Policy", "full": "Regulation and strategy"},
]

RULES: dict[str, list[str]] = {
    "smr": [
        r"\bsmrs?\b", r"small modular", r"microreactor", r"micro-reactor", r"\bammr", r"\bamr\b",
        r"bwrx-?300", r"nuscale", r"voygr", r"rolls-royce smr", r"\bsmr-300", r"ap300", r"xe-100",
        r"natrium", r"\bacp100", r"linglong", r"ritm-?200", r"ритм-?200", r"\bммр\b", r"\bасмм\b",
        r"малы[хйем]+ модульн", r"малой мощности", r"плавуч", r"floating nuclear", r"ldr-50",
        r"нuward", r"nuward", r"aurora powerhouse", r"\boklo\b", r"\bkairos\b", r"hermes",
        r"брест", r"brest-od", r"шельф", r"elena", r"htr-pm",
    ],
    "tech": [
        r"fusion", r"термояд", r"токамак", r"tokamak", r"stellarator", r"\bhaleu\b", r"\btriso\b",
        r"molten salt", r"жидкосолев", r"расплав", r"fast reactor", r"быстр[а-я]+ нейтрон", r"sodium-cooled",
        r"lead-cooled", r"свинцов", r"натри", r"accident.tolerant", r"\batf\b", r"thorium", r"тори[йя]",
        r"closed fuel cycle", r"замкнут[а-я]+ топливн", r"digital twin", r"цифров[а-я]+ двойн",
        r"artificial intelligence|\bai\b", r"искусственн[а-я]+ интеллект", r"hydrogen", r"водород",
        r"isotope", r"изотоп", r"additive manufactur", r"аддитивн", r"high-temperature gas", r"htgr",
        r"research reactor", r"исследовательск[а-я]+ (ядерн|реактор)", r"\bмбир\b", r"\bmbir\b",
        r"new fuel", r"новое топливо", r"ремикс", r"remix fuel", r"\bлазер", r"laser enrichment",
    ],
    "startups": [
        r"start-?up", r"стартап", r"venture", r"венчур", r"series [abc]\b", r"raises? \$", r"funding round",
        r"investment of", r"инвестиц", r"seed round", r"\bipo\b", r"spac", r"newly formed", r"new company",
        r"founded", r"основан[а-я]* компан", r"acquires?", r"acquisition", r"приобрет", r"merger",
        r"\bmou\b", r"memorandum", r"меморандум", r"partnership", r"партн[её]рств", r"joint venture",
        r"совместн[а-я]+ предприят", r"newcleo", r"steady energy", r"last energy", r"blue energy", r"deep fission",
        r"radiant", r"valar atomics", r"aalo", r"thorizon", r"copenhagen atomics", r"naarea", r"jimmy energy",
    ],
    "policy": [
        r"licen[cs]", r"лиценз", r"regulator", r"регулятор", r"ростехнадзор", r"\bnrc\b", r"\bonr\b",
        r"\bcnsc\b", r"\bgda\b", r"generic design assessment", r"construction permit", r"разрешени",
        r"strategy", r"стратеги", r"policy", r"политик", r"legislation", r"закон", r"law\b", r"bill\b",
        r"taxonomy", r"таксоном", r"government", r"правительств", r"ministry", r"министерств", r"minister",
        r"министр", r"\biaea\b", r"магатэ", r"european commission", r"еврокомисс", r"\beu\b", r"\bес\b",
        r"cop\d+", r"paris agreement", r"парижск", r"subsid", r"субсид", r"tender", r"тендер", r"roadmap",
        r"дорожн[а-я]+ карт", r"executive order", r"указ", r"safety review", r"approval", r"одобр",
    ],
}

_COMPILED = {k: [re.compile(p, re.I) for p in v] for k, v in RULES.items()}


def classify(*texts: str) -> list[str]:
    blob = " ".join(t for t in texts if t)
    tags = []
    for slug, patterns in _COMPILED.items():
        hits = sum(1 for p in patterns if p.search(blob))
        if hits >= 1:
            tags.append(slug)
    return tags
