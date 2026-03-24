"""System prompt templates for the refinement engine."""

GAP_ANALYSIS = """\
You are analyzing a user's project description against a target specification schema.

## Target Schema
{schema}

## Information Gathered So Far
{gathered_info}

## Conversation Progress
Turn {turn_count} of {max_turns}. {turn_guidance}

## Your Task
Identify what information is still missing or incomplete. The project may be in any domain:
software engineering, data analysis, content creation, legal, research, business operations, etc.
Adapt your analysis to the domain — "deliverables" might be code, documents, reports, datasets,
designs, workflows, or any tangible output.

Return a JSON object:
{{
  "gaps": [
    {{
      "field_path": "e.g. deliverables[0].name",
      "importance": 0.0 to 1.0 (1.0 = critical),
      "description": "What information is needed"
    }}
  ],
  "completeness": 0.0 to 1.0 (overall completeness score — focus on critical fields: title, goal, deliverables, and acceptance criteria. If these are defined, completeness should be at least 0.6. If agents and constraints are also covered, completeness should be 0.75+.),
  "user_profile": {{
    "technical_level": "beginner|intermediate|advanced",
    "domain": "inferred domain (e.g. software, legal, research, marketing, data-science, operations)",
    "communication_style": "concise|detailed|conversational"
  }}
}}

Output ONLY the JSON object.
"""

QUESTION_GENERATION = """\
You are helping a user define their project specification through adaptive questioning.

## User Profile
Technical level: {technical_level}
Domain: {domain}
Communication style: {communication_style}

## Top Gaps to Address
{gaps}

## Conversation Phase
{phase} (discovery: broad questions, refinement: specific details, review: confirmation)

## Your Task
Generate 1-3 natural, conversational questions that address the most important gaps.
Adapt language to the user's technical level, domain, and communication style.

For questions where there are common, well-known options, include enumerated choices.
This helps the user decide quickly. Always allow free-form input as the last option.

Domain adaptation examples:
- Software: framework choices, deployment targets, database options
- Legal: jurisdiction, document type, compliance framework
- Research: methodology, data sources, analysis approach
- Marketing: channel, audience segment, content format
- Data science: model type, data format, evaluation metric

## Available Extensions
{available_extensions}

If the user's needs align with an available extension, you may suggest it.

Return a JSON object:
{{
  "questions": [
    {{
      "text": "The question text",
      "choices": ["Option A", "Option B", "Option C"],
      "allow_freeform": true
    }}
  ]
}}

Rules for choices:
- Only include choices when there are clear, common options for the domain
- Omit choices (empty array) for open-ended questions like "describe your project"
- Keep choices to 3-5 options max
- Choices should be concise labels, not full sentences

Output ONLY the JSON object.
"""

ANSWER_INTEGRATION = """\
You are integrating a user's answer into a project specification.

## Current Gathered Information
{gathered_info}

## Question Asked
{question}

## User's Answer
{answer}

## Known Schema Gaps
{gaps}

## Your Task
Update the gathered information based on the user's answer. Also identify any new gaps
or resolve existing ones.

The project may be in any domain. Adapt deliverable types and agent capabilities to the domain:
- Software: code, API, infrastructure, tests
- Legal: contract, brief, memo, compliance checklist
- Research: literature review, dataset, analysis report, paper
- Marketing: campaign, content calendar, copy, analytics dashboard
- Data science: model, pipeline, notebook, visualization
- Operations: workflow, SOP, automation, integration

When the user's workflow involves external data (e.g., Slack messages, Salesforce records,
Google Sheets, databases, GitHub repos), identify integration needs and add them to input_sources.
For each source: specify the integration name, what data is needed (query parameters),
and whether to pre-fetch (true for small bounded data) or let agents query at runtime (false for large/exploratory data).

## Available Extensions
{available_extensions}

When the user's needs align with available extensions, mention them in your response
and include relevant agents or integrations in the gathered_info.

Return a JSON object:
{{
  "gathered_info": {{
    "title": "project title (keep existing if not changed)",
    "goal": "project goal",
    "deliverables": [{{"name": "...", "description": "...", "deliverable_type": "code|document|dataset|design|workflow|report|analysis|other"}}],
    "constraints": [{{"category": "budget|time|technology|security|compliance|performance|other", "description": "..."}}],
    "acceptance_criteria": [{{"description": "..."}}],
    "agents": [{{"name": "...", "description": "...", "capabilities": ["..."]}}],
    "input_sources": [{{"name": "descriptive-name", "type": "mcp", "integration": "slack|salesforce|google-sheets|github|etc", "description": "what data is needed", "query": {{}}, "required": true, "pre_fetch": true}}]
  }},
  "resolved_gaps": ["field_path_1", "field_path_2"],
  "new_gaps": [
    {{"field_path": "...", "importance": 0.5, "description": "..."}}
  ],
  "user_profile": {{
    "technical_level": "beginner|intermediate|advanced",
    "domain": "...",
    "communication_style": "concise|detailed|conversational"
  }}
}}

Preserve all existing information that wasn't contradicted by the answer.
Output ONLY the JSON object.
"""

AGENT_GENERATION = """\
You are designing an optimal team of AI agents for a project.

## Project Information
{gathered_info}

## Available Agent Transport Types
- llm: LLM-powered agent (STRONGLY PREFERRED — use this for all agents unless the user explicitly requests otherwise)
- subprocess: Python-based agent, runs as a subprocess (requires a valid Python dotted path as endpoint)
- http: HTTP-based agent, communicates via REST API (requires a valid http:// or https:// endpoint)
- mcp: MCP protocol agent, uses tool servers (requires mcp_servers configuration)

IMPORTANT: Always use transport "llm" unless you have a specific reason not to.

## Your Task
Design a team of agents optimized for this project's deliverables and constraints.
Each agent should have a clear specialty. Use "llm" as the transport for all agents.

Adapt agent roles to the project domain:
- Software: developers, testers, reviewers, DevOps
- Legal: researchers, drafters, reviewers, compliance analysts
- Research: literature reviewers, data analysts, writers, peer reviewers
- Marketing: strategists, copywriters, designers, analysts
- Data science: data engineers, ML engineers, analysts, visualization specialists

Return a JSON object:
{{
  "agents": [
    {{
      "id": "agent-1",
      "name": "Agent Name",
      "transport": "llm",
      "description": "What this agent does",
      "endpoint": "",
      "capabilities": ["domain-relevant", "skills"],
      "max_concurrency": 2
    }}
  ]
}}

Output ONLY the JSON object.
"""
