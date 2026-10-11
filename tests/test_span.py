"""Multi-disc packing never slices a file and keeps 32 MB free."""

from stele.burn.span import plan_volumes, usable_bytes
from stele.models import HEADROOM_BYTES, SpanFile

DVD = 4_700_372_992


def test_overflow_makes_two_or_more_volumes_without_splitting():
    usable = usable_bytes(DVD)
    big = int(usable * 0.6)
    files = [SpanFile("a.bin", big), SpanFile("b.bin", big), SpanFile("c.bin", big)]
    plan = plan_volumes(files, DVD)
    assert plan.error is None
    assert len(plan.volumes) >= 2
    seen: list[str] = []
    for volume in plan.volumes:
        assert volume.used_bytes <= plan.usable_bytes
        for item in volume.files:
            assert item.size == big
            seen.append(item.path)
    assert sorted(seen) == ["a.bin", "b.bin", "c.bin"]


def test_headroom_is_respected():
    almost = DVD - (HEADROOM_BYTES // 2)
    plan = plan_volumes([SpanFile("rim.bin", almost)], DVD)
    assert plan.error
    assert "was not split" in plan.error


def test_oversized_file_is_refused():
    plan = plan_volumes([SpanFile("huge.gguf", DVD)], DVD)
    assert plan.error
    assert "huge.gguf" in plan.error
    assert "not split" in plan.error
    assert plan.volumes == []
