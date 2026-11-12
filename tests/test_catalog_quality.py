import csv
from pathlib import Path
from scripts.audit_catalog import audit

ROOT = Path(__file__).resolve().parents[1]

def test_catalog_ids_and_core_fields_are_valid():
    with (ROOT / "data" / "productos_mvp.csv").open(encoding="utf-8-sig", newline="") as f:
        report = audit(list(csv.DictReader(f)))
    assert report["total"] == 688
    assert report["duplicate_ids"] == []
    assert report["missing_id_count"] == 0
    assert report["required_fields_missing"] == 0
    assert report["invalid_hex_ids"] == []
    assert report["invalid_price_ids"] == []
