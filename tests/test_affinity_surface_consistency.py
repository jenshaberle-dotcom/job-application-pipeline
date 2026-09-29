from pathlib import Path


FRONTEND = Path("frontend/control-center/src")


def test_affinity_never_falls_back_to_candidate_fit_score() -> None:
    review = (FRONTEND / "JobReviewLabelControls.tsx").read_text(encoding="utf-8")
    workspace = (FRONTEND / "ApplicationWorkspace.tsx").read_text(encoding="utf-8")
    adapter = (FRONTEND / "productPayloadRuntimeAdapter.ts").read_text(encoding="utf-8")

    assert 'typeof job?.product_overall_quality_score === "number"' in review
    assert ': job?.overall_quality_score;' not in review

    assert "const affinityScore = (job: TopJob)" in workspace
    assert "percent(selectedJob.overall_quality_score)" not in workspace
    assert "percent(job.overall_quality_score)" not in workspace
    assert "Number(right.overall_quality_score ?? -1)" not in workspace

    assert "function operatorPrimaryScore" not in adapter
    assert "overall_quality_score: job.overall_quality_score" in adapter
