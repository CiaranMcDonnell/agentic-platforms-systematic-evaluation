"""
Output Schema for Requirements Stage

Defines the structured output produced by the Requirements stage.
This output is consumed by subsequent pipeline stages (Code Generation, Testing, etc.)
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from datetime import datetime


class RequirementPriority(Enum):
    """Priority levels for requirements."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RequirementCategory(Enum):
    """Categories for requirements."""
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    CONSTRAINT = "constraint"
    INTERFACE = "interface"
    DATA = "data"


class DiagramType(Enum):
    """Types of PlantUML diagrams."""
    USE_CASE = "use_case"
    CLASS = "class"
    SEQUENCE = "sequence"
    COMPONENT = "component"
    ACTIVITY = "activity"
    STATE = "state"
    ENTITY_RELATIONSHIP = "entity_relationship"


@dataclass
class UserStory:
    """
    User story in standard format.

    Format: As a [role], I want [feature], so that [benefit].
    """
    id: str
    role: str
    feature: str
    benefit: str
    acceptance_criteria: list[str] = field(default_factory=list)
    priority: RequirementPriority = RequirementPriority.MEDIUM
    story_points: Optional[int] = None
    dependencies: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        """Convert to standard user story text format."""
        text = f"[{self.id}] As a {self.role}, I want {self.feature}, so that {self.benefit}."
        if self.acceptance_criteria:
            text += "\n  Acceptance Criteria:"
            for ac in self.acceptance_criteria:
                text += f"\n    - {ac}"
        return text


@dataclass
class FunctionalRequirement:
    """A functional requirement specification."""
    id: str
    title: str
    description: str
    category: RequirementCategory = RequirementCategory.FUNCTIONAL
    priority: RequirementPriority = RequirementPriority.MEDIUM
    rationale: Optional[str] = None
    source: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)
    related_user_stories: list[str] = field(default_factory=list)
    verification_method: Optional[str] = None


@dataclass
class NonFunctionalRequirement:
    """A non-functional requirement (quality attribute)."""
    id: str
    title: str
    description: str
    category: str  # e.g., "Performance", "Security", "Scalability"
    metric: Optional[str] = None  # e.g., "Response time < 200ms"
    priority: RequirementPriority = RequirementPriority.MEDIUM
    rationale: Optional[str] = None


@dataclass
class Actor:
    """An actor in the system (for use case diagrams)."""
    name: str
    description: str
    type: str = "primary"  # primary, secondary, external_system


@dataclass
class UseCase:
    """A use case specification."""
    id: str
    name: str
    description: str
    actors: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    main_flow: list[str] = field(default_factory=list)
    alternative_flows: list[list[str]] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)
    extends: list[str] = field(default_factory=list)


@dataclass
class Entity:
    """An entity/class in the domain model."""
    name: str
    description: str
    attributes: list[dict] = field(default_factory=list)  # [{name, type, required, description}]
    methods: list[dict] = field(default_factory=list)  # [{name, parameters, return_type, description}]
    relationships: list[dict] = field(default_factory=list)  # [{target, type, cardinality}]


@dataclass
class Component:
    """A system component for architecture diagrams."""
    name: str
    description: str
    type: str  # e.g., "service", "database", "api", "ui"
    interfaces: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)


@dataclass
class PlantUMLDiagram:
    """A PlantUML diagram specification."""
    diagram_type: DiagramType
    name: str
    description: str
    plantuml_code: str
    related_requirements: list[str] = field(default_factory=list)


@dataclass
class APIEndpoint:
    """An API endpoint specification."""
    path: str
    method: str  # GET, POST, PUT, DELETE, PATCH
    description: str
    request_body: Optional[dict] = None
    response_schema: Optional[dict] = None
    parameters: list[dict] = field(default_factory=list)
    authentication_required: bool = True
    related_use_cases: list[str] = field(default_factory=list)


@dataclass
class DataModel:
    """Data model specification for the system."""
    entities: list[Entity] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)


@dataclass
class RequirementsOutput:
    """
    Complete output of the Requirements Stage.

    This is consumed by subsequent pipeline stages:
    - Code Generation Stage: Uses entities, components, API specs
    - Testing Stage: Uses acceptance criteria, verification methods
    - Deployment Stage: Uses components, non-functional requirements
    """
    # Metadata
    project_name: str
    version: str = "1.0.0"
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # User Stories
    user_stories: list[UserStory] = field(default_factory=list)

    # Requirements
    functional_requirements: list[FunctionalRequirement] = field(default_factory=list)
    non_functional_requirements: list[NonFunctionalRequirement] = field(default_factory=list)

    # Use Case Model
    actors: list[Actor] = field(default_factory=list)
    use_cases: list[UseCase] = field(default_factory=list)

    # Domain Model
    entities: list[Entity] = field(default_factory=list)
    data_model: Optional[DataModel] = None

    # Architecture
    components: list[Component] = field(default_factory=list)
    api_endpoints: list[APIEndpoint] = field(default_factory=list)

    # PlantUML Diagrams
    diagrams: list[PlantUMLDiagram] = field(default_factory=list)

    # Traceability
    traceability_matrix: dict[str, list[str]] = field(default_factory=dict)

    # Summary
    summary: Optional[str] = None
    risks: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    def get_diagram_by_type(self, diagram_type: DiagramType) -> list[PlantUMLDiagram]:
        """Get all diagrams of a specific type."""
        return [d for d in self.diagrams if d.diagram_type == diagram_type]

    def get_requirements_by_priority(self, priority: RequirementPriority) -> list[FunctionalRequirement]:
        """Get all functional requirements of a specific priority."""
        return [r for r in self.functional_requirements if r.priority == priority]

    def to_json(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        import json
        from dataclasses import asdict

        def enum_handler(obj):
            if isinstance(obj, Enum):
                return obj.value
            return obj

        result = asdict(self)
        # Convert enums to their values
        return json.loads(json.dumps(result, default=enum_handler))

    def export_diagrams(self, output_dir: str) -> list[str]:
        """Export all PlantUML diagrams to files."""
        import os
        exported = []
        for diagram in self.diagrams:
            filename = f"{diagram.diagram_type.value}_{diagram.name.lower().replace(' ', '_')}.puml"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'w') as f:
                f.write(diagram.plantuml_code)
            exported.append(filepath)
        return exported
