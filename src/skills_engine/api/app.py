from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from ..config import Settings
from ..engine import SkillsEngine
from ..inference.contexts import ContextType
from ..lifecycle.models import LifecyclePolicy
from ..lifecycle.runner import LifecycleRunner


class InferRequest(BaseModel):
    text: str
    context_type: str = ContextType.JOB_DESCRIPTION.value
    locale: str = "en"


class NormalizeRequest(BaseModel):
    name: str
    locale: str = "en"


class FeedbackRequest(BaseModel):
    raw_input: str
    accepted: bool


def create_app(data_dir=None, enable_usage_logging: bool = False) -> FastAPI:
    settings = Settings(data_dir=data_dir)
    engine = SkillsEngine(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield

    application = FastAPI(title="Skills Intelligence Engine", version="0.1.0", lifespan=lifespan)

    @application.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    @application.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @application.get("/v1/taxonomy/stats")
    def taxonomy_stats() -> dict:
        return engine.stats()

    @application.post("/v1/skills/infer")
    def infer_skills(req: InferRequest) -> dict:
        try:
            ctx = ContextType(req.context_type)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"unknown context_type '{req.context_type}'")
        return engine.infer(req.text, ctx, req.locale, log_usage=enable_usage_logging)

    @application.post("/v1/skills/normalize")
    def normalize_skill(req: NormalizeRequest) -> dict:
        return engine.normalize(req.name, req.locale)

    @application.get("/v1/skills/search")
    def search_skills(q: str = Query(..., min_length=1), k: int = Query(5, ge=1, le=50)) -> dict:
        return {"query": q, "results": engine.search(q, k)}

    @application.post("/v1/feedback")
    def submit_feedback(req: FeedbackRequest) -> dict:
        return engine.feedback(req.raw_input, req.accepted)

    @application.get("/v1/model/weights")
    def model_weights() -> dict:
        if engine.ranker is None:
            raise HTTPException(status_code=404, detail="ranker disabled")
        return {"weights": engine.ranker.weights, "n_updates": engine.ranker.n_updates}

    @application.get("/v1/lifecycle/report")
    def lifecycle_report(today: str | None = None) -> dict:
        runner = LifecycleRunner(engine.store, engine.normalizer, settings.data_dir)
        day = date.fromisoformat(today) if today else date.today()
        policy = LifecyclePolicy()
        actions = runner.report(policy, day)
        return {"today": day.isoformat(), "actions": [a.model_dump(mode="json") for a in actions]}

    @application.post("/v1/lifecycle/run")
    def lifecycle_run(dry_run: bool = True, today: str | None = None) -> dict:
        runner = LifecycleRunner(engine.store, engine.normalizer, settings.data_dir)
        day = date.fromisoformat(today) if today else date.today()
        policy = LifecyclePolicy()
        actions = runner.report(policy, day)
        snapshot_dir = None
        if not dry_run:
            snapshot_dir = str(runner.apply(actions, policy, day))
        return {
            "today": day.isoformat(),
            "dry_run": dry_run,
            "applied": len(actions),
            "snapshot_dir": snapshot_dir,
            "actions": [a.model_dump(mode="json") for a in actions],
        }

    return application


app = create_app()
