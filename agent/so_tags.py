"""Tri thuc StackOverflow dang nhe: taxonomy Tags.xml (65k tags) de mo rong query
+ dinh huong mien (chong bia API). Stdlib only, lazy-load."""
import os
import re
import xml.etree.ElementTree as ET

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANDIDATES = [
    os.path.join(BASE, "so_data", "Tags.xml"),
    r"C:\Users\trinh\Downloads\database stackoverflow\so_tags.xml",
]

_INDEX = None


def _find_xml():
    for p in CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def load_index(min_count: int = 500):
    """{tag: count} chi tag pho bien. Cache RAM sau lan 1."""
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    _INDEX = {}
    fp = _find_xml()
    if not fp:
        return _INDEX
    try:
        for _ev, el in ET.iterparse(fp, events=("end",)):
            if el.tag != "row":
                continue
            try:
                c = int(el.get("Count", 0))
            except (TypeError, ValueError):
                c = 0
            if c >= min_count:
                _INDEX[el.get("TagName", "").lower()] = c
            el.clear()
    except ET.ParseError:
        pass
    return _INDEX


def detect(text: str, top_n: int = 6):
    """Tag SO xuat hien trong text, sort theo do pho bien."""
    idx = load_index()
    if not idx:
        return []
    low = " " + text.lower().replace("-", " ").replace("_", " ") + " "
    hits = []
    for tag, cnt in idx.items():
        t = tag.replace("-", " ").replace(".", " ")
        if len(t) >= 3 and (" " + t + " " in low or "+" in tag and tag in text.lower()):
            hits.append((cnt, tag))
    hits.sort(reverse=True)
    return [t for _c, t in hits[:top_n]]


def context_line(query: str, file_text: str = "") -> str:
    """1 dong boi canh mien cho prompt. Re neu khong co data."""
    tags = detect(query + " " + file_text[:2000])
    if not tags:
        return ""
    return "Tags lien quan (StackOverflow): " + ", ".join(tags) + "."
