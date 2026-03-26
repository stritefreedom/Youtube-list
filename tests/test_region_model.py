from models.region import Region


def test_region_defaults() -> None:
    region = Region(id="r1", bbox=(0, 0, 10, 10))
    assert region.text == ""
