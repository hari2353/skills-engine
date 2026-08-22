from datetime import date

from ..text import fold

ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowProvider:
    name = "arbeitnow"

    def __init__(self, fetch=None, page_size: int = 25, timeout: float = 20.0) -> None:
        self._fetch = fetch if fetch is not None else self._http_fetch
        self.page_size = page_size
        self.timeout = timeout

    def _http_fetch(self, page: int) -> dict:
        import httpx

        resp = httpx.get(ARBEITNOW_URL, params={"page": page}, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def fetch_postings(self, pages: int = 1) -> list[dict]:
        postings: list[dict] = []
        for page in range(1, pages + 1):
            data = self._fetch(page).get("data", [])
            postings.extend(data)
            if len(data) < self.page_size:
                break
        return postings


def posting_text(posting: dict) -> str:
    parts = [str(posting.get(key) or "") for key in ("title", "description", "tags")]
    return " ".join(parts)


def postings_to_events(engine, postings: list[dict], source: str | None = None) -> list[dict]:
    today = date.today().isoformat()
    events: list[dict] = []
    for posting in postings:
        result = engine.infer(posting_text(posting), emit_unknown=True)
        for skill in result["skills"]:
            event = {"ts": today, "type": "resolved", "skill_id": skill["skill_id"]}
            if source:
                event["source"] = source
            events.append(event)
        for raw in result["unresolved"]:
            event = {"ts": today, "type": "unresolved", "raw": fold(raw)}
            if source:
                event["source"] = source
            events.append(event)
    return events
