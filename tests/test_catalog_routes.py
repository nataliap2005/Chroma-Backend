from fastapi import FastAPI
from fastapi.testclient import TestClient
from catalog_routes import router

client = TestClient(FastAPI())
client.app.include_router(router)

def test_facets_have_products():
    response = client.get("/api/catalog/facets")
    assert response.status_code == 200
    assert response.json()["total"] == 688
    assert "Base" in response.json()["categories"]

def test_search_pagination_and_filter():
    response = client.get("/api/catalog/search", params={"category": "Base", "limit": 5, "offset": 0})
    assert response.status_code == 200
    data = response.json()
    assert len(data["products"]) == 5
    assert data["total"] >= 5
    assert all(p["categoria"] == "Base" for p in data["products"])

def test_rejects_bad_pagination():
    assert client.get("/api/catalog/search", params={"limit": 0}).status_code == 422
