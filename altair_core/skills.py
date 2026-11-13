"""Bounded, on-demand skill discovery. Instructions are data, never executable code."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "skills"


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path


@lru_cache(maxsize=1)
def catalog():
    result = {}
    for path in sorted(ROOT.glob("*/SKILL.md")):
        # Only bounded metadata is kept in memory, not every instruction body.
        with path.open(encoding="utf-8") as source:
            if source.readline(512).strip() != "---":
                continue
            metadata = {}
            for _ in range(12):
                line = source.readline(512).strip()
                if line == "---":
                    break
                key, sep, value = line.partition(":")
                if sep:
                    metadata[key] = value.strip().strip('"')
        name = metadata.get("name", "")
        if name and name == path.parent.name:
            result[name] = Skill(name, metadata.get("description", "")[:200], path)
    return result


@lru_cache(maxsize=24)
def instructions(name):
    skill = catalog().get(name)
    if skill is None:
        return ""
    with skill.path.open(encoding="utf-8") as source:
        content = source.read(4000)
    pieces = content.split("---", 2)
    return pieces[-1].strip()[:700] if len(pieces) == 3 else ""


def select(question, has_image=False):
    if has_image:
        return "vision"
    from .toolkit import normalize
    text = normalize(question)
    if any(word in text for word in ("so sanh", "phuong an", "nen chon", "nen lam", "xu ly tinh huong")):
        return "decision"
    return "explain" if any(word in text for word in ("giai thich", "la gi", "tai sao", "vi sao")) else "conversation"
