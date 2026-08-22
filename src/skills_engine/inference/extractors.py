import json
import re

import httpx

from ..taxonomies.models import Skill, SkillStatus
from ..text import fold
from .contexts import PROMPTS, ContextType

STOPWORDS = {
    "and", "or", "the", "a", "an", "of", "for", "with", "in", "on", "to", "using", "use",
    "strong", "experience", "knowledge", "works", "work", "working", "skills", "skilled",
    "plus", "etc", "years", "year", "new", "familiar", "proficient", "expertise", "role",
}


class RuleBasedExtractor:
    def __init__(self, skills: list[Skill]) -> None:
        surfaces: dict[str, str] = {}
        for s in skills:
            if s.status in (SkillStatus.DEPRECATED, SkillStatus.ARCHIVED):
                continue
            for label in [s.name, *s.aliases]:
                surfaces.setdefault(fold(label), s.name)
        self.canonical_by_surface = dict(sorted(surfaces.items(), key=lambda kv: kv[0].count(" "), reverse=True))
        self.max_words = max((k.count(" ") + 1 for k in self.canonical_by_surface), default=1)

    def extract(self, text: str, context_type: ContextType, emit_unknown: bool = False) -> list[str]:
        words = fold(text).split()
        found: list[str] = []
        seen: set[str] = set()
        matched = [False] * len(words)
        i = 0
        while i < len(words):
            match = None
            for size in range(min(self.max_words, len(words) - i), 0, -1):
                surface = " ".join(words[i : i + size])
                canonical = self.canonical_by_surface.get(surface)
                if canonical:
                    match = (size, canonical)
                    break
            if match:
                size, canonical = match
                for j in range(i, i + size):
                    matched[j] = True
                if canonical not in seen:
                    seen.add(canonical)
                    found.append(canonical)
                i += size
            else:
                i += 1
        if emit_unknown:
            for candidate in self._unknown_phrases(words, matched):
                if candidate not in seen:
                    seen.add(candidate)
                    found.append(candidate)
        return found

    def _unknown_phrases(self, words: list[str], matched: list[bool], limit: int = 10) -> list[str]:
        phrases: list[str] = []
        run: list[str] = []

        def flush() -> None:
            if 2 <= len(run) <= 4:
                phrases.append(" ".join(run))
            run.clear()

        for idx, word in enumerate(words):
            if matched[idx] or word in STOPWORDS or len(word) < 3:
                flush()
                continue
            run.append(word)
            if len(run) == 4:
                flush()
        flush()
        return phrases[:limit]


class OpenAICompatExtractor:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def extract(self, text: str, context_type: ContextType, emit_unknown: bool = False) -> list[str]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": PROMPTS[context_type]},
                {"role": "user", "content": text},
            ],
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = httpx.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return parse_skills_json(content)


def parse_skills_json(content: str) -> list[str]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    data = json.loads(content)
    items = data.get("skills", []) if isinstance(data, dict) else data
    return [str(s).strip() for s in items if str(s).strip()]


def get_extractor(skills: list[Skill], llm_base_url: str | None, llm_api_key: str, llm_model: str):
    if llm_base_url:
        return OpenAICompatExtractor(llm_base_url, llm_api_key, llm_model)
    return RuleBasedExtractor(skills)
