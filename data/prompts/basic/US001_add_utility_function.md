# Prompt

Add a `validate_email(email: str) -> bool` function to `utils/validation.py`.

Requirements:
- Use regex to validate email format
- Handle edge cases (empty string, None, whitespace)
- Return True for valid emails, False otherwise
- Add type hints and a docstring
- Valid format: local@domain.tld where local allows alphanumeric, dots,
  hyphens, underscores; domain allows alphanumeric and hyphens; TLD is 2-10 chars

# Context

The project uses Python 3.11+ with type hints throughout.
The utils/ directory already exists with an __init__.py.
Follow existing code style (Google-style docstrings, snake_case).
