"""Jira project hierarchy dataclasses (Theme/Objective/Epic).

Ported from BugHamster/JiraProjectStructure.py. Mutable dataclass instance
defaults were converted to ``field(default_factory=...)`` because Python
3.11+ rejects mutable defaults on dataclass fields (the original module's
defaults raised ``ValueError`` on import under this project's Python
version). Behavior is otherwise unchanged.
"""

from dataclasses import dataclass, asdict, field
from typing import Optional
from dacite import from_dict
import json


@dataclass
class JiraIssueEssential:
    summary: Optional[str] = None
    key: str = ""


@dataclass
class PlatformClosing(JiraIssueEssential):
    """
    Platform closing structure.
    Take Dell Blue Ridge 10 Platform as an example.
    Theme: Enable Dell Blue Ridge 10 Platform
    └── Objective: Dell Blue Ridge 10 Platform Closing
        ├── Epic: Dell Blue Ridge 10 Platform Certification
        └── Epic: Dell Blue Ridge 10 Platform MIR
    """
    platform_certification: JiraIssueEssential = field(
        default_factory=lambda: JiraIssueEssential(summary="Platform Certification"))
    platform_mir: JiraIssueEssential = field(default_factory=lambda: JiraIssueEssential(summary="Platform MIR"))
    summary: str = "Platform Closing"


@dataclass
class PlatformExecution(JiraIssueEssential):
    """
    Platform execution structure.
    Take Dell Blue Ridge 10 Platform as an example.
    Theme: Enable Dell Blue Ridge 10 Platform
    └── Objective: Dell Blue Ridge 10 Platform Execution
        ├── Epic: Dell Blue Ridge 10 Platform DVT1 Samples Handling
        ├── Epic: Dell Blue Ridge 10 Platform FC Image Release & Validation
        ├── Epic: Dell Blue Ridge 10 Platform Needs to be Fixed Bugs for FC Image Release
        ├── Epic: Dell Blue Ridge 10 Platform DVT2 Samples Handling
        ├── Epic: Dell Blue Ridge 10 Platform GM Image Release & Validation
        └── Epic: Dell Blue Ridge 10 Platform Needs to be Fixed Bugs for GM Image Release
    """
    dvt1_samples_handling: JiraIssueEssential = field(
        default_factory=lambda: JiraIssueEssential(summary="DVT1 Samples Handling"))
    fc_image_release_validation: JiraIssueEssential = field(
        default_factory=lambda: JiraIssueEssential(summary="FC Image Release & Validation"))
    needs_fixed_bugs_fc_image: JiraIssueEssential = field(
        default_factory=lambda: JiraIssueEssential(
            summary="Needs to be Fixed Bugs for FC Image Release"))
    dvt2_samples_handling: JiraIssueEssential = field(
        default_factory=lambda: JiraIssueEssential(summary="DVT2 Samples Handling"))
    gm_image_release_validation: JiraIssueEssential = field(
        default_factory=lambda: JiraIssueEssential(summary="GM Image Release & Validation"))
    needs_fixed_bugs_gm_image: JiraIssueEssential = field(
        default_factory=lambda: JiraIssueEssential(
            summary="Needs to be Fixed Bugs for GM Image Release"))
    summary: str = "Platform Execution"


@dataclass
class PlatformPlanning(JiraIssueEssential):
    """
    Platform planning structure.
    Take Dell Blue Ridge 10 Platform as an example.
    Theme: Enable Dell Blue Ridge 10 Platform
    └── Objective: Dell Blue Ridge 10 Platform Planning
        └── Epic: Dell Blue Ridge 10 Platform Engineering Plan
    """
    engineering_plan: JiraIssueEssential = field(
        default_factory=lambda: JiraIssueEssential(summary="Engineering Plan"))
    summary: str = "Platform Planning"


@dataclass
class PlatformEnablement(JiraIssueEssential):
    """
    Platform enablement structure.
    Take Dell Blue Ridge 10 Platform as an example.
    Theme: Enable Dell Blue Ridge 10 Platform
    ├── Objective: Dell Blue Ridge 10 Platform Planning
    │   └── Epic: Dell Blue Ridge 10 Platform Engineering Plan
    ├── Objective: Dell Blue Ridge 10 Platform Execution
    │   ├── Epic: Dell Blue Ridge 10 Platform DVT1 Samples Handling
    │   ├── Epic: Dell Blue Ridge 10 Platform FC Image Release & Validation
    │   ├── Epic: Dell Blue Ridge 10 Platform Needs to be Fixed Bugs for FC Image Release
    │   ├── Epic: Dell Blue Ridge 10 Platform DVT2 Samples Handling
    │   ├── Epic: Dell Blue Ridge 10 Platform GM Image Release & Validation
    │   └── Epic: Dell Blue Ridge 10 Platform Needs to be Fixed Bugs for GM Image Release
    └── Objective: Dell Blue Ridge 10 Platform Closing
        ├── Epic: Dell Blue Ridge 10 Platform Certification
        └── Epic: Dell Blue Ridge 10 Platform MIR
    """
    platform_planning: PlatformPlanning = field(default_factory=PlatformPlanning)
    platform_execution: PlatformExecution = field(default_factory=PlatformExecution)
    platform_closing: PlatformClosing = field(default_factory=PlatformClosing)


if __name__ == "__main__":
    dell_br10 = PlatformEnablement(
        summary="Enable Dell Blue Ridge 10 Platform", key="BR10",
        platform_planning=PlatformPlanning(
            summary="Dell Blue Ridge 10 Platform Planning", key="BR10-PLANNING",
            engineering_plan=JiraIssueEssential(
                summary="Dell Blue Ridge 10 Platform Engineering Plan", key="BR10-ENG-PLAN")),
        platform_execution=PlatformExecution(
            summary="Dell Blue Ridge 10 Platform Execution", key="BR10-EXECUTION",
            dvt1_samples_handling=JiraIssueEssential(
                summary="Dell Blue Ridge 10 Platform DVT1 Samples Handling", key="BR10-DVT1"),
            fc_image_release_validation=JiraIssueEssential(
                summary="Dell Blue Ridge 10 Platform FC Image Release & Validation", key="BR10-FC-IMAGE"),
            needs_fixed_bugs_fc_image=JiraIssueEssential(
                summary="Dell Blue Ridge 10 Platform Needs to be Fixed Bugs for FC Image Release", key="BR10-FC-BUGS"),
            dvt2_samples_handling=JiraIssueEssential(
                summary="Dell Blue Ridge 10 Platform DVT2 Samples Handling", key="BR10-DVT2"),
            gm_image_release_validation=JiraIssueEssential(
                summary="Dell Blue Ridge 10 Platform GM Image Release & Validation", key="BR10-GM-IMAGE"),
            needs_fixed_bugs_gm_image=JiraIssueEssential(
                summary="Dell Blue Ridge 10 Platform Needs to be Fixed Bugs for GM Image Release", key="BR10-GM-BUGS")),
        platform_closing=PlatformClosing(
            summary="Dell Blue Ridge 10 Platform Closing", key="BR10-CLOSING",
            platform_certification=JiraIssueEssential(
                summary="Dell Blue Ridge 10 Platform Certification", key="BR10-CERTIFICATION"),
            platform_mir=JiraIssueEssential(summary="Dell Blue Ridge 10 Platform MIR", key="BR10-MIR")))
    print(asdict(dell_br10))
    demarshall = from_dict(data_class=PlatformEnablement, data=asdict(dell_br10))
    print(asdict(demarshall))
    assert demarshall == dell_br10, "Demarshalling failed, the data does not match the original object."
    foo = PlatformEnablement(key="SOMERVILLE-2636")
    print(json.dumps(asdict(foo), indent=2))  # This will print an empty PlatformEnablement object

    def dfs(obj, parent=None, me=""):
        if hasattr(obj, "__dataclass_fields__"):
            for field in obj.__dataclass_fields__:
                if field == "key" or field == "summary":
                    continue
                value = getattr(obj, field)
                dfs(value, parent=obj, me=field)
            if me != 'root':  # Skip the root object
                print(f"parent: {parent.summary if parent else 'None'}")
                print(f"me: {me}")
                print(f'JQL: parent = "{parent.key}" AND summary ~ "{obj.summary}"')

    def bfs(obj, parent=None, identifier=''):
        from collections import deque
        queue = deque([(obj, parent, identifier)])

        while queue:
            current_obj, current_parent, current_id = queue.popleft()

            if hasattr(current_obj, "__dataclass_fields__"):
                # Add children to queue for next level processing
                for field in current_obj.__dataclass_fields__:
                    if field == "key" or field == "summary":
                        continue
                    value = getattr(current_obj, field)
                    queue.append((value, current_obj, field))

                # Print current node info (skip root)
                if current_id != '':
                    print(f"parent: {current_parent.summary if current_parent else 'None'}")
                    print(f"me: {current_id}")
                    print(f'JQL: parent = "{current_parent.key}" AND summary ~ "{current_obj.summary}"')

    print("DFS traversal:")
    dfs(foo, parent=None, me='root')

    print("\nBFS traversal:")
    bfs(foo)
