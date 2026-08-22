import csv
from pathlib import Path

from .models import Skill, SkillStatus, SkillTier

COLUMNS = ["skill_id", "name", "tier", "vendor", "locale", "parent_id", "status", "aliases"]

TIER_FILES = {
    SkillTier.MASTER: "master_skills.csv",
    SkillTier.EXTERNAL: "external_skills.csv",
    SkillTier.CUSTOM: "custom_skills.csv",
}


def _parse_row(row: dict) -> Skill:
    aliases = [a.strip() for a in row.get("aliases", "").split("|") if a.strip()]
    status = row.get("status") or SkillStatus.ACTIVE.value
    return Skill(
        skill_id=row["skill_id"],
        name=row["name"],
        tier=SkillTier(row["tier"]),
        vendor=row.get("vendor") or None,
        locale=row.get("locale") or "en",
        parent_id=row.get("parent_id") or None,
        status=SkillStatus(status),
        aliases=aliases,
    )


def _write_rows(path: Path, skills: list[Skill]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for s in skills:
            writer.writerow(
                {
                    "skill_id": s.skill_id,
                    "name": s.name,
                    "tier": s.tier.value,
                    "vendor": s.vendor or "",
                    "locale": s.locale,
                    "parent_id": s.parent_id or "",
                    "status": s.status.value,
                    "aliases": "|".join(s.aliases),
                }
            )


class TaxonomyStore:
    def __init__(self) -> None:
        self.skills: dict[str, Skill] = {}
        self.by_tier: dict[SkillTier, list[Skill]] = {t: [] for t in SkillTier}

    def load_dir(self, data_dir: Path) -> None:
        for tier, filename in TIER_FILES.items():
            path = data_dir / filename
            if not path.exists():
                continue
            with path.open(newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    skill = _parse_row(row)
                    self.skills[skill.skill_id] = skill
                    self.by_tier[tier].append(skill)

    def add_or_update(self, skill: Skill) -> None:
        self.skills[skill.skill_id] = skill
        bucket = self.by_tier[skill.tier]
        for i, existing in enumerate(bucket):
            if existing.skill_id == skill.skill_id:
                bucket[i] = skill
                return
        bucket.append(skill)

    def write_snapshot(self, snapshot_dir: Path) -> None:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        for tier, filename in TIER_FILES.items():
            _write_rows(snapshot_dir / filename, self.by_tier[tier])
