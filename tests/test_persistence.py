"""Tests for persistence and SkillRun threading."""

import json
from pathlib import Path

from caliper.persistence import RunDir, make_skill_run
from caliper.schemas import JudgeScore, SkillRun


def test_rundir_layout(tmp_path: Path):
    rd = RunDir(tmp_path / "r1")
    assert rd.config_path.parent == tmp_path / "r1"
    assert "rounds" in str(rd.round_dir(2))
    assert "round_002" in str(rd.round_dir(2))


def test_write_read_skill_runs(tmp_path: Path):
    rd = RunDir(tmp_path / "r1")
    runs = [
        SkillRun(
            id="a",
            skill_version_hash="h1",
            input="i",
            response="r",
            judges=[
                JudgeScore(
                    model_family="qwen",
                    model_id="qwen-max",
                    rubric_item_id="a",
                    score=0.8,
                )
            ],
        ),
        SkillRun(id="b", skill_version_hash="h1", input="i2", response="r2"),
    ]
    rd.write_skill_runs(0, runs)
    back = rd.read_skill_runs(0)
    assert len(back) == 2
    assert back[0].id == "a"
    assert back[0].judges[0].score == 0.8


def test_make_skill_run_hashes():
    r1 = make_skill_run(input_text="x", response="y", skill_md="# S1")
    r2 = make_skill_run(input_text="x", response="y", skill_md="# S2")
    assert r1.skill_version_hash != r2.skill_version_hash


def test_list_rounds(tmp_path: Path):
    rd = RunDir(tmp_path / "r2")
    rd.round_dir(0)
    rd.round_dir(1)
    rd.round_dir(4)
    assert rd.list_rounds() == [0, 1, 4]


def test_write_json_pydantic_model(tmp_path: Path):
    rd = RunDir(tmp_path / "r3")
    from caliper.schemas import Decision

    d = Decision(accept=True, reason="ok", evidence={"n": 5})
    rd.write_json(rd.verdict_path(0), d)
    data = json.loads(rd.verdict_path(0).read_text(encoding="utf-8"))
    assert data["accept"] is True
    assert data["evidence"]["n"] == 5
