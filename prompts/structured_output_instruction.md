---
name: structured_output_instruction
version: 2
description: Instruction added to the system prompt when the backend cannot enforce a JSON schema itself.
---
Respond only with a valid JSON object that conforms to the JSON schema below. No text before or after, no code block, no explanation.

Expected JSON schema:
{{ schema_json }}
