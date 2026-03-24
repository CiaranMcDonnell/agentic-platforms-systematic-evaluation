"""Stage 2: Requirements Engineering — Platform generates requirements and UML from user stories.

Processes natural language requirements and produces structured outputs including:

- User Stories with acceptance criteria
- Functional and Non-Functional Requirements
- Use Case specifications with actors and flows
- Domain Entity/Class designs
- System Component architecture
- API Endpoint specifications
- Mermaid diagrams (Use Case, Class, Component, ER, Sequence, etc.)

Usage:
    from desmet.stages.stage2_requirements import (
        RequirementsInput,
        RequirementsOutput,
        RequirementsStageRunner,
        create_input_from_text,
    )

    # Create input
    input_data = create_input_from_text(
        project_name="MyProject",
        description="A web application for...",
        requirements_text="The system should...",
        domain="web_application",
        technologies=["Python", "FastAPI"],
    )

    # Run the stage
    runner = RequirementsStageRunner(
        output_dir="./outputs",
        llm_client=your_llm_client,
    )
    output = await runner.run(input_data)

    # Access outputs
    print(output.user_stories)
    print(output.diagrams)
"""

from .agents import (
    BaseRequirementsAgent,
    RequirementsAgentPrompts,
    SimpleRequirementsAgent,
)
from .schemas import (
    Actor,
    APIEndpoint,
    Component,
    ConstraintInfo,
    DataModel,
    DiagramType,
    Entity,
    FunctionalRequirement,
    MermaidDiagram,
    NonFunctionalRequirement,
    ProjectDomain,
    RequirementCategory,
    RequirementPriority,
    # Input types
    RequirementsInput,
    # Output types
    RequirementsOutput,
    RequirementType,
    StakeholderInfo,
    UseCase,
    UserStory,
)
from .stage_runner import (
    RequirementsStageRunner,
    create_input_from_text,
)
from .templates.mermaid_templates import MermaidTemplates

__all__ = [
    # Input
    "RequirementsInput",
    "RequirementType",
    "ProjectDomain",
    "StakeholderInfo",
    "ConstraintInfo",
    # Output
    "RequirementsOutput",
    "RequirementPriority",
    "RequirementCategory",
    "DiagramType",
    "UserStory",
    "FunctionalRequirement",
    "NonFunctionalRequirement",
    "Actor",
    "UseCase",
    "Entity",
    "Component",
    "MermaidDiagram",
    "APIEndpoint",
    "DataModel",
    # Agents
    "BaseRequirementsAgent",
    "SimpleRequirementsAgent",
    "RequirementsAgentPrompts",
    # Runner
    "RequirementsStageRunner",
    "create_input_from_text",
    # Templates
    "MermaidTemplates",
]
