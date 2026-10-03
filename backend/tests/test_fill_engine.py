from app.services.fill_engine import (
    CAP_FULL_REASON, build_fill_lines, compute_gap, summarize,
)

def test_gap_basic():
    assert compute_gap(20, 5, 0) == 15
    assert compute_gap(20, 10, 5) == 5

def test_no_negative_fill():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 10, "stock": 12, "in_transit": 0}]
    lines = build_fill_lines(lanes)
    assert lines[0].fill_qty == 0
    assert lines[0].status == "overbooked"

def test_cap_by_gap():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 20, "stock": 5, "in_transit": 0}]
    lines = build_fill_lines(lanes, requested={1: 100})
    assert lines[0].fill_qty == 15
    assert lines[0].gap == 15

def test_full_zero_fill():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 10, "stock": 8, "in_transit": 2}]
    s = summarize(build_fill_lines(lanes))
    assert s["full_count"] == 1
    assert s["total_fill"] == 0

def _chip_lanes():
    # 薯片: B1 gap=7, B3 gap=8 — same sku, two lanes
    return [
        {"id": 1, "slot_no": "B1", "sku_name": "薯片", "capacity": 12, "stock": 3, "in_transit": 2},
        {"id": 2, "slot_no": "B3", "sku_name": "薯片", "capacity": 10, "stock": 2, "in_transit": 0},
        {"id": 3, "slot_no": "A1", "sku_name": "矿泉水", "capacity": 20, "stock": 5, "in_transit": 0},
    ]

def test_sku_cap_below_first_gap():
    # cap 5 < B1 ideal gap 7: B1 fills exactly to cap, later same-sku lane zeroed
    lines = build_fill_lines(_chip_lanes(), sku_caps={"薯片": 5})
    by_slot = {l.slot_no: l for l in lines}
    assert by_slot["B1"].fill_qty == 5
    assert by_slot["B1"].status == "need_fill"
    assert by_slot["B1"].reason == ""
    assert by_slot["B3"].fill_qty == 0
    assert by_slot["B3"].status == "cap_full"
    assert by_slot["B3"].reason == CAP_FULL_REASON
    assert CAP_FULL_REASON == "同品合计已满"

def test_sku_cap_total_never_exceeds():
    lines = build_fill_lines(_chip_lanes(), sku_caps={"薯片": 5})
    chip_total = sum(l.fill_qty for l in lines if l.sku_name == "薯片")
    assert chip_total == 5
    assert summarize(lines)["total_fill"] == 5 + 15  # 薯片 5 + 矿泉水 15

def test_sku_cap_split_across_lanes_in_slot_order():
    # cap 10: B1 takes 7 first (slot order), B3 gets the remaining 3
    by_slot = {l.slot_no: l for l in build_fill_lines(_chip_lanes(), sku_caps={"薯片": 10})}
    assert by_slot["B1"].fill_qty == 7
    assert by_slot["B3"].fill_qty == 3
    assert by_slot["B3"].status == "need_fill"  # partially capped, still has gap

def test_sku_cap_ordering_regardless_of_input_order():
    lanes = list(reversed(_chip_lanes()))  # B3 before B1
    by_slot = {l.slot_no: l for l in build_fill_lines(lanes, sku_caps={"薯片": 5})}
    assert by_slot["B1"].fill_qty == 5
    assert by_slot["B3"].status == "cap_full"

def test_unregistered_sku_unconstrained():
    lines = build_fill_lines(_chip_lanes())  # no caps at all
    by_slot = {l.slot_no: l for l in lines}
    assert by_slot["B1"].fill_qty == 7
    assert by_slot["B3"].fill_qty == 8
    assert all(l.status != "cap_full" for l in lines)

def test_other_sku_cap_does_not_touch_sku():
    by_slot = {l.slot_no: l for l in build_fill_lines(_chip_lanes(), sku_caps={"矿泉水": 4})}
    assert by_slot["B1"].fill_qty == 7
    assert by_slot["B3"].fill_qty == 8

def test_full_lane_consumes_no_cap():
    lanes = [
        {"id": 1, "slot_no": "A2", "sku_name": "薯片", "capacity": 18, "stock": 18, "in_transit": 0},
        {"id": 2, "slot_no": "B1", "sku_name": "薯片", "capacity": 12, "stock": 3, "in_transit": 2},
    ]
    by_slot = {l.slot_no: l for l in build_fill_lines(lanes, sku_caps={"薯片": 5})}
    assert by_slot["A2"].status == "full"
    assert by_slot["A2"].reason == ""  # 单道满仓不得并句
    assert by_slot["B1"].fill_qty == 5

def test_nonpositive_cap_ignored_by_engine():
    # API rejects registration; engine itself must never treat <=0 as "fill zero"
    lines = build_fill_lines(_chip_lanes(), sku_caps={"薯片": 0})
    assert sum(l.fill_qty for l in lines if l.sku_name == "薯片") == 15
