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
     created_at, completed_at)
VALUES
    ('demo', 'demo-spec-books-api', 'completed', 3, 3, 0,
     now() - interval '2 minutes', now() - interval '30 seconds')
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
     status, result, output, created_at, started_at, completed_at)
VALUES
    ('demo-t1', 'demo-ws-main', 'demo',
     'Design the API schema',
     'Define the book resource shape, field types, and CRUD endpoints.',
     'completed',
     '{"verified": true, "score": 0.92, "feedback": "Schema covers required fields (id, title, author, isbn, publishedAt); RESTful routes /books and /books/{id}."}'::jsonb,
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
     'completed',
     '{"verified": true, "score": 0.88, "feedback": "All 5 endpoints implemented; 12 pytest cases pass; coverage 94%."}'::jsonb,
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
     'completed',
     '{"verified": true, "score": 0.95, "feedback": "OpenAPI 3.1 spec auto-generated; README contains 5 runnable curl commands and response samples."}'::jsonb,
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
