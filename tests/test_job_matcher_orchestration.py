"""
End-to-end orchestration test for the job_matcher example spec.

Validates that the orchestrator can:
  - Load and validate the job_matcher spec
  - Plan a multi-agent workflow with concurrent independent services
  - Execute tasks producing standalone Python file artifacts
  - Respect dependency ordering (CV parser + scraper concurrent, scorer after parser)
  - Verify outputs via mixed strategies (test + llm_judge)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from rooben.agents.registry import AgentRegistry
from rooben.domain import TaskStatus, TokenUsage, WorkflowStatus
from rooben.orchestrator import Orchestrator
from rooben.planning.llm_planner import LLMPlanner
from rooben.planning.provider import GenerationResult
from rooben.spec.loader import load_spec
from rooben.state.filesystem import FilesystemBackend
from rooben.verification.llm_judge import LLMJudgeVerifier


def _gen_result(text: str) -> GenerationResult:
    return GenerationResult(
        text=text,
        usage=TokenUsage(input_tokens=100, output_tokens=50),
        model="mock-model",
        provider="mock",
    )


EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


class JobMatcherPlanProvider:
    """
    Mock LLM provider that returns a realistic plan for the job_matcher spec.

    Exercises:
      - 4 agents with different capabilities
      - Concurrent dispatch of CV parser + job scraper (independent services)
      - Sequential dependency: scorer depends on parser, pipeline depends on all
      - Artifact production: each task produces a standalone .py file
    """

    def __init__(self) -> None:
        self._calls: list[dict] = []

    async def generate(
        self, system: str, prompt: str, max_tokens: int = 4096
    ) -> GenerationResult:
        self._calls.append({"system": system, "prompt": prompt})

        if "planning engine" in system.lower():
            return _gen_result(self._plan_response())
        elif "autonomous agent executing" in system.lower():
            return _gen_result(self._agent_response(prompt))
        elif "quality assurance judge" in system.lower():
            return _gen_result(self._judge_response())
        return _gen_result('{"output": "ok"}')

    def _plan_response(self) -> str:
        return json.dumps({
            "workstreams": [
                {
                    "id": "ws-services",
                    "name": "Standalone Services",
                    "description": "Independent Python service modules",
                    "tasks": [
                        {
                            "id": "task-cv-parser",
                            "title": "Build CV parser service",
                            "description": "Create cv_parser.py with parse_cv() and CLI",
                            "assigned_agent_id": "llm-service-dev",
                            "depends_on": [],
                            "acceptance_criteria_ids": ["AC-001", "AC-002", "AC-003"],
                            "verification_strategy": "test",
                            "skeleton_tests": [],
                        },
                        {
                            "id": "task-job-scraper",
                            "title": "Build job scraper service",
                            "description": "Create job_scraper.py with Playwright search",
                            "assigned_agent_id": "browser-automation-dev",
                            "depends_on": [],
                            "acceptance_criteria_ids": ["AC-004", "AC-005", "AC-006"],
                            "verification_strategy": "test",
                            "skeleton_tests": [],
                        },
                    ],
                },
                {
                    "id": "ws-scoring",
                    "name": "Scoring Engine",
                    "description": "Job scoring against profile",
                    "tasks": [
                        {
                            "id": "task-job-scorer",
                            "title": "Build job scorer service",
                            "description": "Create job_scorer.py with LLM and keyword scoring",
                            "assigned_agent_id": "llm-service-dev",
                            "depends_on": ["task-cv-parser"],
                            "acceptance_criteria_ids": ["AC-007", "AC-008", "AC-009"],
                            "verification_strategy": "test",
                            "skeleton_tests": [],
                        },
                    ],
                },
                {
                    "id": "ws-integration",
                    "name": "Pipeline Integration",
                    "description": "CLI pipeline and documentation",
                    "tasks": [
                        {
                            "id": "task-pipeline",
                            "title": "Build pipeline CLI",
                            "description": "Create pipeline.py wiring all services",
                            "assigned_agent_id": "integration-dev",
                            "depends_on": [
                                "task-cv-parser",
                                "task-job-scraper",
                                "task-job-scorer",
                            ],
                            "acceptance_criteria_ids": ["AC-010", "AC-011"],
                            "verification_strategy": "test",
                            "skeleton_tests": [],
                        },
                        {
                            "id": "task-docs",
                            "title": "Create requirements and README",
                            "description": "Write requirements.txt and README.md",
                            "assigned_agent_id": "integration-dev",
                            "depends_on": [
                                "task-cv-parser",
                                "task-job-scraper",
                                "task-job-scorer",
                            ],
                            "acceptance_criteria_ids": ["AC-014"],
                            "verification_strategy": "llm_judge",
                            "skeleton_tests": [],
                        },
                    ],
                },
                {
                    "id": "ws-testing",
                    "name": "Test Suite",
                    "description": "Unit and integration tests",
                    "tasks": [
                        {
                            "id": "task-tests",
                            "title": "Write test suite",
                            "description": "Pytest tests for all services with mocks",
                            "assigned_agent_id": "test-engineer",
                            "depends_on": ["task-pipeline"],
                            "acceptance_criteria_ids": ["AC-012", "AC-013"],
                            "verification_strategy": "test",
                            "skeleton_tests": [],
                        },
                    ],
                },
            ]
        })

    def _agent_response(self, prompt: str) -> str:
        """Return realistic artifacts based on which task is being executed.

        Match on task title line ('# Task: ...') to avoid false matches from
        dependency output context included by ContextBuilder.
        """
        # Extract the task title line for reliable matching
        title_line = ""
        for line in prompt.lower().split("\n"):
            if line.startswith("# task:"):
                title_line = line
                break

        if "cv parser" in title_line or "cv_parser" in title_line:
            return json.dumps({
                "output": "Built cv_parser.py with parse_cv() and CLI",
                "artifacts": {
                    "cv_parser.py": CV_PARSER_ARTIFACT,
                },
                "generated_tests": [],
            })
        elif "scraper" in title_line:
            return json.dumps({
                "output": "Built job_scraper.py with Playwright search",
                "artifacts": {
                    "job_scraper.py": JOB_SCRAPER_ARTIFACT,
                },
                "generated_tests": [],
            })
        elif "scorer" in title_line:
            return json.dumps({
                "output": "Built job_scorer.py with LLM and keyword scoring",
                "artifacts": {
                    "job_scorer.py": JOB_SCORER_ARTIFACT,
                },
                "generated_tests": [],
            })
        elif "pipeline" in title_line:
            return json.dumps({
                "output": "Built pipeline.py CLI",
                "artifacts": {
                    "pipeline.py": PIPELINE_ARTIFACT,
                },
                "generated_tests": [],
            })
        else:
            return json.dumps({
                "output": "Task completed",
                "artifacts": {"output.txt": "# generated content"},
                "generated_tests": [],
            })

    def _judge_response(self) -> str:
        return json.dumps({
            "passed": True,
            "score": 0.9,
            "feedback": "Output meets requirements",
        })


# ---------------------------------------------------------------------------
# Realistic artifact stubs (abbreviated but structurally valid Python)
# ---------------------------------------------------------------------------

CV_PARSER_ARTIFACT = '''"""CV Parser — extracts structured profile from resume text or PDF."""
import json, os, sys
from pydantic import BaseModel, Field

class Skill(BaseModel):
    name: str
    level: str = "intermediate"
    years: int = 0

class Experience(BaseModel):
    title: str
    company: str
    start: str = ""
    end: str = ""
    description: str = ""

class Profile(BaseModel):
    name: str = ""
    email: str = ""
    skills: list[Skill] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    preferred_titles: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    summary: str = ""

async def parse_cv_text(text: str) -> Profile:
    """Parse plain text CV into structured Profile."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return await _parse_with_llm(text, api_key)
    return _parse_with_regex(text)

async def _parse_with_llm(text: str, api_key: str) -> Profile:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[{"role": "user", "content": f"Extract structured profile from CV:\\n{text}"}],
    )
    return Profile.model_validate_json(response.content[0].text)

def _parse_with_regex(text: str) -> Profile:
    import re
    skills = []
    for match in re.finditer(r"Skills?:\\s*(.+)", text, re.IGNORECASE):
        for s in match.group(1).split(","):
            skills.append(Skill(name=s.strip()))
    return Profile(skills=skills, summary=text[:200])

if __name__ == "__main__":
    import asyncio, argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("cv_path")
    parser.add_argument("--output", default="-")
    args = parser.parse_args()
    with open(args.cv_path) as f:
        text = f.read()
    profile = asyncio.run(parse_cv_text(text))
    out = profile.model_dump_json(indent=2)
    if args.output == "-":
        print(out)
    else:
        with open(args.output, "w") as f:
            f.write(out)
'''

JOB_SCRAPER_ARTIFACT = '''"""Job Scraper — searches for jobs using Playwright browser automation."""
import asyncio, json, os, random, sys
from pydantic import BaseModel, Field

class JobListing(BaseModel):
    title: str
    company: str = ""
    location: str = ""
    url: str = ""
    description: str = ""
    posted_date: str = ""
    salary_range: str = ""
    source: str = "google_jobs"

async def search_jobs(
    keywords: list[str],
    location: str = "",
    remote: bool = False,
    max_results: int = 20,
    headless: bool = True,
) -> list[JobListing]:
    """Search for jobs using Playwright."""
    from playwright.async_api import async_playwright
    query = " ".join(keywords)
    if location:
        query += f" {location}"
    if remote:
        query += " remote"

    jobs = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        search_url = f"https://www.google.com/search?q={query}+jobs&ibp=htl;jobs"
        await page.goto(search_url, timeout=30000)
        await asyncio.sleep(random.uniform(1, 3))

        cards = await page.query_selector_all("[class*=\\'job\\']")
        for card in cards[:max_results]:
            title_el = await card.query_selector("h2, h3, [class*=\\'title\\']")
            title = await title_el.inner_text() if title_el else "Unknown"
            jobs.append(JobListing(title=title, source="google_jobs"))
            await asyncio.sleep(random.uniform(1, 3))

        await browser.close()
    return jobs

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--keywords", required=True)
    parser.add_argument("--location", default="")
    parser.add_argument("--remote", action="store_true")
    parser.add_argument("--max", type=int, default=20)
    args = parser.parse_args()
    kw = [k.strip() for k in args.keywords.split(",")]
    results = asyncio.run(search_jobs(kw, args.location, args.remote, args.max))
    print(json.dumps([j.model_dump() for j in results], indent=2))
'''

JOB_SCORER_ARTIFACT = '''"""Job Scorer — ranks job postings against a professional profile."""
import json, os, sys
from pydantic import BaseModel, Field

class ScoredJob(BaseModel):
    title: str
    company: str = ""
    location: str = ""
    url: str = ""
    overall_score: float = 0
    skill_match: float = 0
    seniority_fit: float = 0
    industry_match: float = 0
    title_match: float = 0
    reasoning: str = ""

def score_jobs_keyword(profile: dict, jobs: list[dict]) -> list[ScoredJob]:
    """Keyword-based fallback scorer (no API key needed)."""
    profile_skills = {s["name"].lower() for s in profile.get("skills", [])}
    profile_titles = {t.lower() for t in profile.get("preferred_titles", [])}
    profile_industries = {i.lower() for i in profile.get("industries", [])}

    scored = []
    for job in jobs:
        desc = (job.get("description", "") + " " + job.get("title", "")).lower()
        skill_hits = sum(1 for s in profile_skills if s in desc)
        skill_match = min(100, (skill_hits / max(len(profile_skills), 1)) * 100)
        title_match = 100 if any(t in desc for t in profile_titles) else 30
        industry_match = 100 if any(i in desc for i in profile_industries) else 20
        overall = skill_match * 0.5 + title_match * 0.25 + industry_match * 0.25
        scored.append(ScoredJob(
            title=job.get("title", ""),
            company=job.get("company", ""),
            url=job.get("url", ""),
            overall_score=round(overall, 1),
            skill_match=round(skill_match, 1),
            title_match=round(title_match, 1),
            industry_match=round(industry_match, 1),
        ))
    scored.sort(key=lambda j: j.overall_score, reverse=True)
    return scored

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("profile_path")
    parser.add_argument("jobs_path")
    parser.add_argument("--output", default="-")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()
    with open(args.profile_path) as f:
        profile = json.load(f)
    with open(args.jobs_path) as f:
        jobs = json.load(f)
    scored = score_jobs_keyword(profile, jobs)[:args.top]
    out = json.dumps([s.model_dump() for s in scored], indent=2)
    if args.output == "-":
        print(out)
    else:
        with open(args.output, "w") as f:
            f.write(out)
'''

PIPELINE_ARTIFACT = '''"""Pipeline — wires CV parser, job scraper, and scorer into one CLI."""
import asyncio, json, sys
import click

def deduplicate_jobs(jobs: list[dict]) -> list[dict]:
    """Remove duplicate jobs by URL."""
    seen = set()
    unique = []
    for job in jobs:
        url = job.get("url", "")
        if url and url in seen:
            continue
        if url:
            seen.add(url)
        unique.append(job)
    return unique

@click.command()
@click.argument("cv_path")
@click.option("--location", default="", help="Job location filter")
@click.option("--remote", is_flag=True, help="Filter for remote jobs")
@click.option("--top", default=20, help="Number of top results to show")
@click.option("--output", type=click.Choice(["json", "table"]), default="table")
def main(cv_path, location, remote, top, output):
    """Find and rank jobs matching your CV."""
    asyncio.run(_run(cv_path, location, remote, top, output))

async def _run(cv_path, location, remote, top, output_format):
    from cv_parser import parse_cv_text
    from job_scraper import search_jobs
    from job_scorer import score_jobs_keyword

    with open(cv_path) as f:
        cv_text = f.read()

    profile = await parse_cv_text(cv_text)
    keywords = [s.name for s in profile.skills[:5]]
    jobs_raw = await search_jobs(keywords, location, remote)
    jobs_deduped = deduplicate_jobs([j.model_dump() for j in jobs_raw])
    scored = score_jobs_keyword(profile.model_dump(), jobs_deduped)[:top]

    if output_format == "json":
        click.echo(json.dumps([s.model_dump() for s in scored], indent=2))
    else:
        for i, job in enumerate(scored, 1):
            click.echo(f"{i:3d}. [{job.overall_score:5.1f}] {job.title} @ {job.company}")

if __name__ == "__main__":
    main()
'''


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestJobMatcherOrchestration:

    @pytest.mark.asyncio
    async def test_spec_loads_and_validates(self):
        """The job_matcher YAML loads into a valid Specification."""
        spec = load_spec(EXAMPLES_DIR / "job_matcher.yaml")
        assert spec.id == "spec-job-matcher"
        assert len(spec.deliverables) == 6
        assert len(spec.agents) == 4
        assert len(spec.success_criteria.acceptance_criteria) == 14
        assert spec.global_budget is not None

    @pytest.mark.asyncio
    async def test_full_orchestration_produces_artifacts(self):
        """Full run produces standalone Python file artifacts."""
        spec = load_spec(EXAMPLES_DIR / "job_matcher.yaml")
        provider = JobMatcherPlanProvider()

        with tempfile.TemporaryDirectory() as tmpdir:
            planner = LLMPlanner(provider=provider)
            registry = AgentRegistry(llm_provider=provider)
            for agent_spec in spec.agents:
                registry.register_mcp_agent(
                    agent_spec.id,
                    max_concurrency=agent_spec.max_concurrency,
                )
            backend = FilesystemBackend(base_dir=tmpdir)
            verifier = LLMJudgeVerifier(provider=provider)

            orchestrator = Orchestrator(
                planner=planner,
                agent_registry=registry,
                backend=backend,
                verifier=verifier,
                budget=spec.global_budget,
            )

            state = await orchestrator.run(spec)

            # All tasks should pass
            wf = list(state.workflows.values())[0]
            assert wf.status == WorkflowStatus.COMPLETED
            assert wf.failed_tasks == 0

            # Collect all artifacts produced across all tasks
            all_artifacts = {}
            for task in state.tasks.values():
                if task.result and task.result.artifacts:
                    all_artifacts.update(task.result.artifacts)

            # Verify standalone Python files were produced
            assert "cv_parser.py" in all_artifacts
            assert "job_scraper.py" in all_artifacts
            assert "job_scorer.py" in all_artifacts
            assert "pipeline.py" in all_artifacts

            # Verify artifacts contain expected patterns
            assert "parse_cv_text" in all_artifacts["cv_parser.py"]
            assert "playwright" in all_artifacts["job_scraper.py"].lower()
            assert "score_jobs_keyword" in all_artifacts["job_scorer.py"]
            assert "deduplicate_jobs" in all_artifacts["pipeline.py"]

            # Verify each artifact has a __main__ block
            for name in ("cv_parser.py", "job_scraper.py", "job_scorer.py", "pipeline.py"):
                assert '__name__' in all_artifacts[name], (
                    f"{name} missing __main__ block"
                )

    @pytest.mark.asyncio
    async def test_concurrent_service_dispatch(self):
        """CV parser and job scraper are dispatched concurrently."""
        spec = load_spec(EXAMPLES_DIR / "job_matcher.yaml")
        provider = JobMatcherPlanProvider()

        with tempfile.TemporaryDirectory() as tmpdir:
            planner = LLMPlanner(provider=provider)
            registry = AgentRegistry(llm_provider=provider)
            for agent_spec in spec.agents:
                registry.register_mcp_agent(
                    agent_spec.id,
                    max_concurrency=agent_spec.max_concurrency,
                )
            backend = FilesystemBackend(base_dir=tmpdir)
            verifier = LLMJudgeVerifier(provider=provider)

            orchestrator = Orchestrator(
                planner=planner,
                agent_registry=registry,
                backend=backend,
                verifier=verifier,
                budget=spec.global_budget,
            )

            state = await orchestrator.run(spec)

            # CV parser and scraper should both be PASSED and have no
            # dependencies on each other (task IDs have workflow suffix)
            from tests.helpers import find_task
            cv_task = find_task(state, "cv", "parser")
            scraper_task = find_task(state, "scraper")
            assert cv_task.status == TaskStatus.PASSED
            assert scraper_task.status == TaskStatus.PASSED
            assert cv_task.depends_on == []
            assert scraper_task.depends_on == []

            # They should be assigned to different agents
            assert cv_task.assigned_agent_id == "llm-service-dev"
            assert scraper_task.assigned_agent_id == "browser-automation-dev"

    @pytest.mark.asyncio
    async def test_dependency_chain_respected(self):
        """Scorer depends on parser, pipeline depends on all three."""
        spec = load_spec(EXAMPLES_DIR / "job_matcher.yaml")
        provider = JobMatcherPlanProvider()
        planner = LLMPlanner(provider=provider)

        state = await planner.plan(spec, "wf-test-deps")

        # Task IDs have workflow suffix — look up by title
        sfx = "wf-test-deps".split("-")[-1][:6]  # "deps"
        scorer = state.tasks[f"task-job-scorer-{sfx}"]
        pipeline = state.tasks[f"task-pipeline-{sfx}"]

        # Scorer depends on CV parser (needs Profile model)
        assert f"task-cv-parser-{sfx}" in scorer.depends_on

        # Pipeline depends on all three services
        assert f"task-cv-parser-{sfx}" in pipeline.depends_on
        assert f"task-job-scraper-{sfx}" in pipeline.depends_on
        assert f"task-job-scorer-{sfx}" in pipeline.depends_on

    @pytest.mark.asyncio
    async def test_agent_routing(self):
        """Tasks are routed to agents matching their capabilities."""
        spec = load_spec(EXAMPLES_DIR / "job_matcher.yaml")
        provider = JobMatcherPlanProvider()

        with tempfile.TemporaryDirectory() as tmpdir:
            planner = LLMPlanner(provider=provider)
            registry = AgentRegistry(llm_provider=provider)
            for agent_spec in spec.agents:
                registry.register_mcp_agent(
                    agent_spec.id,
                    max_concurrency=agent_spec.max_concurrency,
                )
            backend = FilesystemBackend(base_dir=tmpdir)
            verifier = LLMJudgeVerifier(provider=provider)

            orchestrator = Orchestrator(
                planner=planner,
                agent_registry=registry,
                backend=backend,
                verifier=verifier,
                budget=spec.global_budget,
            )

            state = await orchestrator.run(spec)

            # Task IDs have workflow suffix — look up by title
            from tests.helpers import find_task as _find_task

            def _find(keyword: str):
                return _find_task(state, keyword)

            # LLM services go to llm-service-dev
            assert _find("cv parser").assigned_agent_id == "llm-service-dev"
            assert _find("scorer").assigned_agent_id == "llm-service-dev"
            # Browser automation goes to browser-automation-dev
            assert _find("scraper").assigned_agent_id == "browser-automation-dev"
            # Integration goes to integration-dev
            assert _find("pipeline").assigned_agent_id == "integration-dev"
            # Tests go to test-engineer
            assert _find("test").assigned_agent_id == "test-engineer"
