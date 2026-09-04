from dataclasses import asdict

from dacite import from_dict

from checkbox_jira_bugger.jira_project_structure import (
    JiraIssueEssential,
    PlatformClosing,
    PlatformEnablement,
    PlatformExecution,
    PlatformPlanning,
)


def test_jira_issue_essential_defaults():
    issue = JiraIssueEssential()
    assert issue.summary is None
    assert issue.key == ""


def test_platform_enablement_is_jira_issue_essential():
    enablement = PlatformEnablement(summary="Enable Foo", key="FOO")
    assert isinstance(enablement, JiraIssueEssential)
    assert isinstance(enablement.platform_planning, PlatformPlanning)
    assert isinstance(enablement.platform_execution, PlatformExecution)
    assert isinstance(enablement.platform_closing, PlatformClosing)
    assert enablement.summary == "Enable Foo"
    assert enablement.key == "FOO"


def test_platform_enablement_roundtrip_via_dacite():
    original = PlatformEnablement(
        summary="Enable Dell Blue Ridge 10 Platform",
        key="BR10",
        platform_planning=PlatformPlanning(
            summary="Dell Blue Ridge 10 Platform Planning",
            key="BR10-PLANNING",
            engineering_plan=JiraIssueEssential(
                summary="Dell Blue Ridge 10 Platform Engineering Plan",
                key="BR10-ENG-PLAN",
            ),
        ),
    )

    demarshalled = from_dict(data_class=PlatformEnablement, data=asdict(original))

    assert demarshalled == original
    assert (
        demarshalled.platform_planning.engineering_plan.key == "BR10-ENG-PLAN"
    )


def test_default_nested_fields_are_isolated_between_instances():
    instance1 = PlatformEnablement()
    instance2 = PlatformEnablement()

    instance1.platform_planning.summary = "mutated"
    instance1.platform_planning.engineering_plan.summary = "mutated engineering plan"
    instance1.platform_execution.dvt1_samples_handling.key = "mutated-key"
    instance1.platform_closing.platform_mir.summary = "mutated mir"

    assert instance2.platform_planning.summary == "Platform Planning"
    assert instance2.platform_planning.engineering_plan.summary == "Engineering Plan"
    assert instance2.platform_execution.dvt1_samples_handling.key == ""
    assert instance2.platform_closing.platform_mir.summary == "Platform MIR"
