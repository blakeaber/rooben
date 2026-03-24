"""SpecValidator — pre-execution validation of Specification objects."""

from __future__ import annotations

from dataclasses import dataclass, field

from rooben.spec.models import AgentTransport, Specification


@dataclass
class ValidationResult:
    """Result of validating a Specification."""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = []
        if self.errors:
            lines.append(f"  Errors ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"    - {e}")
        if self.warnings:
            lines.append(f"  Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"    - {w}")
        if not lines:
            lines.append("  No issues found.")
        return "\n".join(lines)


class SpecValidator:
    """Validates a Specification before execution."""

    def validate(self, spec: Specification) -> ValidationResult:
        """Run all validation checks."""
        result = ValidationResult()
        self._check_transport_config(spec, result)
        self._check_acceptance_criteria_refs(spec, result)
        self._check_agent_refs_in_hints(spec, result)
        self._check_minimum_content(spec, result)
        self._check_duplicate_ids(spec, result)
        self._check_budget_sanity(spec, result)
        return result

    def _check_transport_config(self, spec: Specification, result: ValidationResult) -> None:
        for agent in spec.agents:
            if agent.transport == AgentTransport.HTTP:
                if not agent.endpoint or not agent.endpoint.startswith(("http://", "https://")):
                    result.errors.append(
                        f"Agent '{agent.id}' uses HTTP transport but has no valid endpoint URL"
                    )
            elif agent.transport == AgentTransport.SUBPROCESS:
                if not agent.endpoint:
                    result.errors.append(
                        f"Agent '{agent.id}' uses subprocess transport but has no endpoint (Python dotted path)"
                    )
            elif agent.transport == AgentTransport.MCP:
                if not agent.mcp_servers:
                    result.errors.append(
                        f"Agent '{agent.id}' uses MCP transport but has no mcp_servers configured"
                    )

    def _check_acceptance_criteria_refs(self, spec: Specification, result: ValidationResult) -> None:
        ac_ids = {ac.id for ac in spec.success_criteria.acceptance_criteria}
        for deliverable in spec.deliverables:
            for ac_id in deliverable.acceptance_criteria_ids:
                if ac_id not in ac_ids:
                    result.errors.append(
                        f"Deliverable '{deliverable.id}' references non-existent acceptance criterion '{ac_id}'"
                    )

    def _check_agent_refs_in_hints(self, spec: Specification, result: ValidationResult) -> None:
        agent_ids = {a.id for a in spec.agents}
        for hint in spec.workflow_hints:
            if hint.suggested_agent_id and hint.suggested_agent_id not in agent_ids:
                result.warnings.append(
                    f"Workflow hint '{hint.name}' references non-existent agent '{hint.suggested_agent_id}'"
                )

    def _check_minimum_content(self, spec: Specification, result: ValidationResult) -> None:
        if not spec.deliverables:
            result.errors.append("Specification has no deliverables")
        if not spec.success_criteria.acceptance_criteria:
            result.warnings.append("Specification has no acceptance criteria")
        if not spec.agents:
            result.errors.append("Specification has no agents")

    def _check_duplicate_ids(self, spec: Specification, result: ValidationResult) -> None:
        # Check across all ID namespaces
        all_ids: list[tuple[str, str]] = []
        for d in spec.deliverables:
            all_ids.append((d.id, "deliverable"))
        for ac in spec.success_criteria.acceptance_criteria:
            all_ids.append((ac.id, "acceptance_criterion"))
        for a in spec.agents:
            all_ids.append((a.id, "agent"))

        seen: dict[str, str] = {}
        for id_val, id_type in all_ids:
            if id_val in seen:
                result.errors.append(
                    f"Duplicate ID '{id_val}' used by both {seen[id_val]} and {id_type}"
                )
            else:
                seen[id_val] = id_type

    def _check_budget_sanity(self, spec: Specification, result: ValidationResult) -> None:
        if spec.global_budget:
            b = spec.global_budget
            if b.max_total_tokens and b.max_total_tokens > 100_000_000:
                result.warnings.append(
                    f"Global budget max_total_tokens is very large: {b.max_total_tokens:,}"
                )
            if b.max_total_tasks and b.max_total_tasks > 1000:
                result.warnings.append(
                    f"Global budget max_total_tasks is very large: {b.max_total_tasks}"
                )
