"""SpecBuilder — deterministic transform from GatheredInfo to Specification."""

from __future__ import annotations

import uuid

import yaml

from rooben.refinement.state import GatheredInfo
from rooben.spec.models import (
    AcceptanceCriterion,
    AgentSpec,
    Constraint,
    ConstraintCategory,
    Deliverable,
    DeliverableType,
    InputSource,
    InputSourceType,
    Specification,
    WorkflowHint,
)


class SpecBuilder:
    """Converts gathered information into a validated Specification."""

    def build(
        self,
        gathered_info: GatheredInfo,
        agents: list[AgentSpec],
        workflow_hints: list[dict] | None = None,
    ) -> Specification:
        """Build a Specification from gathered info and agent roster."""
        deliverables = self._build_deliverables(gathered_info)
        constraints = self._build_constraints(gathered_info)
        criteria = self._build_criteria(gathered_info)
        input_sources = self._build_input_sources(gathered_info)
        hints = self._build_workflow_hints(workflow_hints or [])

        spec = Specification(
            id=f"spec-{uuid.uuid4().hex[:8]}",
            title=gathered_info.title or "Untitled Project",
            goal=gathered_info.goal or "Complete the project",
            deliverables=deliverables,
            agents=agents,
            constraints=constraints,
            input_sources=input_sources,
            workflow_hints=hints,
        )
        if criteria:
            spec.success_criteria.acceptance_criteria = criteria

        return spec

    def to_yaml(self, spec: Specification) -> str:
        """Serialize a Specification to YAML."""
        data = spec.model_dump(mode="json", exclude_defaults=True)
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def _build_deliverables(self, info: GatheredInfo) -> list[Deliverable]:
        deliverables = []
        for i, d in enumerate(info.deliverables, 1):
            dt = d.get("deliverable_type", "code")
            try:
                dtype = DeliverableType(dt)
            except ValueError:
                dtype = DeliverableType.CODE

            deliverables.append(Deliverable(
                id=d.get("id", f"D-{i:03d}"),
                name=d.get("name", f"Deliverable {i}"),
                deliverable_type=dtype,
                description=d.get("description", ""),
            ))

        if not deliverables:
            deliverables.append(Deliverable(
                id="D-001",
                name="Primary Output",
                deliverable_type=DeliverableType.CODE,
                description=info.goal or "Project output",
            ))

        return deliverables

    def _build_constraints(self, info: GatheredInfo) -> list[Constraint]:
        constraints = []
        for i, c in enumerate(info.constraints, 1):
            cat = c.get("category", "other")
            try:
                category = ConstraintCategory(cat)
            except ValueError:
                category = ConstraintCategory.OTHER

            constraints.append(Constraint(
                id=f"C-{i:03d}",
                category=category,
                description=c.get("description", ""),
            ))
        return constraints

    def _build_criteria(self, info: GatheredInfo) -> list[AcceptanceCriterion]:
        criteria = []
        for i, ac in enumerate(info.acceptance_criteria, 1):
            criteria.append(AcceptanceCriterion(
                id=f"AC-{i:03d}",
                description=ac.get("description", ""),
            ))
        return criteria

    def _build_workflow_hints(self, hints: list[dict]) -> list[WorkflowHint]:
        result = []
        for h in hints:
            result.append(WorkflowHint(
                name=h.get("name", ""),
                description=h.get("description", ""),
                suggested_agent_id=h.get("suggested_agent"),
                depends_on=h.get("depends_on", []),
            ))
        return result

    def _build_input_sources(self, info: GatheredInfo) -> list[InputSource]:
        sources = []
        for s in info.input_sources:
            src_type = s.get("type", "mcp")
            try:
                ist = InputSourceType(src_type)
            except ValueError:
                ist = InputSourceType.MCP

            sources.append(InputSource(
                name=s.get("name", f"source-{len(sources) + 1}"),
                type=ist,
                integration=s.get("integration"),
                description=s.get("description", ""),
                query=s.get("query", {}),
                required=s.get("required", True),
                pre_fetch=s.get("pre_fetch", True),
            ))
        return sources
