"""Vending refill engine.

Per-lane ideal fill = gap = capacity - stock - in_transit, capped by gap.
A location may register a per-SKU aggregate fill cap (同品合计补量上限):
lanes of the same sku_name accumulate ideal fills in slot_no order; once the
cap is reached, later lanes get fill_qty 0 with reason 同品合计已满.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

CAP_FULL_REASON = "同品合计已满"


@dataclass
class FillLine:
    lane_id: int
    slot_no: str
    sku_name: str
    capacity: int
    stock: int
    in_transit: int
    gap: int
    fill_qty: int
    status: str  # need_fill | full | overbooked | cap_full
    reason: str = ""


def compute_gap(capacity: int, stock: int, in_transit: int) -> int:
    return capacity - stock - in_transit


def build_fill_lines(
    lanes: list[dict],
    requested: dict[int, int] | None = None,
    sku_caps: dict[str, int] | None = None,
) -> list[FillLine]:
    """requested optional desired fill per lane_id; capped by gap; never negative.

    sku_caps maps sku_name to a positive aggregate fill cap for this location.
    Skus without a registered cap are not constrained.
    """
    lines: list[FillLine] = []
    for lane in lanes:
        gap = compute_gap(int(lane["capacity"]), int(lane["stock"]), int(lane["in_transit"]))
        if gap < 0:
            status = "overbooked"
            fill = 0
        elif gap == 0:
            status = "full"
            fill = 0
        else:
            status = "need_fill"
            desire = gap if requested is None else int(requested.get(lane["id"], gap))
            fill = max(0, min(desire, gap))
        lines.append(FillLine(
            lane_id=lane["id"], slot_no=lane["slot_no"], sku_name=lane["sku_name"],
            capacity=lane["capacity"], stock=lane["stock"], in_transit=lane["in_transit"],
            gap=gap, fill_qty=fill, status=status,
        ))
    apply_sku_caps(lines, sku_caps or {})
    return lines


def apply_sku_caps(lines: list[FillLine], sku_caps: dict[str, int]) -> None:
    """Truncate same-sku fills against one shared cap, slot_no order.

    A lane only consumes cap while it still needs fill (gap > 0); full and
    overbooked lanes keep their own status and consume nothing.
    """
    for sku_name, raw_cap in sku_caps.items():
        if raw_cap is None:
            continue
        cap = int(raw_cap)
        if cap <= 0:  # registration rejects <=0; never treat as "fill nothing"
            continue
        remaining = cap
        ordered = sorted(
            (l for l in lines if l.sku_name == sku_name),
            key=lambda l: l.slot_no,
        )
        for line in ordered:
            if line.status != "need_fill":
                continue
            ideal = line.fill_qty
            if remaining <= 0:
                line.fill_qty = 0
                line.status = "cap_full"
                line.reason = CAP_FULL_REASON
                continue
            alloc = min(ideal, remaining)
            remaining -= alloc
            line.fill_qty = alloc
            # A partially capped lane still receives goods and keeps an
            # unmet gap; only the lanes zeroed by the cap carry the reason.


def summarize(lines: list[FillLine]) -> dict:
    return {
        "total_fill": sum(l.fill_qty for l in lines),
        "need_fill_count": sum(1 for l in lines if l.status == "need_fill"),
        "full_count": sum(1 for l in lines if l.status == "full"),
        "overbooked_count": sum(1 for l in lines if l.status == "overbooked"),
        "cap_full_count": sum(1 for l in lines if l.status == "cap_full"),
        "lines": [asdict(l) for l in lines],
    }
