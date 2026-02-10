# Requirements Stage

The first stage of the DESMET Agentic Platforms pipeline that processes natural language requirements and produces structured outputs for downstream stages.

## Overview

The Requirements Stage takes raw requirements (natural language, user stories, feature requests) and produces:

1. **Structured User Stories** - With acceptance criteria, priorities, and dependencies
2. **Functional Requirements** - What the system must do
3. **Non-Functional Requirements** - Quality attributes (performance, security, etc.)
4. **Use Case Specifications** - Actors, flows, preconditions, postconditions
5. **Domain Entity Designs** - Classes, attributes, methods, relationships
6. **System Component Architecture** - High-level component design
7. **API Endpoint Specifications** - REST API design
8. **PlantUML Diagrams** - Visual representations of the design

## Directory Structure

```
requirements/
├── __init__.py              # Main module exports
├── README.md                # This file
├── stage_runner.py          # Stage orchestration and execution
├── schemas/
│   ├── __init__.py
│   ├── input_schema.py      # Input data structures
│   └── output_schema.py     # Output data structures
├── agents/
│   ├── __init__.py
│   └── requirements_agent.py # Core agent logic
├── templates/
│   └── plantuml_templates.py # PlantUML diagram generators
├── examples/
│   ├── example_usage.py      # Usage examples
│   └── sample_requirements.txt
└── outputs/                  # Generated outputs (created at runtime)
```

## Usage

### Basic Usage

```python
import asyncio
from stages.requirements import (
    RequirementsStageRunner,
    create_input_from_text,
)
from openai import AsyncOpenAI

async def main():
    # Create LLM client
    client = AsyncOpenAI(api_key="your-key")

    # Create input
    input_data = create_input_from_text(
        project_name="TaskFlow",
        description="A task management application",
        requirements_text="""
        Users should be able to create and manage tasks.
        Tasks should have titles, descriptions, and due dates.
        Users can assign tasks to team members.
        """,
        domain="web_application",
        technologies=["Python", "FastAPI", "React"],
    )

    # Run the stage
    runner = RequirementsStageRunner(
        output_dir="./outputs",
        llm_client=client,
        model="gpt-4",
    )

    output = await runner.run(input_data)

    # Access outputs
    print(f"Generated {len(output.user_stories)} user stories")
    print(f"Generated {len(output.diagrams)} PlantUML diagrams")

asyncio.run(main())
```

### Advanced Usage with Stakeholders

```python
from stages.requirements import (
    RequirementsInput,
    RequirementType,
    ProjectDomain,
    StakeholderInfo,
    ConstraintInfo,
)

input_data = RequirementsInput(
    project_name="E-Commerce Platform",
    project_description="An online marketplace",
    raw_requirements="...",
    requirement_type=RequirementType.NATURAL_LANGUAGE,
    domain=ProjectDomain.WEB_APPLICATION,
    stakeholders=[
        StakeholderInfo(
            name="Customer",
            role="End User",
            concerns=["Easy checkout", "Fast delivery"],
            priority=1,
        ),
        StakeholderInfo(
            name="Merchant",
            role="Seller",
            concerns=["Sales analytics", "Inventory management"],
            priority=1,
        ),
    ],
    constraints=ConstraintInfo(
        technical=["Must use PostgreSQL"],
        business=["Launch in Q2"],
        regulatory=["GDPR compliant"],
    ),
    target_technologies=["Python", "Django", "React"],
    quality_attributes={
        "Performance": 1,
        "Security": 1,
        "Scalability": 2,
    },
)
```

## Output Files

When the stage runs, it produces the following outputs:

| File | Description | Consumed By |
|------|-------------|-------------|
| `requirements_output.json` | Complete JSON output with all artifacts | All stages |
| `user_stories.md` | Markdown formatted user stories | Testing stage |
| `requirements_specification.md` | Full requirements document | Documentation |
| `for_code_generation.json` | Entities, APIs, components | Code Generation stage |
| `for_testing.json` | Acceptance criteria, test cases | Testing stage |
| `diagrams/*.puml` | PlantUML diagram files | Documentation |

## PlantUML Diagrams

The stage generates the following diagram types:

1. **Use Case Diagram** - Shows actors and their interactions with the system
2. **Class Diagram** - Domain model with entities and relationships
3. **Component Diagram** - High-level system architecture
4. **Entity-Relationship Diagram** - Database schema design
5. **Sequence Diagram** - Interaction flows (when detailed flows provided)
6. **Activity Diagram** - Workflow processes
7. **State Diagram** - State machines for complex entities

### Rendering Diagrams

PlantUML diagrams can be rendered using:

```bash
# Using PlantUML CLI
java -jar plantuml.jar diagram.puml

# Using online renderer
# Paste content at https://www.plantuml.com/plantuml/

# Using VS Code extension
# Install "PlantUML" extension
```

## Extending for DESMET Evaluation

The `BaseRequirementsAgent` abstract class defines the interface for implementing the Requirements Stage on different agentic platforms:

```python
from stages.requirements.agents import BaseRequirementsAgent

class LangGraphRequirementsAgent(BaseRequirementsAgent):
    """LangGraph implementation for DESMET evaluation."""

    async def analyze_requirements(self, input_data):
        # Implement using LangGraph
        pass

    async def extract_user_stories(self, context):
        # Implement using LangGraph
        pass

    # ... implement other abstract methods
```

This enables systematic comparison of how different platforms (LangGraph, CrewAI, AutoGen, etc.) handle requirements engineering tasks.

## Integration with Pipeline

The Requirements Stage outputs feed into subsequent stages:

```
┌─────────────────┐
│  Requirements   │
│     Stage       │
└────────┬────────┘
         │
         ├──► for_code_generation.json ──► Code Generation Stage
         │
         ├──► for_testing.json ──────────► Testing Stage
         │
         └──► diagrams/*.puml ───────────► Documentation
```

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `ANTHROPIC_API_KEY` | Anthropic API key | Optional |
| `LLM_MODEL` | Model to use | `gpt-4` |
| `OUTPUT_DIR` | Output directory | `./outputs` |
