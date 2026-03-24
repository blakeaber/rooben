"""LLM prompt templates for the extension builder engine."""

EXT_GAP_ANALYSIS = """\
You are analyzing a user's description to build a Rooben extension (integration, template, or agent).

## Extension Types
- **integration** (user-facing name: "Data Source"): Connects external services via MCP servers. \
Needs: servers config, required_env vars, cost_tier, domain_tags.
- **template**: A reusable workflow starting point. Needs: prefill text (workflow description), \
category (professional/builder/automator), domain_tags.
- **agent**: A specialized AI agent preset. Needs: capabilities, prompt_template, \
model_override (optional), integration (optional).

## Information Gathered So Far
{gathered_info}

## Conversation Progress
Turn {turn_count} of {max_turns}. {turn_guidance}

## Your Task
1. If type is not yet determined, detect the most likely type from the description.
2. Identify what information is still missing or incomplete for this extension type.
3. Score overall completeness.

Return a JSON object:
{{
  "detected_type": "integration|template|agent",
  "gaps": [
    {{
      "field_path": "e.g. servers, prefill, capabilities",
      "importance": 0.0 to 1.0,
      "description": "What information is needed"
    }}
  ],
  "completeness": 0.0 to 1.0
}}

Output ONLY the JSON object.
"""

EXT_QUESTION_GENERATION = """\
You are helping a user create a Rooben extension through adaptive questioning.

## Extension Type
{extension_type} (display name: {display_type})

## Top Gaps to Address
{gaps}

## Conversation Phase
{phase}

## Your Task
Generate 1-3 natural questions that address the most important gaps for this extension type.

Type-specific question guidance:
- **Data Source (integration)**: Ask about the service to connect, authentication method, \
what data to access, read-only vs read-write.
- **Template**: Ask about the workflow goal, output format, target audience, \
category (professional work, building software, automation).
- **Agent**: Ask about the agent's role, what capabilities it needs, \
which integration it works with, any model preferences.

Return a JSON object:
{{
  "questions": [
    {{
      "text": "The question text",
      "choices": ["Option A", "Option B"],
      "allow_freeform": true
    }}
  ]
}}

Output ONLY the JSON object.
"""

EXT_ANSWER_INTEGRATION = """\
You are integrating a user's answer into an extension specification.

## Extension Type
{extension_type}

## Current Gathered Information
{gathered_info}

## Question Asked
{question}

## User's Answer
{answer}

## Known Gaps
{gaps}

## Your Task
Update the gathered information based on the answer. For integrations, generate \
server configurations with appropriate npx packages, env vars, and transport types.

Return a JSON object:
{{
  "gathered_info": {{
    "name": "kebab-case-name",
    "type": "{extension_type}",
    "description": "...",
    "tags": ["..."],
    "domain_tags": ["..."],
    "category": "professional|builder|automator",
    "use_cases": ["..."],
    "servers": [{{
      "name": "server-name",
      "transport_type": "stdio",
      "command": "npx",
      "args": ["-y", "package-name"],
      "env": {{"KEY": "${{KEY}}"}}
    }}],
    "required_env": [{{"name": "KEY", "description": "...", "link": ""}}],
    "cost_tier": 2,
    "prefill": "workflow description text",
    "requires": [],
    "capabilities": ["..."],
    "prompt_template": "...",
    "model_override": "",
    "integration": ""
  }},
  "resolved_gaps": ["field_path_1"],
  "new_gaps": [
    {{"field_path": "...", "importance": 0.5, "description": "..."}}
  ]
}}

Preserve all existing information that wasn't contradicted. Output ONLY the JSON object.
"""
