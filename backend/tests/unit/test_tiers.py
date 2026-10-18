from pathlib import Path

import pytest

from tests.conftest import TESTS, tier_of


@pytest.mark.parametrize("tier", ["unit", "integration", "contract"])
def test_tier_is_the_directory_under_tests(tier: str) -> None:
    assert tier_of(TESTS / tier / "test_x.py") == tier


def test_a_test_outside_the_tier_directories_is_an_error() -> None:
    with pytest.raises(pytest.UsageError, match="tests must live in"):
        tier_of(TESTS / "test_stray.py")


def test_this_file_is_a_unit_test(request: pytest.FixtureRequest) -> None:
    assert request.node.get_closest_marker("unit") is not None
    assert tier_of(Path(__file__)) == "unit"
