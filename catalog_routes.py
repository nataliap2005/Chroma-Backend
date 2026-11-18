"""Rutas de búsqueda y filtros del catálogo (/api/catalog)."""
from fastapi import APIRouter, Query
from catalog_service import get_products, search_catalog, catalog_facets

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

@router.get("/search")
def search(q: str = "", category: str = "", brand: str = "",
           max_price: int | None = Query(None, ge=0),
           offset: int = Query(0, ge=0), limit: int = Query(24, ge=1, le=100)):
    return search_catalog(get_products(), q=q, category=category, brand=brand, max_price=max_price, offset=offset, limit=limit)

@router.get("/facets")
def facets():
    return catalog_facets(get_products())
