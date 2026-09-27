# test-writer

Adds tests to a workspace in the project's own framework and runs them when the runtime allows `execute`.

Tools: `list_files`, `read_file`, `search`, `write_file`, `execute`. In read-only mode (the public playground) the last two are stripped and the agent returns the test file content in its answer instead.

Config: `framework`, `test_dir`.
