"""Jira project hierarchy dataclasses (Theme/Objective/Epic).

Ported from BugHamster/JiraProjectStructure.py. Mutable dataclass instance
defaults were converted to ``field(default_factory=...)`` because Python
3.11+ rejects mutable defaults on dataclass fields (the original module's
defaults raised ``ValueError`` on import under this project's Python
version). Behavior is otherwise unchanged.
"""

from dataclasses import dataclass, field
from typing import Optional


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
