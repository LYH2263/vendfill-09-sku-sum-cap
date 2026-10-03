import os
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Lane, Location, SkuFillCap


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(session):
    def _get_db():
        try:
            yield session
        finally:
            pass
    app.dependency_overrides[get_db] = _get_db
    # No `with`: lifespan (and its seed) does not run against this client.
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def chip_location(session):
    loc = Location(code="VM-T", name="测试点位", address="测试地址")
    session.add(loc); session.flush()
    for slot, sku, cap, stock, transit in [
        ("B1", "薯片", 12, 3, 2),   # gap 7
        ("B3", "薯片", 10, 2, 0),   # gap 8
        ("A2", "可乐", 18, 18, 0),  # full, gap 0
    ]:
        session.add(Lane(location_id=loc.id, slot_no=slot, sku_name=sku,
                         capacity=cap, stock=stock, in_transit=transit))
    session.commit()
    return loc.id


def test_nonpositive_cap_rejected_leaves_config_unchanged(client, chip_location):
    for bad in (0, -1, -99):
        r = client.put("/api/sku-caps", json={"location_id": chip_location,
                                              "sku_name": "可乐", "cap_qty": bad})
        assert r.status_code == 400
    assert client.get(f"/api/sku-caps?location_id={chip_location}").json() == []


def test_cap_end_to_end_run_and_summary(client, chip_location):
    r = client.put("/api/sku-caps", json={"location_id": chip_location,
                                          "sku_name": "薯片", "cap_qty": 5})
    assert r.status_code == 200
    run = client.post(f"/api/refills/run?location_id={chip_location}").json()
    by_slot = {l["slot_no"]: l for l in run["lines"]}
    assert by_slot["B1"]["fill_qty"] == 5
    assert by_slot["B3"]["fill_qty"] == 0
    assert by_slot["B3"]["status"] == "cap_full"
    assert by_slot["B3"]["reason"] == "同品合计已满"
    assert by_slot["A2"]["status"] == "full" and by_slot["A2"]["reason"] == ""
    assert sum(l["fill_qty"] for l in run["lines"]) == run["total_fill"] == 5
    # summary total matches the capped receipt
    s = client.get(f"/api/refills/summary?location_id={chip_location}").json()
    assert s["total_fill"] == 5
    assert s["cap_full_count"] == 1
    # /full only contains single-lane full rows, never the cap-zeroed one
    full = client.get(f"/api/refills/full?location_id={chip_location}").json()["lanes"]
    assert [l["slot_no"] for l in full] == ["A2"]
    # lanes list uses the same truncation
    lanes = client.get(f"/api/lanes?location_id={chip_location}").json()
    lb = {l["slot_no"]: l for l in lanes}
    assert lb["B3"]["fill_qty"] == 0 and lb["B3"]["reason"] == "同品合计已满"
    assert lb["B1"]["fill_qty"] == 5


def test_change_cap_regenerates_against_new_cap(client, chip_location):
    client.put("/api/sku-caps", json={"location_id": chip_location,
                                      "sku_name": "薯片", "cap_qty": 5})
    first = client.post(f"/api/refills/run?location_id={chip_location}").json()
    assert first["total_fill"] == 5  # old order stored with old cap
    # raise cap: next run follows the new aggregate, no stale over-restriction
    client.put("/api/sku-caps", json={"location_id": chip_location,
                                      "sku_name": "薯片", "cap_qty": 20})
    run = client.post(f"/api/refills/run?location_id={chip_location}").json()
    by_slot = {l["slot_no"]: l for l in run["lines"]}
    assert by_slot["B1"]["fill_qty"] == 7
    assert by_slot["B3"]["fill_qty"] == 8
    assert run["total_fill"] == 15
    # lower it again: must not over-issue against any stale larger cap
    client.put("/api/sku-caps", json={"location_id": chip_location,
                                      "sku_name": "薯片", "cap_qty": 3})
    run = client.post(f"/api/refills/run?location_id={chip_location}").json()
    assert run["total_fill"] == 3
    by_slot = {l["slot_no"]: l for l in run["lines"]}
    assert by_slot["B1"]["fill_qty"] == 3 and by_slot["B3"]["fill_qty"] == 0


def test_cap_persists_and_unregistered_sku_free(client, session, chip_location):
    client.put("/api/sku-caps", json={"location_id": chip_location,
                                      "sku_name": "薯片", "cap_qty": 5})
    rows = session.query(SkuFillCap).filter_by(location_id=chip_location).all()
    assert len(rows) == 1 and rows[0].cap_qty == 5
    run = client.post(f"/api/refills/run?location_id={chip_location}").json()
    by_slot = {l["slot_no"]: l for l in run["lines"]}
    assert by_slot["A2"]["fill_qty"] == 0  # gap 0, untouched by cap machinery


def test_delete_cap_releases_constraint(client, chip_location):
    client.put("/api/sku-caps", json={"location_id": chip_location,
                                      "sku_name": "薯片", "cap_qty": 5})
    r = client.delete(f"/api/sku-caps?location_id={chip_location}&sku_name=薯片")
    assert r.status_code == 200
    run = client.post(f"/api/refills/run?location_id={chip_location}").json()
    assert run["total_fill"] == 15  # 7 + 8 again
