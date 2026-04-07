# Prompt

A trivial utility module `hello.py` is needed at the workspace root. It
should expose a single parameterless function `hello()` that returns the
literal string `"Hello, world!"`.

Requirements:

1. Module path: `hello.py` (workspace root)
2. Function signature: `def hello() -> str`
3. Return value: the string `"Hello, world!"` exactly
4. No arguments, no dependencies, no error handling, no edge cases

# Context

This story is the DESMET adapter smoke test. Its purpose is to run the
full SDLC pipeline (requirements → codegen → testing → deploy) on the
smallest possible task so a newly added adapter can be verified end-to-end
in seconds. Produce whatever your current stage expects — do NOT jump
ahead to producing source code during the requirements stage.
