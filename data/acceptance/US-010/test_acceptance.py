"""Hidden acceptance tests for US-010 (user profile endpoints).

Derived from data/gherkin/intermediate/US010_add_api_endpoint.feature.
Never shown to the agent; see data/acceptance/US-001 for the convention.
"""

PROFILE = "/api/users/{}/profile"


async def test_AC_010_1_get_returns_profile(client):
    response = await client.get(PROFILE.format(1))
    assert response.status_code == 200
    body = response.json()
    for key in ("display_name", "bio", "avatar_url"):
        assert key in body
    assert body["display_name"] == "Ada"


async def test_AC_010_2_get_unknown_user_returns_404(client):
    response = await client.get(PROFILE.format(999))
    assert response.status_code == 404
    assert "User not found" in response.text


async def test_AC_010_3_put_updates_profile(client):
    response = await client.put(
        PROFILE.format(1), json={"display_name": "New Name", "bio": "Updated bio"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "New Name"
    assert body["bio"] == "Updated bio"


async def test_AC_010_4_put_invalid_payload_returns_422(client):
    response = await client.put(
        PROFILE.format(1), json={"display_name": ["not", "a", "string"]}
    )
    assert response.status_code == 422
    assert "detail" in response.json()
