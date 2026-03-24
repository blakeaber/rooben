"""Tests for specification schema validation."""

from __future__ import annotations

import json
import tempfile

import pytest
import yaml

from rooben.spec.loader import load_spec
from rooben.spec.models import (
    AgentSpec,
    AgentTransport,
    Deliverable,
    DeliverableType,
    Specification,
)


class TestSpecValidation:
    def test_minimal_valid_spec(self):
        spec = Specification(
            id="test-1",
            title="Test",
            goal="Do something",
            deliverables=[
                Deliverable(
                    id="D-1",
                    name="Output",
                    deliverable_type=DeliverableType.CODE,
                    description="Some code",
                ),
            ],
            agents=[
                AgentSpec(
                    id="a-1",
                    name="Agent",
                    transport=AgentTransport.SUBPROCESS,
                    description="Does things",
                    endpoint="my.module.func",
                ),
            ],
        )
        assert spec.id == "test-1"
        assert len(spec.deliverables) == 1

    def test_empty_deliverables_rejected(self):
        with pytest.raises(Exception):
            Specification(
                id="test-2",
                title="Test",
                goal="Do something",
                deliverables=[],
                agents=[
                    AgentSpec(
                        id="a-1",
                        name="Agent",
                        transport=AgentTransport.SUBPROCESS,
                        description="Does things",
                        endpoint="my.module.func",
                    ),
                ],
            )

    def test_empty_agents_rejected(self):
        with pytest.raises(Exception):
            Specification(
                id="test-3",
                title="Test",
                goal="Do something",
                deliverables=[
                    Deliverable(
                        id="D-1",
                        name="Output",
                        deliverable_type=DeliverableType.CODE,
                        description="Some code",
                    ),
                ],
                agents=[],
            )

    def test_duplicate_deliverable_ids_rejected(self):
        with pytest.raises(Exception):
            Specification(
                id="test-4",
                title="Test",
                goal="Do something",
                deliverables=[
                    Deliverable(id="D-1", name="A", deliverable_type=DeliverableType.CODE, description="x"),
                    Deliverable(id="D-1", name="B", deliverable_type=DeliverableType.CODE, description="y"),
                ],
                agents=[
                    AgentSpec(
                        id="a-1",
                        name="Agent",
                        transport=AgentTransport.SUBPROCESS,
                        description="Does things",
                        endpoint="my.module.func",
                    ),
                ],
            )

    def test_duplicate_agent_ids_rejected(self):
        with pytest.raises(Exception):
            Specification(
                id="test-5",
                title="Test",
                goal="Do something",
                deliverables=[
                    Deliverable(id="D-1", name="A", deliverable_type=DeliverableType.CODE, description="x"),
                ],
                agents=[
                    AgentSpec(id="a-1", name="A", transport=AgentTransport.SUBPROCESS, description="x", endpoint="a.b"),
                    AgentSpec(id="a-1", name="B", transport=AgentTransport.SUBPROCESS, description="y", endpoint="c.d"),
                ],
            )

    def test_http_agent_requires_url(self):
        with pytest.raises(Exception):
            AgentSpec(
                id="a-1",
                name="Agent",
                transport=AgentTransport.HTTP,
                description="Does things",
                endpoint="not_a_url",
            )

    def test_content_hash_deterministic(self, sample_spec):
        h1 = sample_spec.content_hash()
        h2 = sample_spec.content_hash()
        assert h1 == h2
        assert len(h1) == 16


class TestSpecLoader:
    def test_load_yaml(self, sample_spec):
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(sample_spec.model_dump(mode="json"), f)
            f.flush()
            loaded = load_spec(f.name)
            assert loaded.id == sample_spec.id
            assert loaded.title == sample_spec.title

    def test_load_json(self, sample_spec):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(sample_spec.model_dump(mode="json"), f, default=str)
            f.flush()
            loaded = load_spec(f.name)
            assert loaded.id == sample_spec.id

    def test_unsupported_format(self):
        with tempfile.NamedTemporaryFile(suffix=".xml", mode="w", delete=False) as f:
            f.write("<spec/>")
            f.flush()
            with pytest.raises(ValueError, match="Unsupported"):
                load_spec(f.name)
