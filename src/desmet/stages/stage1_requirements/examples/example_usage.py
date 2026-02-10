"""
Example Usage of the Requirements Stage

This file demonstrates how to use the Requirements Stage with different
LLM providers (OpenAI, Anthropic) and shows the complete workflow.
"""

import asyncio
import os
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from stages.requirements.schemas import (
    RequirementsInput,
    RequirementType,
    ProjectDomain,
    StakeholderInfo,
    ConstraintInfo,
)
from stages.requirements.stage_runner import RequirementsStageRunner, create_input_from_text


# Example 1: Simple usage with text input
EXAMPLE_REQUIREMENTS = """
# Task Management Application Requirements

## Overview
We need a web-based task management application that allows teams to organize
and track their work efficiently. The application should support multiple users,
project organization, and real-time updates.

## Core Features

### User Management
- Users should be able to register with email and password
- Users should be able to login and logout securely
- Users should be able to update their profile information
- Administrators should be able to manage user accounts

### Task Management
- Users should be able to create, edit, and delete tasks
- Tasks should have a title, description, due date, and priority level
- Tasks can be assigned to one or more team members
- Tasks should support status tracking (To Do, In Progress, Done)
- Users should be able to add comments to tasks
- Users should be able to attach files to tasks

### Project Organization
- Tasks should be organized into projects
- Projects should have a name, description, and team members
- Users should be able to view all tasks in a project
- Projects should support different visibility levels (private, team, public)

### Collaboration
- Team members should see real-time updates when tasks change
- Users should receive notifications for task assignments and updates
- Users should be able to mention other users in comments

### Reporting
- Users should be able to view task statistics and progress
- Projects should have a dashboard showing overall progress
- Users should be able to export task data

## Non-Functional Requirements
- The application should load within 2 seconds
- The application should support 1000 concurrent users
- All data should be encrypted in transit and at rest
- The application should be accessible on mobile devices
- The application should be available 99.9% of the time
"""


async def example_simple_usage():
    """Simple example using text input."""
    print("=" * 60)
    print("Example 1: Simple Usage with Text Input")
    print("=" * 60)

    # Create input from simple text
    input_data = create_input_from_text(
        project_name="TaskFlow",
        description="A modern task management application for teams",
        requirements_text=EXAMPLE_REQUIREMENTS,
        domain="web_application",
        technologies=["Python", "FastAPI", "React", "PostgreSQL"],
    )

    print(f"Project: {input_data.project_name}")
    print(f"Domain: {input_data.domain.value}")
    print(f"Technologies: {', '.join(input_data.target_technologies)}")
    print()

    # Note: This would require an actual LLM client
    print("To run this example, configure an LLM client as shown in example_with_openai()")
    print()


async def example_detailed_input():
    """Example with detailed structured input."""
    print("=" * 60)
    print("Example 2: Detailed Structured Input")
    print("=" * 60)

    # Create detailed input with stakeholders and constraints
    input_data = RequirementsInput(
        project_name="E-Commerce Platform",
        project_description="""
        A full-featured e-commerce platform for small to medium businesses.
        The platform should allow businesses to set up online stores,
        manage inventory, process payments, and handle shipping.
        """,
        raw_requirements="""
        ## Customer Features
        - Browse products by category
        - Search for products with filters (price, brand, ratings)
        - Add products to shopping cart
        - Checkout with multiple payment options
        - Track orders
        - Write product reviews
        - Create wishlists

        ## Merchant Features
        - Create and manage product listings
        - Set prices and discounts
        - Manage inventory
        - View sales analytics
        - Process orders and returns
        - Configure shipping options

        ## Admin Features
        - Manage merchants and customers
        - Configure payment gateways
        - View platform analytics
        - Handle disputes
        """,
        requirement_type=RequirementType.NATURAL_LANGUAGE,
        domain=ProjectDomain.WEB_APPLICATION,
        stakeholders=[
            StakeholderInfo(
                name="End Customer",
                role="Consumer",
                concerns=["Easy to use", "Secure payments", "Fast shipping"],
                priority=1,
            ),
            StakeholderInfo(
                name="Merchant",
                role="Business Owner",
                concerns=["Sales analytics", "Inventory management", "Low fees"],
                priority=1,
            ),
            StakeholderInfo(
                name="Platform Admin",
                role="Operations",
                concerns=["Dispute resolution", "Platform stability", "Fraud prevention"],
                priority=2,
            ),
        ],
        constraints=ConstraintInfo(
            technical=["Must integrate with Stripe and PayPal", "Mobile-responsive design"],
            business=["Launch within 6 months", "Support multi-currency"],
            regulatory=["GDPR compliance", "PCI-DSS for payment handling"],
        ),
        target_technologies=["Python", "Django", "React", "PostgreSQL", "Redis", "Elasticsearch"],
        quality_attributes={
            "Performance": 1,
            "Security": 1,
            "Scalability": 2,
            "Usability": 1,
            "Reliability": 1,
        },
    )

    # Print the generated prompt context
    print("Generated Prompt Context:")
    print("-" * 40)
    print(input_data.to_prompt_context())
    print()


async def example_with_openai():
    """Example with OpenAI client (requires API key)."""
    print("=" * 60)
    print("Example 3: With OpenAI Client")
    print("=" * 60)

    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not set. Skipping OpenAI example.")
        print("Set your API key: export OPENAI_API_KEY='your-key'")
        return

    try:
        from openai import AsyncOpenAI

        # Create OpenAI client
        client = AsyncOpenAI(api_key=api_key)

        # Create input
        input_data = create_input_from_text(
            project_name="TaskFlow",
            description="A modern task management application for teams",
            requirements_text=EXAMPLE_REQUIREMENTS,
            domain="web_application",
            technologies=["Python", "FastAPI", "React", "PostgreSQL"],
        )

        # Create runner with OpenAI client
        output_dir = Path(__file__).parent.parent / "outputs"
        runner = RequirementsStageRunner(
            output_dir=str(output_dir),
            llm_client=client,
            model="gpt-4",
        )

        # Run the requirements stage
        output = await runner.run(input_data)

        # Print summary
        print("\nGenerated Artifacts:")
        print(f"- User Stories: {len(output.user_stories)}")
        print(f"- Functional Requirements: {len(output.functional_requirements)}")
        print(f"- Non-Functional Requirements: {len(output.non_functional_requirements)}")
        print(f"- Use Cases: {len(output.use_cases)}")
        print(f"- Entities: {len(output.entities)}")
        print(f"- Components: {len(output.components)}")
        print(f"- API Endpoints: {len(output.api_endpoints)}")
        print(f"- PlantUML Diagrams: {len(output.diagrams)}")

    except ImportError:
        print("OpenAI package not installed. Run: pip install openai")
    except Exception as e:
        print(f"Error: {e}")


async def example_with_anthropic():
    """Example with Anthropic client (requires API key)."""
    print("=" * 60)
    print("Example 4: With Anthropic Client")
    print("=" * 60)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set. Skipping Anthropic example.")
        print("Set your API key: export ANTHROPIC_API_KEY='your-key'")
        return

    # Note: Would need to create an Anthropic-compatible wrapper
    print("Anthropic integration requires a custom adapter.")
    print("See the agents/requirements_agent.py for the interface to implement.")


async def main():
    """Run all examples."""
    await example_simple_usage()
    print()

    await example_detailed_input()
    print()

    await example_with_openai()
    print()

    await example_with_anthropic()


if __name__ == "__main__":
    asyncio.run(main())
