from enum import Enum


class ContextType(str, Enum):
    JOB_DESCRIPTION = "job_description"
    JOB_DEFINITION = "job_definition"
    RESUME = "resume"
    TASK = "task"
    REFLECTION = "reflection"
    USER_SIGNAL = "user_signal"
    CONTENT = "content"


_CONTEXT_HINTS = {
    ContextType.JOB_DESCRIPTION: "A job description posted by an employer.",
    ContextType.JOB_DEFINITION: "A structured job definition or role profile.",
    ContextType.RESUME: "A candidate resume or CV describing professional experience.",
    ContextType.TASK: "A work task, ticket, or assignment description.",
    ContextType.REFLECTION: "An employee reflection, self-assessment, or performance narrative.",
    ContextType.USER_SIGNAL: "User behavioral signals such as searches, clicks, or learning activity.",
    ContextType.CONTENT: "Learning content metadata such as course titles, abstracts, or transcripts.",
}

PROMPTS = {
    ctx: (
        f"You are a skill taxonomy extractor. Context type: {ctx.value}. {hint}\n"
        "Extract concrete skills, technologies, methods, or competencies explicitly present "
        "or strongly implied by the text.\n"
        'Reply with JSON only: {"skills": ["...", "..."]}'
    )
    for ctx, hint in _CONTEXT_HINTS.items()
}
