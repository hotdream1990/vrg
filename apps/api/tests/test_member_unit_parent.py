"""Cây công ty MẸ-CON (member_unit.parent_company): gán/gỡ + các ràng buộc hợp lệ.

Không cho tự làm mẹ của chính mình, mẹ phải tồn tại, không cho vòng lặp 2 cấp
(A mẹ = B trong khi B mẹ = A). Xoá đơn vị mẹ phải gỡ liên kết các đơn vị con.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.services import member_unit_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

A, B, C = "_zz_par_a", "_zz_par_b", "_zz_par_c"


def _cleanup() -> None:
    with session_scope() as db:
        db.execute(text("UPDATE member_unit SET parent_company = NULL WHERE name = ANY(:u)"),
                   {"u": [A, B, C]})
        db.execute(text("DELETE FROM member_unit WHERE name = ANY(:u)"), {"u": [A, B, C]})


@pytest.fixture(autouse=True)
def _units():
    _cleanup()
    member_unit_repo.add_unit(A)
    member_unit_repo.add_unit(B)
    member_unit_repo.add_unit(C)
    yield
    _cleanup()


def test_set_parent_and_clear() -> None:
    member_unit_repo.set_parent(B, A)
    units = {u["name"]: u for u in member_unit_repo.list_units()}
    assert units[B]["parent_company"] == A
    assert A in member_unit_repo.parents()

    member_unit_repo.set_parent(B, None)
    units = {u["name"]: u for u in member_unit_repo.list_units()}
    assert units[B]["parent_company"] is None
    assert A not in member_unit_repo.parents()


def test_cannot_be_own_parent() -> None:
    with pytest.raises(ValueError):
        member_unit_repo.set_parent(A, A)


def test_parent_must_exist() -> None:
    with pytest.raises(ValueError):
        member_unit_repo.set_parent(A, "_zz_par_khong_ton_tai")


def test_rejects_two_level_cycle() -> None:
    member_unit_repo.set_parent(B, A)  # A là mẹ của B
    with pytest.raises(ValueError):
        member_unit_repo.set_parent(A, B)  # B lại làm mẹ của A → vòng lặp


def test_delete_parent_unlinks_children() -> None:
    member_unit_repo.set_parent(B, A)
    member_unit_repo.set_parent(C, A)
    assert member_unit_repo.delete_unit(A) is True
    units = {u["name"]: u for u in member_unit_repo.list_units()}
    assert units[B]["parent_company"] is None
    assert units[C]["parent_company"] is None
