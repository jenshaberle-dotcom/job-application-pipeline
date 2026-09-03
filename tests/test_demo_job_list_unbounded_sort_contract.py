from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "scripts" / "product_v1_control_center_base.py"
UI = ROOT / "frontend" / "control-center" / "src" / "OperatorWorkspace.tsx"
HELPER = ROOT / "scripts" / "prepare_product_v1_demo_operator_test.py"
LAUNCHER = ROOT / "scripts" / "run_product_v1_live_demo.py"


def test_product_v1_read_models_have_no_arbitrary_200_row_window() -> None:
    source = BASE.read_text(encoding="utf-8")

    job_query = source.split(
        "FROM gold_product_v1_job_readiness", 1
    )[1].split("ranking_policy =", 1)[0]

    application_query = source.split(
        "FROM gold_product_v1_application_readiness", 1
    )[1].split("application_sources =", 1)[0]

    assert "LIMIT 200" not in job_query
    assert "LIMIT 200" not in application_query


def test_jobs_default_to_all_newest_first_and_are_sortable() -> None:
    source = UI.read_text(encoding="utf-8")

    assert 'useState<JobFilter>("all")' in source
    assert 'useState<JobSort>("newest")' in source
    assert 'value="newest">Newest first' in source
    assert 'value="oldest">Oldest first' in source
    assert 'value="fit_desc">Affinity high → low' in source
    assert 'value="fit_asc">Affinity low → high' in source
    assert "compareJobs(a, b, sort)" in source
    assert 'sortHeader("published", "Published")' in source
    assert "displayDate(job.publication_date)" in source


def test_operator_entrypoints_are_direct_invocation_safe() -> None:
    helper = HELPER.read_text(encoding="utf-8")
    launcher = LAUNCHER.read_text(encoding="utf-8")

    guard = "if not __package__ and str(ROOT) not in sys.path"
    assert guard in helper
    assert guard in launcher

    assert '"-m",' in helper
    assert '"scripts.run_product_v1_live_demo",' in helper
