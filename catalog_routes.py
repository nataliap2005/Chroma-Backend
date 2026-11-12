"""Rutas opcionales de catálogo; agregar al FastAPI existente con include_router."""
from fastapi import APIRouter, Query
from catalog_service import load_catalog, search_catalog, catalog_facets

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

@router.get("/search")
def search(q: str = "", category: str = "", brand: str = "",
           max_price: int | None = Query(None, ge=0),
           offset: int = Query(0, ge=0), limit: int = Query(24, ge=1, le=100)):
    return search_catalog(load_catalog(), q=q, category=category, brand=brand, max_price=max_price, offset=offset, limit=limit)

@router.get("/facets")
def facets():
    return catalog_facets(load_catalog())
