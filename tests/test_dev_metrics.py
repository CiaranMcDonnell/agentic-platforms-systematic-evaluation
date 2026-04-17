from desmet.harness.dev_metrics import (
    DevMetrics, compute_dev_metrics, compute_all_dev_metrics,
    count_loc, count_sloc, get_shared_loc,
)


def test_count_loc_excludes_blanks_and_comments():
    source = '"""Docstring."""\n\n# A comment\nimport os\n\ndef foo():\n    # inline comment\n    return 1\n'
    assert count_loc(source) == 4  # docstring, import, def, return


def test_count_sloc_excludes_imports_and_docstrings():
    source = '"""Module docstring."""\n\nimport os\nfrom pathlib import Path\n\ndef foo():\n    """Function docstring."""\n    return 1\n\nclass Bar:\n    pass\n'
    assert count_sloc(source) == 4  # def foo, return 1, class Bar, pass


def test_compute_dev_metrics_langgraph():
    dm = compute_dev_metrics("langgraph")
    assert dm.platform_id == "langgraph"
    assert dm.adapter_loc > 0
    assert dm.adapter_sloc > 0
    assert dm.adapter_sloc <= dm.adapter_loc
    assert dm.dependency_count > 0
    assert any("langgraph" in d for d in dm.dependency_names)


def test_compute_all_dev_metrics():
    all_metrics = compute_all_dev_metrics()
    assert "langgraph" in all_metrics
    assert "crewai" in all_metrics


def test_get_shared_loc():
    shared = get_shared_loc()
    assert shared > 0


def test_compute_dev_metrics_maps_mismatched_platform_ids():
    from desmet.harness.dev_metrics import compute_dev_metrics

    maf = compute_dev_metrics("microsoft_agent_framework")
    assert maf.adapter_loc > 0, "MAF should resolve to agent_framework.py"
    assert maf.adapter_sloc > 0

    oai = compute_dev_metrics("openai_agents_sdk")
    assert oai.adapter_loc > 0, "OpenAI SDK should resolve to openai_agents.py"
    assert oai.adapter_sloc > 0
