"""Smoke tests for the ingredients endpoint (verifies BE-002 is wired up)."""

import pytest


@pytest.mark.asyncio
async def test_list_ingredients_requires_auth(client):
    """GET /api/ingredients/ without token must return 403."""
    ac, _ = client

    resp = await ac.get("/api/ingredients/")
    # HTTPBearer with auto_error=False returns 403 when no credentials
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_ingredients_with_staff_token(client, staff_token, mock_staff_user):
    """GET /api/ingredients/ with a valid staff JWT must return 200 and a list."""
    ac, mock_db = client

    # The auth middleware will call db.user.find_unique to resolve the token subject.
    mock_db.user.find_unique.return_value = mock_staff_user
    mock_db.ingredient.find_many.return_value = []
    mock_db.ingredient.count.return_value = 0

    resp = await ac.get(
        "/api/ingredients/",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)
