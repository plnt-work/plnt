# code-reviewer

Reviews a workspace for bugs, security issues or style and reports findings with `path:line` citations.

Tools: `list_files`, `read_file`, `search` (read-only). The runtime enforces that the agent read at least one file before it answers (`require_tool = "read_file"`).

Config: `focus` (bugs | security | style | all), `max_findings`, `language_hint`.
