-- Demo seed: one completed workflow with three verified tasks + cost telemetry.
-- Mounted only via docker-compose.demo.yml (and therefore `make demo`), never
-- on production deploys. Postgres runs init scripts in ASCII order; this file
-- is mounted as `seed-demo.sql` so it runs AFTER `init.sql` (letters > digits,
-- and "s" > "i" alphabetically).
--
-- Idempotent: ON CONFLICT DO NOTHING on every insert so reruns are safe.

BEGIN;

INSERT INTO workflows
    (id, spec_id, status, total_tasks, completed_tasks, failed_tasks,
     created_at, completed_at, spec_yaml, spec_metadata)
VALUES
    ('demo', 'demo-spec-books-api', 'completed', 3, 3, 0,
     now() - interval '2 minutes', now() - interval '30 seconds',
     $YAML$
id: "demo-spec-books-api"
title: "Books API service"
goal: |
  Build a production-ready REST API for managing a book catalog with CRUD
  endpoints, validation, and pytest coverage of at least 90%.
context: |
  Hello-world service demonstrating Rooben's plan-execute-verify loop on a real
  codebase deliverable with verifiable acceptance criteria.

deliverables:
  - id: "D-001"
    name: "API Schema"
    deliverable_type: "document"
    description: "OpenAPI 3.1 schema defining the Book resource and 5 CRUD endpoints."
    output_path: "openapi.yaml"
  - id: "D-002"
    name: "FastAPI Service"
    deliverable_type: "code"
    description: "FastAPI implementation with Pydantic v2 models, in-memory store, and 5 endpoints."
    output_path: "app/main.py"
  - id: "D-003"
    name: "Test Suite"
    deliverable_type: "test"
    description: "pytest suite covering all 5 endpoints with >= 90% line coverage."
    output_path: "tests/test_books.py"
  - id: "D-004"
    name: "API Documentation"
    deliverable_type: "document"
    description: "README with runnable curl examples and JSON response samples for every endpoint."
    output_path: "README.md"

agents:
  - id: "demo-agent-architect"
    name: "API Architect"
    description: "Designs schemas, RESTful resource paths, and validation rules."
    transport: "llm"
  - id: "demo-agent-engineer"
    name: "Backend Engineer"
    description: "Implements FastAPI endpoints with Pydantic validation and pytest tests."
    transport: "llm"
  - id: "demo-agent-writer"
    name: "Documentation Writer"
    description: "Generates OpenAPI schemas and README curl examples from the implementation."
    transport: "llm"

success_criteria:
  acceptance_criteria:
    - id: "AC-001"
      description: "All 5 CRUD endpoints exist and return correct status codes (201/200/200/200/204)."
      verification: "test_runner"
      priority: "critical"
    - id: "AC-002"
      description: "Book resource validates required fields (id, title, author, isbn, publishedAt) using Pydantic."
      verification: "test_runner"
      priority: "critical"
    - id: "AC-003"
      description: "pytest test suite achieves >= 90% line coverage."
      verification: "test_runner"
      priority: "high"
    - id: "AC-004"
      description: "OpenAPI 3.1 schema validates against the openapi-spec-validator tool."
      verification: "llm_judge"
      priority: "high"
    - id: "AC-005"
      description: "README contains a runnable curl example for every endpoint plus a sample JSON response."
      verification: "llm_judge"
      priority: "medium"
  completion_threshold: 0.85

constraints:
  - id: "C-001"
    category: "technology"
    hard: true
    description: "Implementation must use FastAPI and Pydantic v2."
  - id: "C-002"
    category: "performance"
    hard: false
    description: "Each endpoint responds in under 50ms with the in-memory store."
  - id: "C-003"
    category: "budget"
    hard: true
    description: "Total token usage capped at 25,000 tokens across the workflow."

global_budget:
  max_total_tokens: 25000
  max_cost_usd: 1.00
  max_wall_seconds: 300
  max_concurrent_agents: 3
$YAML$,
     $JSON${
  "id": "demo-spec-books-api",
  "title": "Books API service",
  "goal": "Build a production-ready REST API for managing a book catalog with CRUD endpoints, validation, and pytest coverage of at least 90%.",
  "context": "Hello-world service demonstrating Rooben's plan-execute-verify loop on a real codebase deliverable with verifiable acceptance criteria.",
  "deliverables": [
    {"id": "D-001", "name": "API Schema", "deliverable_type": "document", "description": "OpenAPI 3.1 schema defining the Book resource and 5 CRUD endpoints.", "output_path": "openapi.yaml"},
    {"id": "D-002", "name": "FastAPI Service", "deliverable_type": "code", "description": "FastAPI implementation with Pydantic v2 models, in-memory store, and 5 endpoints.", "output_path": "app/main.py"},
    {"id": "D-003", "name": "Test Suite", "deliverable_type": "test", "description": "pytest suite covering all 5 endpoints with >= 90% line coverage.", "output_path": "tests/test_books.py"},
    {"id": "D-004", "name": "API Documentation", "deliverable_type": "document", "description": "README with runnable curl examples and JSON response samples for every endpoint.", "output_path": "README.md"}
  ],
  "agents": [
    {"id": "demo-agent-architect", "name": "API Architect", "description": "Designs schemas, RESTful resource paths, and validation rules.", "transport": "llm"},
    {"id": "demo-agent-engineer", "name": "Backend Engineer", "description": "Implements FastAPI endpoints with Pydantic validation and pytest tests.", "transport": "llm"},
    {"id": "demo-agent-writer", "name": "Documentation Writer", "description": "Generates OpenAPI schemas and README curl examples from the implementation.", "transport": "llm"}
  ],
  "acceptance_criteria": [
    {"id": "AC-001", "description": "All 5 CRUD endpoints exist and return correct status codes (201/200/200/200/204).", "priority": "critical"},
    {"id": "AC-002", "description": "Book resource validates required fields (id, title, author, isbn, publishedAt) using Pydantic.", "priority": "critical"},
    {"id": "AC-003", "description": "pytest test suite achieves >= 90% line coverage.", "priority": "high"},
    {"id": "AC-004", "description": "OpenAPI 3.1 schema validates against the openapi-spec-validator tool.", "priority": "high"},
    {"id": "AC-005", "description": "README contains a runnable curl example for every endpoint plus a sample JSON response.", "priority": "medium"}
  ],
  "constraints": [
    {"id": "C-001", "category": "technology", "hard": true, "description": "Implementation must use FastAPI and Pydantic v2."},
    {"id": "C-002", "category": "performance", "hard": false, "description": "Each endpoint responds in under 50ms with the in-memory store."},
    {"id": "C-003", "category": "budget", "hard": true, "description": "Total token usage capped at 25,000 tokens across the workflow."}
  ],
  "global_budget": {
    "max_total_tokens": 25000,
    "max_cost_usd": 1.00,
    "max_wall_seconds": 300,
    "max_concurrent_agents": 3
  }
}$JSON$::jsonb
    )
ON CONFLICT (id) DO NOTHING;

INSERT INTO workstreams
    (id, workflow_id, name, description, status, task_ids, created_at, updated_at)
VALUES
    ('demo-ws-main', 'demo', 'Books API',
     'Build a REST API for managing a book catalog with tests and documentation.',
     'completed',
     '["demo-t1", "demo-t2", "demo-t3"]'::jsonb,
     now() - interval '2 minutes', now() - interval '30 seconds')
ON CONFLICT (id) DO NOTHING;

INSERT INTO tasks
    (id, workstream_id, workflow_id, title, description,
     status, attempt, result, attempt_feedback, output,
     created_at, started_at, completed_at)
VALUES
    ('demo-t1', 'demo-ws-main', 'demo',
     'Design the API schema',
     'Define the book resource shape, field types, and CRUD endpoints.',
     'passed', 1,
     '{"verified": true, "score": 0.92, "feedback": "Schema covers required fields (id, title, author, isbn, publishedAt); RESTful routes /books and /books/{id}.", "output": "OpenAPI 3.1 schema with 5 routes; Book resource fully typed.", "token_usage": 2070, "wall_seconds": 20.4}'::jsonb,
     '[{"attempt": 1, "score": 0.92, "passed": true, "verifier_type": "llm_judge",
        "feedback": "Schema covers required fields (id, title, author, isbn, publishedAt); RESTful routes /books and /books/{id}.",
        "suggested_improvements": [],
        "test_results": [
          {"name": "covers required Book fields", "passed": true},
          {"name": "RESTful resource paths", "passed": true},
          {"name": "ISBN format documented", "passed": true}
        ]}]'::jsonb,
     'POST /books          — create a book' || chr(10) ||
     'GET  /books          — list books (?page, ?limit)' || chr(10) ||
     'GET  /books/{id}     — retrieve a book' || chr(10) ||
     'PUT  /books/{id}     — update a book' || chr(10) ||
     'DELETE /books/{id}   — delete a book' || chr(10) || chr(10) ||
     'Book { id: uuid, title: string, author: string, isbn: string, publishedAt: date }',
     now() - interval '2 minutes',
     now() - interval '110 seconds',
     now() - interval '90 seconds'),

    ('demo-t2', 'demo-ws-main', 'demo',
     'Implement CRUD endpoints with tests',
     'FastAPI implementation with pytest coverage >= 90%.',
     'passed', 1,
     '{"verified": true, "score": 0.88, "feedback": "All 5 endpoints implemented; 12 pytest cases pass; coverage 94%.", "output": "FastAPI app with 5 CRUD endpoints; pytest 12/12 pass; coverage 94%.", "token_usage": 6250, "wall_seconds": 34.8}'::jsonb,
     '[{"attempt": 1, "score": 0.88, "passed": true, "verifier_type": "test_runner",
        "feedback": "All 5 endpoints implemented; 12 pytest cases pass; coverage 94%.",
        "suggested_improvements": ["Add rate-limit tests", "Cover concurrent-write edge cases"],
        "test_results": [
          {"name": "POST /books creates and returns 201", "passed": true},
          {"name": "GET /books returns paginated list", "passed": true},
          {"name": "GET /books/{id} returns 404 for missing", "passed": true},
          {"name": "PUT /books/{id} updates fields", "passed": true},
          {"name": "DELETE /books/{id} returns 204", "passed": true},
          {"name": "coverage >= 90%", "passed": true}
        ]}]'::jsonb,
     '# app/main.py — 84 LOC' || chr(10) ||
     'from fastapi import FastAPI, HTTPException' || chr(10) ||
     '# Book model, in-memory store, 5 CRUD handlers' || chr(10) || chr(10) ||
     '# tests/test_books.py — 12 pytest cases, 94% coverage',
     now() - interval '90 seconds',
     now() - interval '80 seconds',
     now() - interval '45 seconds'),

    ('demo-t3', 'demo-ws-main', 'demo',
     'Write API documentation',
     'OpenAPI spec + README with curl examples.',
     'passed', 1,
     '{"verified": true, "score": 0.95, "feedback": "OpenAPI 3.1 spec auto-generated; README contains 5 runnable curl commands and response samples.", "output": "OpenAPI 3.1 spec generated; README with 5 curl examples and response samples.", "token_usage": 2060, "wall_seconds": 9.7}'::jsonb,
     '[{"attempt": 1, "score": 0.95, "passed": true, "verifier_type": "llm_judge",
        "feedback": "OpenAPI 3.1 spec auto-generated; README contains 5 runnable curl commands and response samples.",
        "suggested_improvements": [],
        "test_results": [
          {"name": "OpenAPI 3.1 schema validates", "passed": true},
          {"name": "README curl examples cover all 5 endpoints", "passed": true},
          {"name": "response samples included for each endpoint", "passed": true}
        ]}]'::jsonb,
     '## Books API' || chr(10) || chr(10) ||
     '### Create a book' || chr(10) ||
     'curl -X POST http://localhost:8000/books \' || chr(10) ||
     '  -H "Content-Type: application/json" \' || chr(10) ||
     '  -d ''{"title":"Foundation","author":"Asimov","isbn":"9780553293357"}''',
     now() - interval '45 seconds',
     now() - interval '40 seconds',
     now() - interval '30 seconds')
ON CONFLICT (id) DO NOTHING;

INSERT INTO task_dependencies (task_id, depends_on) VALUES
    ('demo-t2', 'demo-t1'),
    ('demo-t3', 'demo-t2')
ON CONFLICT DO NOTHING;

INSERT INTO workflow_usage
    (workflow_id, task_id, provider, model,
     input_tokens, output_tokens, cost_usd, source, created_at)
VALUES
    ('demo', NULL,       'anthropic', 'claude-sonnet-4',  450,  220, 0.005, 'planner',  now() - interval '115 seconds'),
    ('demo', 'demo-t1',  'anthropic', 'claude-sonnet-4', 1250,  420, 0.013, 'agent',    now() - interval '100 seconds'),
    ('demo', 'demo-t1',  'anthropic', 'claude-haiku-4',   300,  100, 0.001, 'verifier', now() - interval '85 seconds'),
    ('demo', 'demo-t2',  'anthropic', 'claude-sonnet-4', 3800, 1850, 0.041, 'agent',    now() - interval '60 seconds'),
    ('demo', 'demo-t2',  'anthropic', 'claude-haiku-4',   420,  180, 0.001, 'verifier', now() - interval '42 seconds'),
    ('demo', 'demo-t3',  'anthropic', 'claude-sonnet-4',  980,  680, 0.013, 'agent',    now() - interval '35 seconds'),
    ('demo', 'demo-t3',  'anthropic', 'claude-haiku-4',   280,  120, 0.001, 'verifier', now() - interval '27 seconds');

COMMIT;
