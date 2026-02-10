import re


def validate_email(email: str) -> bool:
    """
    Validate the format of an email address.

    Args:
        email (str): The email address to validate.

    Returns:
        bool: True if the email is valid, False otherwise.
    """
    if email is None:
        return False

    email = email.strip()
    if not email:
        return False

    # Define a regex pattern for validating an email
    pattern = r'^[\w.-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,10}$'
    return re.match(pattern, email) is not None
