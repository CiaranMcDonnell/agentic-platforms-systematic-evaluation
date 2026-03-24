# Prompt

Add a `validate_email` function to `utils/validation.py` that validates email
addresses and returns a boolean.

Requirements:
1. Accept a single `email: str` parameter and return `bool`.
2. Use a regex pattern that covers standard RFC 5322 local-part and domain rules:
   - Local part: alphanumeric, dots, underscores, hyphens, plus signs.
   - Domain: at least two labels separated by dots, TLD at least 2 characters.
3. Handle edge cases gracefully — `None`, empty string, whitespace-only input,
   and non-string types should return `False` without raising.
4. Add type hints and a docstring.

Write the function and any necessary imports into `utils/validation.py`.

# Context

You are working in a Python project that has a `utils/` package. The file
`utils/validation.py` may or may not already exist. If it does not exist,
create it with the appropriate module docstring. If it already exists, add
the function without removing existing code.

The project uses Python 3.10+ and follows PEP 8 style conventions.
