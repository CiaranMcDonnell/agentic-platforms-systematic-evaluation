"""
Requirements Agent

The core agent for the Requirements Stage that processes natural language requirements
and produces structured requirements, user stories, and Mermaid diagrams.

This agent can be implemented with different agentic platforms for DESMET evaluation.
"""

import json
from abc import ABC, abstractmethod
from typing import Any

from desmet.llm_config import DEFAULT_MODEL, DEFAULT_TEMPERATURE

from ..schemas import (
    Actor,
    APIEndpoint,
    Component,
    DiagramType,
    Entity,
    FunctionalRequirement,
    MermaidDiagram,
    NonFunctionalRequirement,
    RequirementPriority,
    RequirementsInput,
    RequirementsOutput,
    UseCase,
    UserStory,
)
from ..templates.mermaid_templates import MermaidTemplates


class BaseRequirementsAgent(ABC):
    """
    Abstract base class for Requirements Agent implementations.

    Different agentic platforms (LangGraph, CrewAI, etc.) should implement
    this interface to enable DESMET comparison.
    """

    def __init__(self, model: str = DEFAULT_MODEL, temperature: float = DEFAULT_TEMPERATURE):
        self.model = model
        self.temperature = temperature
        self.templates = MermaidTemplates()

    @abstractmethod
    async def analyze_requirements(self, input_data: RequirementsInput) -> RequirementsOutput:
        """
        Main entry point: Analyze requirements and produce structured output.

        Args:
            input_data: The requirements input containing raw requirements

        Returns:
            RequirementsOutput containing structured requirements and diagrams
        """
        pass

    @abstractmethod
    async def extract_user_stories(self, context: str) -> list[UserStory]:
        """Extract user stories from requirements context."""
        pass

    @abstractmethod
    async def extract_functional_requirements(self, context: str) -> list[FunctionalRequirement]:
        """Extract functional requirements from context."""
        pass

    @abstractmethod
    async def extract_non_functional_requirements(self, context: str) -> list[NonFunctionalRequirement]:
        """Extract non-functional requirements from context."""
        pass

    @abstractmethod
    async def identify_actors(self, context: str) -> list[Actor]:
        """Identify system actors from requirements."""
        pass

    @abstractmethod
    async def design_use_cases(self, context: str, actors: list[Actor]) -> list[UseCase]:
        """Design use cases based on requirements and actors."""
        pass

    @abstractmethod
    async def design_entities(self, context: str) -> list[Entity]:
        """Design domain entities/classes from requirements."""
        pass

    @abstractmethod
    async def design_components(self, context: str) -> list[Component]:
        """Design system components from requirements."""
        pass

    @abstractmethod
    async def design_api_endpoints(self, context: str, entities: list[Entity]) -> list[APIEndpoint]:
        """Design API endpoints based on requirements and entities."""
        pass


class RequirementsAgentPrompts:
    """Prompts for the Requirements Agent LLM calls."""

    SYSTEM_PROMPT = """You are an expert requirements engineer and software architect.
Your role is to analyze natural language requirements and produce:
1. Well-structured user stories with acceptance criteria
2. Functional and non-functional requirements
3. Use case specifications
4. Domain entity/class designs
5. System component architecture
6. API endpoint specifications

Always produce output in valid JSON format as specified in each prompt.
Be thorough but concise. Focus on actionable, testable requirements."""

    USER_STORIES_PROMPT = """Analyze the following project requirements and extract user stories.

{context}

For each user story, identify:
- A unique ID (format: US-001, US-002, etc.)
- The user role
- The desired feature/capability
- The benefit/value
- 2-5 specific acceptance criteria
- Priority (critical, high, medium, low)
- Dependencies on other user stories (if any)

Respond with a JSON array of user stories:
```json
[
  {{
    "id": "US-001",
    "role": "user role",
    "feature": "what they want",
    "benefit": "why they want it",
    "acceptance_criteria": ["criterion 1", "criterion 2"],
    "priority": "high",
    "dependencies": []
  }}
]
```"""

    FUNCTIONAL_REQUIREMENTS_PROMPT = """Analyze the following project requirements and extract functional requirements.

{context}

For each functional requirement, provide:
- A unique ID (format: FR-001, FR-002, etc.)
- A clear title
- A detailed description
- Priority (critical, high, medium, low)
- Rationale (why this requirement exists)
- Related user story IDs
- Verification method (how to test this)

Respond with a JSON array:
```json
[
  {{
    "id": "FR-001",
    "title": "Requirement title",
    "description": "Detailed description",
    "priority": "high",
    "rationale": "Business justification",
    "related_user_stories": ["US-001"],
    "verification_method": "How to verify"
  }}
]
```"""

    NON_FUNCTIONAL_REQUIREMENTS_PROMPT = """Analyze the following project requirements and identify non-functional requirements (quality attributes).

{context}

Consider these categories:
- Performance (response times, throughput)
- Security (authentication, authorization, data protection)
- Scalability (load handling, horizontal/vertical scaling)
- Reliability (uptime, fault tolerance)
- Usability (accessibility, learnability)
- Maintainability (code quality, documentation)

For each NFR, provide:
- A unique ID (format: NFR-001, NFR-002, etc.)
- Title
- Description
- Category
- Measurable metric (e.g., "Response time < 200ms")
- Priority

Respond with a JSON array:
```json
[
  {{
    "id": "NFR-001",
    "title": "Performance - API Response Time",
    "description": "All API endpoints should respond quickly",
    "category": "Performance",
    "metric": "95th percentile response time < 200ms",
    "priority": "high"
  }}
]
```"""

    ACTORS_PROMPT = """Identify all actors (users, systems, external services) that interact with the system.

{context}

For each actor, provide:
- Name
- Description of their role
- Type (primary, secondary, external_system)

Respond with a JSON array:
```json
[
  {{
    "name": "End User",
    "description": "A registered user of the application",
    "type": "primary"
  }},
  {{
    "name": "Payment Gateway",
    "description": "External payment processing service",
    "type": "external_system"
  }}
]
```"""

    USE_CASES_PROMPT = """Design use cases for the system based on requirements and actors.

{context}

Actors identified: {actors}

For each use case, provide:
- Unique ID (format: UC-001, UC-002, etc.)
- Name
- Description
- Primary and secondary actors involved
- Preconditions
- Postconditions
- Main flow (numbered steps)
- Alternative flows (if any)
- Exception handling

Respond with a JSON array:
```json
[
  {{
    "id": "UC-001",
    "name": "User Login",
    "description": "Allows a user to authenticate",
    "actors": ["End User"],
    "preconditions": ["User has a registered account"],
    "postconditions": ["User is authenticated", "Session is created"],
    "main_flow": [
      "User navigates to login page",
      "User enters credentials",
      "System validates credentials",
      "System creates session",
      "User is redirected to dashboard"
    ],
    "alternative_flows": [],
    "exceptions": ["Invalid credentials: Show error message"]
  }}
]
```"""

    ENTITIES_PROMPT = """Design the domain entities/classes for the system.

{context}

For each entity, provide:
- Name
- Description
- Attributes (name, type, required, description)
- Methods (name, parameters, return_type, description)
- Relationships to other entities (target, type, cardinality)

Relationship types: association, aggregation, composition, inheritance

Respond with a JSON array:
```json
[
  {{
    "name": "User",
    "description": "Represents a system user",
    "attributes": [
      {{"name": "id", "type": "UUID", "required": true, "description": "Unique identifier"}},
      {{"name": "email", "type": "String", "required": true, "description": "User email"}},
      {{"name": "passwordHash", "type": "String", "required": true, "description": "Hashed password"}}
    ],
    "methods": [
      {{"name": "authenticate", "parameters": "password: String", "return_type": "Boolean", "description": "Verify password"}}
    ],
    "relationships": [
      {{"target": "Role", "type": "association", "cardinality": "many-to-many"}}
    ]
  }}
]
```"""

    COMPONENTS_PROMPT = """Design the high-level system components/architecture.

{context}

For each component, provide:
- Name
- Description
- Type (service, database, api, ui, queue, cache, etc.)
- Interfaces it exposes
- Dependencies on other components
- Suggested technologies

Respond with a JSON array:
```json
[
  {{
    "name": "API Gateway",
    "description": "Handles all incoming HTTP requests and routing",
    "type": "api",
    "interfaces": ["REST API", "WebSocket"],
    "dependencies": ["Auth Service", "User Service"],
    "technologies": ["Express.js", "nginx"]
  }}
]
```"""

    API_ENDPOINTS_PROMPT = """Design the API endpoints for the system.

{context}

Entities: {entities}

For each endpoint, provide:
- Path
- HTTP method
- Description
- Request body schema (if applicable)
- Response schema
- Query/path parameters
- Whether authentication is required
- Related use cases

Respond with a JSON array:
```json
[
  {{
    "path": "/api/users",
    "method": "POST",
    "description": "Create a new user",
    "request_body": {{"email": "string", "password": "string", "name": "string"}},
    "response_schema": {{"id": "uuid", "email": "string", "name": "string", "createdAt": "datetime"}},
    "parameters": [],
    "authentication_required": false,
    "related_use_cases": ["UC-002"]
  }}
]
```"""


class SimpleRequirementsAgent(BaseRequirementsAgent):
    """
    A simple implementation of the Requirements Agent using direct LLM calls.

    This can serve as a baseline or be adapted for specific platforms.
    """

    def __init__(
        self,
        llm_client: Any = None,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE
    ):
        super().__init__(model, temperature)
        self.llm_client = llm_client
        self.prompts = RequirementsAgentPrompts()

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Make an LLM call and return the response."""
        if self.llm_client is None:
            raise ValueError("LLM client not configured. Please provide an LLM client.")

        # This is a generic interface - specific implementations will override
        response = await self.llm_client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content

    def _parse_json_response(self, response: str) -> Any:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Remove markdown code blocks if present
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        return json.loads(response.strip())

    async def analyze_requirements(self, input_data: RequirementsInput) -> RequirementsOutput:
        """Main entry point for requirement analysis."""
        context = input_data.to_prompt_context()

        # Extract all requirement artifacts
        user_stories = await self.extract_user_stories(context)
        functional_reqs = await self.extract_functional_requirements(context)
        non_functional_reqs = await self.extract_non_functional_requirements(context)
        actors = await self.identify_actors(context)
        use_cases = await self.design_use_cases(context, actors)
        entities = await self.design_entities(context)
        components = await self.design_components(context)
        api_endpoints = await self.design_api_endpoints(context, entities)

        # Generate Mermaid diagrams
        diagrams = self._generate_diagrams(
            actors, use_cases, entities, components, input_data.project_name
        )

        # Build traceability matrix
        traceability = self._build_traceability_matrix(
            user_stories, functional_reqs, use_cases
        )

        return RequirementsOutput(
            project_name=input_data.project_name,
            user_stories=user_stories,
            functional_requirements=functional_reqs,
            non_functional_requirements=non_functional_reqs,
            actors=actors,
            use_cases=use_cases,
            entities=entities,
            components=components,
            api_endpoints=api_endpoints,
            diagrams=diagrams,
            traceability_matrix=traceability,
            summary=f"Requirements analysis for {input_data.project_name}",
        )

    async def extract_user_stories(self, context: str) -> list[UserStory]:
        """Extract user stories from requirements."""
        prompt = self.prompts.USER_STORIES_PROMPT.format(context=context)
        response = await self._call_llm(self.prompts.SYSTEM_PROMPT, prompt)
        data = self._parse_json_response(response)

        return [
            UserStory(
                id=item["id"],
                role=item["role"],
                feature=item["feature"],
                benefit=item["benefit"],
                acceptance_criteria=item.get("acceptance_criteria", []),
                priority=RequirementPriority(item.get("priority", "medium")),
                dependencies=item.get("dependencies", []),
            )
            for item in data
        ]

    async def extract_functional_requirements(self, context: str) -> list[FunctionalRequirement]:
        """Extract functional requirements."""
        prompt = self.prompts.FUNCTIONAL_REQUIREMENTS_PROMPT.format(context=context)
        response = await self._call_llm(self.prompts.SYSTEM_PROMPT, prompt)
        data = self._parse_json_response(response)

        return [
            FunctionalRequirement(
                id=item["id"],
                title=item["title"],
                description=item["description"],
                priority=RequirementPriority(item.get("priority", "medium")),
                rationale=item.get("rationale"),
                related_user_stories=item.get("related_user_stories", []),
                verification_method=item.get("verification_method"),
            )
            for item in data
        ]

    async def extract_non_functional_requirements(self, context: str) -> list[NonFunctionalRequirement]:
        """Extract non-functional requirements."""
        prompt = self.prompts.NON_FUNCTIONAL_REQUIREMENTS_PROMPT.format(context=context)
        response = await self._call_llm(self.prompts.SYSTEM_PROMPT, prompt)
        data = self._parse_json_response(response)

        return [
            NonFunctionalRequirement(
                id=item["id"],
                title=item["title"],
                description=item["description"],
                category=item.get("category", "General"),
                metric=item.get("metric"),
                priority=RequirementPriority(item.get("priority", "medium")),
            )
            for item in data
        ]

    async def identify_actors(self, context: str) -> list[Actor]:
        """Identify system actors."""
        prompt = self.prompts.ACTORS_PROMPT.format(context=context)
        response = await self._call_llm(self.prompts.SYSTEM_PROMPT, prompt)
        data = self._parse_json_response(response)

        return [
            Actor(
                name=item["name"],
                description=item["description"],
                type=item.get("type", "primary"),
            )
            for item in data
        ]

    async def design_use_cases(self, context: str, actors: list[Actor]) -> list[UseCase]:
        """Design use cases."""
        actors_str = json.dumps([{"name": a.name, "type": a.type} for a in actors])
        prompt = self.prompts.USE_CASES_PROMPT.format(context=context, actors=actors_str)
        response = await self._call_llm(self.prompts.SYSTEM_PROMPT, prompt)
        data = self._parse_json_response(response)

        return [
            UseCase(
                id=item["id"],
                name=item["name"],
                description=item["description"],
                actors=item.get("actors", []),
                preconditions=item.get("preconditions", []),
                postconditions=item.get("postconditions", []),
                main_flow=item.get("main_flow", []),
                alternative_flows=item.get("alternative_flows", []),
                exceptions=item.get("exceptions", []),
            )
            for item in data
        ]

    async def design_entities(self, context: str) -> list[Entity]:
        """Design domain entities."""
        prompt = self.prompts.ENTITIES_PROMPT.format(context=context)
        response = await self._call_llm(self.prompts.SYSTEM_PROMPT, prompt)
        data = self._parse_json_response(response)

        return [
            Entity(
                name=item["name"],
                description=item["description"],
                attributes=item.get("attributes", []),
                methods=item.get("methods", []),
                relationships=item.get("relationships", []),
            )
            for item in data
        ]

    async def design_components(self, context: str) -> list[Component]:
        """Design system components."""
        prompt = self.prompts.COMPONENTS_PROMPT.format(context=context)
        response = await self._call_llm(self.prompts.SYSTEM_PROMPT, prompt)
        data = self._parse_json_response(response)

        return [
            Component(
                name=item["name"],
                description=item["description"],
                type=item.get("type", "service"),
                interfaces=item.get("interfaces", []),
                dependencies=item.get("dependencies", []),
                technologies=item.get("technologies", []),
            )
            for item in data
        ]

    async def design_api_endpoints(self, context: str, entities: list[Entity]) -> list[APIEndpoint]:
        """Design API endpoints."""
        entities_str = json.dumps([{"name": e.name, "attributes": e.attributes} for e in entities])
        prompt = self.prompts.API_ENDPOINTS_PROMPT.format(context=context, entities=entities_str)
        response = await self._call_llm(self.prompts.SYSTEM_PROMPT, prompt)
        data = self._parse_json_response(response)

        return [
            APIEndpoint(
                path=item["path"],
                method=item["method"],
                description=item["description"],
                request_body=item.get("request_body"),
                response_schema=item.get("response_schema"),
                parameters=item.get("parameters", []),
                authentication_required=item.get("authentication_required", True),
                related_use_cases=item.get("related_use_cases", []),
            )
            for item in data
        ]

    def _generate_diagrams(
        self,
        actors: list[Actor],
        use_cases: list[UseCase],
        entities: list[Entity],
        components: list[Component],
        project_name: str,
    ) -> list[MermaidDiagram]:
        """Generate Mermaid diagrams from extracted data."""
        diagrams = []

        # Use Case Diagram
        if actors and use_cases:
            actor_data = [{"name": a.name, "type": a.type} for a in actors]
            uc_data = [{"id": uc.id, "name": uc.name, "package": "System"} for uc in use_cases]

            # Build relationships from actors to use cases
            relationships = []
            for uc in use_cases:
                for actor_name in uc.actors:
                    relationships.append({
                        "from": actor_name,
                        "to": uc.id,
                        "type": "uses"
                    })
                for inc in uc.includes:
                    relationships.append({
                        "from": uc.id,
                        "to": inc,
                        "type": "includes"
                    })

            uc_diagram = self.templates.use_case_diagram(
                title=f"{project_name} - Use Case Diagram",
                actors=actor_data,
                use_cases=uc_data,
                relationships=relationships
            )
            diagrams.append(MermaidDiagram(
                diagram_type=DiagramType.USE_CASE,
                name="System Use Cases",
                description="Use case diagram showing actors and system functionality",
                mermaid_code=uc_diagram,
            ))

        # Class Diagram
        if entities:
            class_data = []
            relationships = []

            for entity in entities:
                cls = {
                    "name": entity.name,
                    "attributes": [
                        {
                            "name": attr.get("name", "unknown"),
                            "type": attr.get("type", "String"),
                            "visibility": "+"
                        }
                        for attr in entity.attributes
                    ],
                    "methods": [
                        {
                            "name": m.get("name", "unknown"),
                            "return_type": m.get("return_type", "void"),
                            "parameters": m.get("parameters", ""),
                            "visibility": "+"
                        }
                        for m in entity.methods
                    ],
                }
                class_data.append(cls)

                for rel in entity.relationships:
                    relationships.append({
                        "from": entity.name,
                        "to": rel.get("target", "Unknown"),
                        "type": rel.get("type", "association"),
                        "cardinality": rel.get("cardinality", "")
                    })

            class_diagram = self.templates.class_diagram(
                title=f"{project_name} - Domain Model",
                classes=class_data,
                relationships=relationships
            )
            diagrams.append(MermaidDiagram(
                diagram_type=DiagramType.CLASS,
                name="Domain Model",
                description="Class diagram showing domain entities and relationships",
                mermaid_code=class_diagram,
            ))

        # Component Diagram
        if components:
            comp_data = [
                {"name": c.name, "stereotype": c.type}
                for c in components
            ]
            connections = []
            for comp in components:
                for dep in comp.dependencies:
                    connections.append({
                        "from": comp.name,
                        "to": dep,
                        "label": "depends on"
                    })

            comp_diagram = self.templates.component_diagram(
                title=f"{project_name} - System Architecture",
                components=comp_data,
                connections=connections
            )
            diagrams.append(MermaidDiagram(
                diagram_type=DiagramType.COMPONENT,
                name="System Architecture",
                description="Component diagram showing system structure",
                mermaid_code=comp_diagram,
            ))

        # Entity Relationship Diagram
        if entities:
            er_entities = []
            er_relationships = []

            for entity in entities:
                er_entity = {
                    "name": entity.name,
                    "attributes": [
                        {
                            "name": attr.get("name", "unknown"),
                            "type": attr.get("type", "String"),
                            "pk": attr.get("name") == "id",
                        }
                        for attr in entity.attributes
                    ]
                }
                er_entities.append(er_entity)

                for rel in entity.relationships:
                    # Convert cardinality to ER notation
                    cardinality = rel.get("cardinality", "one-to-many")
                    from_card = "1"
                    to_card = "*"
                    if "one-to-one" in cardinality:
                        to_card = "1"
                    elif "many-to-many" in cardinality:
                        from_card = "*"

                    er_relationships.append({
                        "from": entity.name,
                        "to": rel.get("target", "Unknown"),
                        "from_cardinality": from_card,
                        "to_cardinality": to_card,
                        "label": rel.get("type", "")
                    })

            er_diagram = self.templates.entity_relationship_diagram(
                title=f"{project_name} - Data Model",
                entities=er_entities,
                relationships=er_relationships
            )
            diagrams.append(MermaidDiagram(
                diagram_type=DiagramType.ENTITY_RELATIONSHIP,
                name="Data Model",
                description="Entity-relationship diagram for database design",
                mermaid_code=er_diagram,
            ))

        return diagrams

    def _build_traceability_matrix(
        self,
        user_stories: list[UserStory],
        functional_reqs: list[FunctionalRequirement],
        use_cases: list[UseCase],
    ) -> dict[str, list[str]]:
        """Build a traceability matrix linking requirements to use cases."""
        matrix = {}

        for us in user_stories:
            matrix[us.id] = []
            # Find related functional requirements
            for fr in functional_reqs:
                if us.id in fr.related_user_stories:
                    matrix[us.id].append(fr.id)

        for fr in functional_reqs:
            if fr.id not in matrix:
                matrix[fr.id] = []
            # Add use case links
            for uc in use_cases:
                # Simple heuristic: match if title words appear in use case name
                if any(word.lower() in uc.name.lower() for word in fr.title.split()):
                    matrix[fr.id].append(uc.id)

        return matrix
