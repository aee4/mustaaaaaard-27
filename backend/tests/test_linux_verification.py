"""Gate logic tests use recorded-shaped counters, not Linux execution evidence."""

import copy
import json

import pytest

from scripts.ci_summary import summarize
from scripts.linux_container_verify import MEMORY, validate_snapshot


def sample():
    return {
        "state": {"running": True, "oom_killed": False, "restarts": 0},
        "cgroup": {
            "memory.max": str(MEMORY),
            "memory.swap.max": "0",
            "memory.peak": "140247040",
            "cpu.max": "10000 100000",
            "memory.events": "low 0\nhigh 0\nmax 1\noom 0\noom_kill 0",
        },
    }


def test_whole_container_gate_accepts_only_bounded_cgroup_evidence():
    validate_snapshot(sample())


@pytest.mark.parametrize(
    "key,value",
    [
        ("memory.max", "max"),
        ("memory.swap.max", "536870912"),
        ("memory.peak", str(MEMORY + 1)),
        ("cpu.max", "100000 100000"),
        ("memory.events", "oom 1\noom_kill 0"),
        ("memory.events", "oom 0\noom_kill 1"),
    ],
)
def test_missing_or_wrong_resource_limits_and_oom_cannot_pass(key, value):
    evidence = copy.deepcopy(sample())
    evidence["cgroup"][key] = value
    with pytest.raises((AssertionError, ValueError)):
        validate_snapshot(evidence)


def test_dead_container_cannot_pass_without_cgroup_counters():
    evidence = sample()
    evidence["state"]["running"] = False
    evidence["cgroup"] = {}
    with pytest.raises(AssertionError):
        validate_snapshot(evidence)


def test_artifacts_discard_private_test_parameters_failure_details_and_captures(tmp_path):
    source = tmp_path / "raw.xml"
    source.write_text(
        """<testsuites><testsuite><testcase name="test_upload[PRIVATE-TOKEN]" classname="PRIVATE-CLASS">
    <failure>Cookie: PRIVATE-COOKIE https://private/media?signature=PRIVATE-SIGNATURE</failure>
    <system-out>PRIVATE-MEDIA</system-out><properties><property value="PRIVATE-SECRET"/></properties>
    </testcase></testsuite></testsuites>""",
        encoding="utf-8",
    )
    result = summarize(source)
    assert not result["passed"]
    assert result["cases"] == [{"name": "test_upload", "outcome": "failure"}]
    assert "PRIVATE" not in json.dumps(result)


def test_skipped_or_empty_integration_results_are_not_a_pass(tmp_path):
    source = tmp_path / "raw.xml"
    source.write_text('<testsuite><testcase name="test_upload"><skipped/></testcase></testsuite>')
    assert not summarize(source)["passed"]
    source.write_text("<testsuite/>")
    assert not summarize(source)["passed"]
