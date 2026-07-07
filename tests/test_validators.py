import pytest

from framebatch.core.validators import validate_frame_user_index


def test_validate_frame_user_index_accepts_positive_integer() -> None:
    assert validate_frame_user_index(1) == 1
    assert validate_frame_user_index(25) == 25


def test_validate_frame_user_index_rejects_zero() -> None:
    with pytest.raises(ValueError):
        validate_frame_user_index(0)


def test_validate_frame_user_index_rejects_non_integer() -> None:
    with pytest.raises(TypeError):
        validate_frame_user_index("25")  # type: ignore[arg-type]
