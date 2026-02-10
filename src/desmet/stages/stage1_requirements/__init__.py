"""
Requirements Stage

The first stage of the software engineering pipeline that processes
natural language requirements and produces structured outputs including:

- User Stories with acceptance criteria
- Functional and Non-Functional Requirements
- Use Case specifications with actors and flows
- Domain Entity/Class designs
- System Component architecture
- API Endpoint specifications
- PlantUML diagrams (Use Case, Class, Component, ER, Sequence, etc.)

Usage:
    from stages.requirements import (
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

from .schemas import (
    # Input types
    RequirementsInput,
    RequirementType,
    ProjectDomain,
    StakeholderInfo,
    ConstraintInfo,
    # Output types
    RequirementsOutput,
    RequirementPriority,
    RequirementCategory,
    DiagramType,
    UserStory,
    FunctionalRequirement,
    NonFunctionalRequirement,
    Actor,
    UseCase,
    Entity,
    Component,
    PlantUMLDiagram,
    APIEndpoint,
    DataModel,
)

from .agents import (
    BaseRequirementsAgent,
    SimpleRequirementsAgent,
    RequirementsAgentPrompts,
)

from .stage_runner import (
    RequirementsStageRunner,
    create_input_from_text,
)

from .templates.plantuml_templates import PlantUMLTemplates

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
    "PlantUMLDiagram",
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
    "PlantUMLTemplates",
]
