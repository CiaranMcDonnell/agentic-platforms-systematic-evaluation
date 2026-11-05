"""Hidden acceptance tests for US-001 (email validation utility).

Derived from data/gherkin/basic/US001_add_utility_function.feature.  Never
shown to the agent: the harness copies this directory into the archived
workspace after the pipeline finishes.  Test names start with the
acceptance-criterion id (``test_AC_001_2_...``) so results map back to
StoryResult.criteria_results.
"""

import inspect
import typing

import pytest

from utils.validation import validate_email


def _mentions(annotation, target: type) -> bool:
    """True if *annotation* is *target* or a union/optional containing it."""
    if annotation is target:
        return True
    return target in typing.get_args(annotation)


def test_AC_001_1_signature_and_type_hints():
    params = list(inspect.signature(validate_email).parameters.values())
    assert len(params) == 1
    hints = typing.get_type_hints(validate_email)
    assert _mentions(hints.get(params[0].name), str)
    assert hints.get("return") is bool


@pytest.mark.parametrize(
    "email",
    ["user@example.com", "user.name+tag@domain.co.uk", "user_name@sub.domain.org"],
)
def test_AC_001_2_valid_emails_return_true(email):
    assert validate_email(email) is True


@pytest.mark.parametrize(
    "email",
    ["not-an-email", "@missing-local.com", "user@", "user@.com", "user@domain"],
)
def test_AC_001_3_invalid_emails_return_false(email):
    assert validate_email(email) is False


@pytest.mark.parametrize("value", ["", None, "   ", 42, ["a@b.com"]])
def test_AC_001_4_edge_cases_return_false(value):
    assert validate_email(value) is False
