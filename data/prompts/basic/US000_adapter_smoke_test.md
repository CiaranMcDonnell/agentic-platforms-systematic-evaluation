# Prompt

Create a file `hello.py` at the workspace root containing a single function:

```python
def hello() -> str:
    return "Hello, world!"
```

That's the entire task. Write the file and stop.

# Context

You are working in an empty Python project. The workspace root does not yet
contain `hello.py`. Create it with exactly the function shown above.

This is a smoke test — no regex, no edge cases, no imports, no existing code
to integrate with. If you find yourself running more than 3 tool calls, you
are overthinking it. Write the file and call check_completion.
