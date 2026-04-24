"""JSON persistence for SkillRun and round artifacts.

Layout
------
    <run_dir>/
        config.json                  frozen Optimizer config
        seed_skill.md                the starting SKILL.md
        champion.md                  current champion
        rounds/
            round_000/
                candidate.md
                lint.json
                skill_runs.jsonl     one per eval case
                verdict.json         {decision, ci, effect_size, linter}
            round_001/
                ...
        final.json                   {champion_path, rounds, decision}

Everything is plain JSON so diffs are readable and external tools can
inspect runs without importing probe.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from probe.schemas import SkillRun


# ---------- helpers ----------


def _to_jsonable(obj: Any) -> Any:
    """Recursively convert pydantic/dataclass/enum to plain dict/list/primitives."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if is_dataclass(obj):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    if hasattr(obj, "value"):  # enum
        return obj.value
    return obj


def _stable_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


# ---------- run dir layout ----------


class RunDir:
    """Thin wrapper over a run directory — creates + locates files."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "rounds").mkdir(exist_ok=True)

    # ---- top-level ----

    @property
    def config_path(self) -> Path: return self.root / "config.json"

    @property
    def seed_path(self) -> Path: return self.root / "seed_skill.md"

    @property
    def champion_path(self) -> Path: return self.root / "champion.md"

    @property
    def final_path(self) -> Path: return self.root / "final.json"

    # ---- per-round ----

    def round_dir(self, i: int) -> Path:
        p = self.root / "rounds" / f"round_{i:03d}"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def candidate_path(self, i: int) -> Path:
        return self.round_dir(i) / "candidate.md"

    def lint_path(self, i: int) -> Path:
        return self.round_dir(i) / "lint.json"

    def skill_runs_path(self, i: int) -> Path:
        return self.round_dir(i) / "skill_runs.jsonl"

    def verdict_path(self, i: int) -> Path:
        return self.round_dir(i) / "verdict.json"

    # ---- writers ----

    def write_json(self, path: Path, obj: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(_to_jsonable(obj), f, ensure_ascii=False, indent=2)

    def write_skill_runs(self, i: int, runs: list[SkillRun]) -> None:
        path = self.skill_runs_path(i)
        with path.open("w", encoding="utf-8") as f:
            for r in runs:
                f.write(json.dumps(r.model_dump(), ensure_ascii=False) + "\n")

    def read_skill_runs(self, i: int) -> list[SkillRun]:
        path = self.skill_runs_path(i)
        out = []
        if not path.exists():
            return out
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(SkillRun(**json.loads(line)))
        return out

    def write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    # ---- discovery ----

    def list_rounds(self) -> list[int]:
        base = self.root / "rounds"
        if not base.exists():
            return []
        out = []
        for d in base.iterdir():
            if d.is_dir() and d.name.startswith("round_"):
                try:
                    out.append(int(d.name.split("_", 1)[1]))
                except ValueError:
                    pass
        return sorted(out)


def make_skill_run(
    *,
    input_text: str,
    response: str,
    skill_md: str,
    id_seed: str | None = None,
) -> SkillRun:
    return SkillRun(
        id=id_seed or datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S%f"),
        skill_version_hash=_stable_hash(skill_md),
        input=input_text,
        response=response,
    )
