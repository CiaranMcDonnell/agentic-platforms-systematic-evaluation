"""
Requirements Stage Runner

Main entry point for executing the Requirements Stage.
This module orchestrates the requirements analysis pipeline and produces
output for downstream stages (Code Generation, Testing, Deployment).
"""

import json
from pathlib import Path

from desmet.llm_config import DEFAULT_MODEL

from .agents import SimpleRequirementsAgent
from .schemas import (
    ProjectDomain,
    RequirementsInput,
    RequirementsOutput,
    RequirementType,
)


class RequirementsStageRunner:
    """
    Runner for the Requirements Stage of the pipeline.

    Handles:
    - Input parsing and validation
    - Agent execution
    - Output generation and export
    """

    def __init__(
        self,
        output_dir: str = "./outputs",
        llm_client: object | None = None,
        model: str = DEFAULT_MODEL,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.agent = SimpleRequirementsAgent(llm_client=llm_client, model=model)

    async def run(self, input_data: RequirementsInput) -> RequirementsOutput:
        """
        Execute the Requirements Stage.

        Args:
            input_data: The requirements input to process

        Returns:
            RequirementsOutput containing all generated artifacts
        """
        print(f"Starting Requirements Stage for: {input_data.project_name}")
        print("-" * 50)

        # Run the requirements agent
        output = await self.agent.analyze_requirements(input_data)

        # Export outputs
        await self._export_outputs(output)

        print("-" * 50)
        print(f"Requirements Stage completed. Output saved to: {self.output_dir}")

        return output

    async def _export_outputs(self, output: RequirementsOutput):
        """Export all outputs to files."""
        project_dir = self.output_dir / output.project_name.lower().replace(" ", "_")
        project_dir.mkdir(parents=True, exist_ok=True)

        # Export Mermaid diagrams
        diagrams_dir = project_dir / "diagrams"
        diagrams_dir.mkdir(exist_ok=True)
        exported_diagrams = output.export_diagrams(str(diagrams_dir))
        print(f"Exported {len(exported_diagrams)} Mermaid diagrams")

        # Export JSON output
        json_output = output.to_json()
        json_path = project_dir / "requirements_output.json"
        with open(json_path, "w") as f:
            json.dump(json_output, f, indent=2)
        print(f"Exported JSON output to: {json_path}")

        # Export user stories as markdown
        stories_path = project_dir / "user_stories.md"
        with open(stories_path, "w") as f:
            f.write(f"# User Stories - {output.project_name}\n\n")
            f.write(f"Generated: {output.generated_at}\n\n")
            for story in output.user_stories:
                f.write(f"## {story.id}: {story.feature}\n\n")
                f.write(f"**As a** {story.role}\n\n")
                f.write(f"**I want** {story.feature}\n\n")
                f.write(f"**So that** {story.benefit}\n\n")
                f.write(f"**Priority:** {story.priority.value}\n\n")
                if story.acceptance_criteria:
                    f.write("**Acceptance Criteria:**\n\n")
                    for ac in story.acceptance_criteria:
                        f.write(f"- [ ] {ac}\n")
                f.write("\n---\n\n")
        print(f"Exported user stories to: {stories_path}")

        # Export requirements specification
        spec_path = project_dir / "requirements_specification.md"
        with open(spec_path, "w") as f:
            f.write(f"# Requirements Specification - {output.project_name}\n\n")
            f.write(f"Version: {output.version}\n\n")
            f.write(f"Generated: {output.generated_at}\n\n")

            f.write("## Table of Contents\n\n")
            f.write("1. [Functional Requirements](#functional-requirements)\n")
            f.write("2. [Non-Functional Requirements](#non-functional-requirements)\n")
            f.write("3. [Use Cases](#use-cases)\n")
            f.write("4. [API Specification](#api-specification)\n\n")

            f.write("## Functional Requirements\n\n")
            for req in output.functional_requirements:
                f.write(f"### {req.id}: {req.title}\n\n")
                f.write(f"{req.description}\n\n")
                f.write(f"- **Priority:** {req.priority.value}\n")
                if req.rationale:
                    f.write(f"- **Rationale:** {req.rationale}\n")
                if req.verification_method:
                    f.write(f"- **Verification:** {req.verification_method}\n")
                f.write("\n")

            f.write("## Non-Functional Requirements\n\n")
            for req in output.non_functional_requirements:
                f.write(f"### {req.id}: {req.title}\n\n")
                f.write(f"**Category:** {req.category}\n\n")
                f.write(f"{req.description}\n\n")
                if req.metric:
                    f.write(f"- **Metric:** {req.metric}\n")
                f.write(f"- **Priority:** {req.priority.value}\n\n")

            f.write("## Use Cases\n\n")
            for uc in output.use_cases:
                f.write(f"### {uc.id}: {uc.name}\n\n")
                f.write(f"{uc.description}\n\n")
                f.write(f"**Actors:** {', '.join(uc.actors)}\n\n")
                if uc.preconditions:
                    f.write("**Preconditions:**\n\n")
                    for pre in uc.preconditions:
                        f.write(f"- {pre}\n")
                    f.write("\n")
                if uc.main_flow:
                    f.write("**Main Flow:**\n\n")
                    for i, step in enumerate(uc.main_flow, 1):
                        f.write(f"{i}. {step}\n")
                    f.write("\n")
                if uc.postconditions:
                    f.write("**Postconditions:**\n\n")
                    for post in uc.postconditions:
                        f.write(f"- {post}\n")
                    f.write("\n")

            f.write("## API Specification\n\n")
            for endpoint in output.api_endpoints:
                f.write(f"### `{endpoint.method} {endpoint.path}`\n\n")
                f.write(f"{endpoint.description}\n\n")
                auth = "Required" if endpoint.authentication_required else "Not required"
                f.write(f"**Authentication:** {auth}\n\n")
                if endpoint.request_body:
                    f.write("**Request Body:**\n\n```json\n")
                    f.write(json.dumps(endpoint.request_body, indent=2))
                    f.write("\n```\n\n")
                if endpoint.response_schema:
                    f.write("**Response:**\n\n```json\n")
                    f.write(json.dumps(endpoint.response_schema, indent=2))
                    f.write("\n```\n\n")

        print(f"Exported requirements specification to: {spec_path}")

        # Export for next stages (structured data for code generation)
        next_stage_path = project_dir / "for_code_generation.json"
        next_stage_data = {
            "project_name": output.project_name,
            "entities": [
                {
                    "name": e.name,
                    "description": e.description,
                    "attributes": e.attributes,
                    "methods": e.methods,
                    "relationships": e.relationships,
                }
                for e in output.entities
            ],
            "api_endpoints": [
                {
                    "path": ep.path,
                    "method": ep.method,
                    "description": ep.description,
                    "request_body": ep.request_body,
                    "response_schema": ep.response_schema,
                    "authentication_required": ep.authentication_required,
                }
                for ep in output.api_endpoints
            ],
            "components": [
                {
                    "name": c.name,
                    "type": c.type,
                    "technologies": c.technologies,
                    "dependencies": c.dependencies,
                }
                for c in output.components
            ],
        }
        with open(next_stage_path, "w") as f:
            json.dump(next_stage_data, f, indent=2)
        print(f"Exported code generation input to: {next_stage_path}")

        # Export for testing stage
        testing_stage_path = project_dir / "for_testing.json"
        testing_data = {
            "project_name": output.project_name,
            "user_stories": [
                {
                    "id": us.id,
                    "feature": us.feature,
                    "acceptance_criteria": us.acceptance_criteria,
                }
                for us in output.user_stories
            ],
            "functional_requirements": [
                {
                    "id": fr.id,
                    "title": fr.title,
                    "verification_method": fr.verification_method,
                }
                for fr in output.functional_requirements
            ],
            "non_functional_requirements": [
                {
                    "id": nfr.id,
                    "title": nfr.title,
                    "category": nfr.category,
                    "metric": nfr.metric,
                }
                for nfr in output.non_functional_requirements
            ],
            "api_endpoints": [
                {
                    "path": ep.path,
                    "method": ep.method,
                    "description": ep.description,
                }
                for ep in output.api_endpoints
            ],
        }
        with open(testing_stage_path, "w") as f:
            json.dump(testing_data, f, indent=2)
        print(f"Exported testing stage input to: {testing_stage_path}")


def create_input_from_text(
    project_name: str,
    description: str,
    requirements_text: str,
    domain: str = "other",
    technologies: list[str] | None = None,
) -> RequirementsInput:
    """
    Convenience function to create RequirementsInput from simple text.

    Args:
        project_name: Name of the project
        description: Project description
        requirements_text: Raw requirements in natural language
        domain: Project domain (web_application, api_service, etc.)
        technologies: List of target technologies

    Returns:
        RequirementsInput ready for processing
    """
    domain_map = {
        "web": ProjectDomain.WEB_APPLICATION,
        "web_application": ProjectDomain.WEB_APPLICATION,
        "mobile": ProjectDomain.MOBILE_APP,
        "mobile_app": ProjectDomain.MOBILE_APP,
        "api": ProjectDomain.API_SERVICE,
        "api_service": ProjectDomain.API_SERVICE,
        "cli": ProjectDomain.CLI_TOOL,
        "cli_tool": ProjectDomain.CLI_TOOL,
        "data": ProjectDomain.DATA_PIPELINE,
        "data_pipeline": ProjectDomain.DATA_PIPELINE,
        "desktop": ProjectDomain.DESKTOP_APP,
        "desktop_app": ProjectDomain.DESKTOP_APP,
        "embedded": ProjectDomain.EMBEDDED_SYSTEM,
        "embedded_system": ProjectDomain.EMBEDDED_SYSTEM,
    }

    return RequirementsInput(
        project_name=project_name,
        project_description=description,
        raw_requirements=requirements_text,
        requirement_type=RequirementType.NATURAL_LANGUAGE,
        domain=domain_map.get(domain.lower(), ProjectDomain.OTHER),
        target_technologies=technologies or [],
    )


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the Requirements Stage")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--description", required=True, help="Project description")
    parser.add_argument("--requirements-file", required=True, help="Path to requirements text file")
    parser.add_argument("--output-dir", default="./outputs", help="Output directory")
    parser.add_argument("--domain", default="other", help="Project domain")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="LLM model to use")

    args = parser.parse_args()

    # Read requirements from file
    with open(args.requirements_file) as f:
        requirements_text = f.read()

    # Create input
    input_data = create_input_from_text(
        project_name=args.project,
        description=args.description,
        requirements_text=requirements_text,
        domain=args.domain,
    )

    # Note: In actual usage, you'd need to configure the LLM client
    print("Note: This requires an LLM client to be configured.")
    print("See the example usage for how to set this up.")
