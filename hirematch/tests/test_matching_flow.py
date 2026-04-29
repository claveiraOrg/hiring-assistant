"""Happy-path tests for the core matching flow."""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

API_KEY = "dev-api-key"
HEADERS = {"X-API-Key": API_KEY}


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "hirematch"}


@pytest.mark.asyncio
async def test_create_candidate(client: AsyncClient):
    fake_profile = {"skills": ["Python", "FastAPI"], "years_experience": 5, "summary": "Senior dev"}

    with patch(
        "src.api.v1.candidates.parse_resume", new_callable=AsyncMock, return_value=fake_profile
    ):
        resp = await client.post(
            "/candidates",
            json={"name": "Alice Smith", "email": "alice@example.com", "resume_text": "Alice has 5 years..."},
            headers=HEADERS,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Alice Smith"
    assert data["email"] == "alice@example.com"
    assert data["structured_profile"] == fake_profile
    return data["id"]


@pytest.mark.asyncio
async def test_create_job(client: AsyncClient):
    resp = await client.post(
        "/jobs",
        json={"title": "Senior Python Engineer", "description": "We need a FastAPI expert."},
        headers=HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Senior Python Engineer"
    assert data["status"] == "active"
    return data["id"]


@pytest.mark.asyncio
async def test_full_matching_flow(client: AsyncClient):
    """Happy path: create job + candidate, trigger match, retrieve ranked results."""
    fake_profile = {"skills": ["Python"], "years_experience": 3}
    fake_score = {"score": 82, "reasoning": "Good Python fit", "evidence": {"strengths": ["Python"], "gaps": []}, "model": "claude-sonnet-4-6"}

    # 1. Create candidate
    with patch("src.api.v1.candidates.parse_resume", new_callable=AsyncMock, return_value=fake_profile):
        cand_resp = await client.post(
            "/candidates",
            json={"name": "Bob Dev", "email": "bob@example.com", "resume_text": "Bob knows Python"},
            headers=HEADERS,
        )
    assert cand_resp.status_code == 201
    candidate_id = cand_resp.json()["id"]

    # 2. Create job
    job_resp = await client.post(
        "/jobs",
        json={"title": "Python Dev", "description": "Looking for Python developers"},
        headers=HEADERS,
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    # 3. Trigger match
    with patch("src.api.v1.matches.score_candidate", new_callable=AsyncMock, return_value=fake_score):
        match_resp = await client.post(
            "/match",
            json={"job_id": job_id, "candidate_ids": [candidate_id]},
            headers=HEADERS,
        )
    assert match_resp.status_code == 200
    match_data = match_resp.json()
    assert match_data["job_id"] == job_id
    assert len(match_data["results"]) == 1
    assert match_data["results"][0]["score"] == 82
    assert match_data["results"][0]["candidate_id"] == candidate_id

    # 4. Retrieve ranked candidates
    ranked_resp = await client.get(f"/matches/{job_id}", headers=HEADERS)
    assert ranked_resp.status_code == 200
    ranked_data = ranked_resp.json()
    assert ranked_data["job_id"] == job_id
    assert len(ranked_data["candidates"]) == 1
    assert ranked_data["candidates"][0]["score"] == 82
    assert ranked_data["candidates"][0]["name"] == "Bob Dev"


@pytest.mark.asyncio
async def test_unauthorized_without_api_key(client: AsyncClient):
    resp = await client.post("/candidates", json={"resume_text": "test"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_match_nonexistent_job(client: AsyncClient):
    import uuid
    resp = await client.post(
        "/match",
        json={"job_id": str(uuid.uuid4()), "candidate_ids": []},
        headers=HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_matches_empty(client: AsyncClient):
    job_resp = await client.post(
        "/jobs",
        json={"title": "Empty Job", "description": "No candidates yet"},
        headers=HEADERS,
    )
    job_id = job_resp.json()["id"]
    resp = await client.get(f"/matches/{job_id}", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["candidates"] == []
