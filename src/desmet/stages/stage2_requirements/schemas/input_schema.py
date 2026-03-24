"""
Input Schema for Requirements Stage

Defines the structure of input that the Requirements stage accepts.
This can be natural language requirements, user stories, or structured requirement documents.
"""

from dataclasses import dataclass, field
from enum import Enum


class RequirementType(Enum):
    """Types of requirements that can be processed."""
    NATURAL_LANGUAGE = "natural_language"
    USER_STORY = "user_story"
    FEATURE_REQUEST = "feature_request"
    STRUCTURED = "structured"


class ProjectDomain(Enum):
    """Domain categories for the project."""
    WEB_APPLICATION = "web_application"
    MOBILE_APP = "mobile_app"
    API_SERVICE = "api_service"
    CLI_TOOL = "cli_tool"
    DATA_PIPELINE = "data_pipeline"
    DESKTOP_APP = "desktop_app"
    EMBEDDED_SYSTEM = "embedded_system"
    OTHER = "other"


@dataclass
class StakeholderInfo:
    """Information about project stakeholders."""
    name: str
    role: str
    concerns: list[str] = field(default_factory=list)
    priority: int = 1  # 1 = highest priority


@dataclass
class ConstraintInfo:
    """Project constraints and limitations."""
    technical: list[str] = field(default_factory=list)
    business: list[str] = field(default_factory=list)
    regulatory: list[str] = field(default_factory=list)
    timeline: str | None = None
    budget: str | None = None


@dataclass
class RequirementsInput:
    """
    Main input schema for the Requirements Stage.

    Attributes:
        project_name: Name of the project
        project_description: High-level description of the project
        raw_requirements: Natural language or structured requirements text
        requirement_type: Type of input requirements
        domain: Project domain category
        stakeholders: List of stakeholder information
        constraints: Project constraints
        existing_context: Any existing documentation or context
        target_technologies: Preferred or required technologies
        quality_attributes: Non-functional requirements priorities
    """
    project_name: str
    project_description: str
    raw_requirements: str
    requirement_type: RequirementType = RequirementType.NATURAL_LANGUAGE
    domain: ProjectDomain = ProjectDomain.OTHER
    stakeholders: list[StakeholderInfo] = field(default_factory=list)
    constraints: ConstraintInfo = field(default_factory=ConstraintInfo)
    existing_context: str | None = None
    target_technologies: list[str] = field(default_factory=list)
    quality_attributes: dict[str, int] = field(default_factory=dict)

    def to_prompt_context(self) -> str:
        """Convert input to a context string for LLM prompts."""
        context_parts = [
            f"# Project: {self.project_name}",
            f"\n## Description\n{self.project_description}",
            f"\n## Requirements\n{self.raw_requirements}",
            f"\n## Domain: {self.domain.value}",
        ]

        if self.stakeholders:
            stakeholder_text = "\n".join([
                f"- {s.name} ({s.role}): {', '.join(s.concerns)}"
                for s in self.stakeholders
            ])
            context_parts.append(f"\n## Stakeholders\n{stakeholder_text}")

        if self.constraints.technical or self.constraints.business:
            constraints_text = []
            if self.constraints.technical:
                constraints_text.append(f"Technical: {', '.join(self.constraints.technical)}")
            if self.constraints.business:
                constraints_text.append(f"Business: {', '.join(self.constraints.business)}")
            if self.constraints.regulatory:
                constraints_text.append(f"Regulatory: {', '.join(self.constraints.regulatory)}")
            context_parts.append("\n## Constraints\n" + "\n".join(constraints_text))

        if self.target_technologies:
            context_parts.append(f"\n## Target Technologies\n{', '.join(self.target_technologies)}")

        if self.quality_attributes:
            qa_text = "\n".join([f"- {k}: Priority {v}" for k, v in self.quality_attributes.items()])
            context_parts.append(f"\n## Quality Attributes\n{qa_text}")

        if self.existing_context:
            context_parts.append(f"\n## Additional Context\n{self.existing_context}")

        return "\n".join(context_parts)
