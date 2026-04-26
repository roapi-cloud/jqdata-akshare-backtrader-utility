Append this after the shared dispatch header.

Goal:
Create templates for handoff between research, implementation, and review agents.

Write scope:
1. `jq_workbench/governance/prompt_templates/research_handoff_template.md`
2. `jq_workbench/governance/prompt_templates/implementation_handoff_template.md`
3. `jq_workbench/governance/prompt_templates/review_handoff_template.md`

Inputs:
1. `jq_workbench/governance/standards/agent_prompt_style_guide.md`
2. `jq_workbench/governance/prompt_templates/shared_dispatch_header.md`

Work:
1. create three handoff templates with explicit inputs, outputs, and blocked-on fields

Do not:
1. change shared header
2. redefine prompt style guide rules

Done when:
1. a team can pass work between agent types with low ambiguity
