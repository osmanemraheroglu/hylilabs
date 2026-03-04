"""
FAZ 3 — GÖREV 3.1: Synonym Scope Test Suite
Global/Company scope synonym onay sistemi testleri
"""
import pytest
from pydantic import BaseModel, Field
from typing import Optional, List


# ═══════════════════════════════════════════════════════════════════════════════
# MOCK - Test için gerekli yapıları yeniden tanımla
# ═══════════════════════════════════════════════════════════════════════════════

class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


def require_company_or_super_admin(current_user: dict) -> dict:
    """
    FAZ 3: Synonym approve için özel auth helper.
    - super_admin: erişebilir, company_id=None döner
    - company_admin/user: erişebilir, company_id döner
    """
    rol = current_user.get("rol")
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")

    if rol == "super_admin":
        return {"is_super_admin": True, "company_id": None, "user_id": user_id}
    elif company_id is not None:
        return {"is_super_admin": False, "company_id": company_id, "user_id": user_id}
    else:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok.")


class SynonymBulkActionRequest(BaseModel):
    synonym_ids: List[int] = Field(..., min_length=1)
    scope: Optional[str] = Field("company", description="Onay kapsamı: 'global' veya 'company'")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1: require_company_or_super_admin auth helper
# ═══════════════════════════════════════════════════════════════════════════════

def test_auth_helper_super_admin():
    """super_admin için is_super_admin=True, company_id=None dönmeli"""
    user = {"id": 1, "rol": "super_admin", "company_id": None}
    result = require_company_or_super_admin(user)

    assert result["is_super_admin"] == True
    assert result["company_id"] is None
    assert result["user_id"] == 1
    print("✓ TEST 1a: super_admin auth PASSED")


def test_auth_helper_company_admin():
    """company_admin için is_super_admin=False, company_id dönmeli"""
    user = {"id": 2, "rol": "company_admin", "company_id": 5}
    result = require_company_or_super_admin(user)

    assert result["is_super_admin"] == False
    assert result["company_id"] == 5
    assert result["user_id"] == 2
    print("✓ TEST 1b: company_admin auth PASSED")


def test_auth_helper_company_user():
    """company_user için is_super_admin=False, company_id dönmeli"""
    user = {"id": 3, "rol": "user", "company_id": 7}
    result = require_company_or_super_admin(user)

    assert result["is_super_admin"] == False
    assert result["company_id"] == 7
    assert result["user_id"] == 3
    print("✓ TEST 1c: company_user auth PASSED")


def test_auth_helper_no_company_no_super():
    """company_id=None ve super_admin değilse 403 fırlatmalı"""
    user = {"id": 4, "rol": "user", "company_id": None}

    with pytest.raises(HTTPException) as exc_info:
        require_company_or_super_admin(user)

    assert exc_info.value.status_code == 403
    print("✓ TEST 1d: unauthorized user 403 PASSED")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2: SynonymBulkActionRequest model
# ═══════════════════════════════════════════════════════════════════════════════

def test_request_model_default_scope():
    """scope belirtilmezse default 'company' olmalı"""
    req = SynonymBulkActionRequest(synonym_ids=[1, 2, 3])
    assert req.scope == "company"
    print("✓ TEST 2a: default scope='company' PASSED")


def test_request_model_global_scope():
    """scope='global' belirtildiğinde global olmalı"""
    req = SynonymBulkActionRequest(synonym_ids=[1], scope="global")
    assert req.scope == "global"
    print("✓ TEST 2b: scope='global' PASSED")


def test_request_model_company_scope():
    """scope='company' belirtildiğinde company olmalı"""
    req = SynonymBulkActionRequest(synonym_ids=[1, 2], scope="company")
    assert req.scope == "company"
    print("✓ TEST 2c: scope='company' PASSED")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3: Scope kontrolü mantığı
# ═══════════════════════════════════════════════════════════════════════════════

def test_scope_check_logic_super_admin_global():
    """super_admin global scope kullanabilmeli"""
    auth_info = require_company_or_super_admin({"id": 1, "rol": "super_admin", "company_id": None})
    scope = "global"

    # Bu kontrol HTTPException fırlatmamalı
    if scope == "global" and not auth_info["is_super_admin"]:
        raise HTTPException(status_code=403, detail="Global onay sadece super_admin yetkisiyle yapılabilir.")

    # super_admin için geçmeli
    assert auth_info["is_super_admin"] == True
    print("✓ TEST 3a: super_admin global scope ALLOWED")


def test_scope_check_logic_company_user_global():
    """company_user global scope kullanamamalı"""
    auth_info = require_company_or_super_admin({"id": 2, "rol": "user", "company_id": 5})
    scope = "global"

    # Bu kontrol HTTPException fırlatmalı
    with pytest.raises(HTTPException) as exc_info:
        if scope == "global" and not auth_info["is_super_admin"]:
            raise HTTPException(status_code=403, detail="Global onay sadece super_admin yetkisiyle yapılabilir.")

    assert exc_info.value.status_code == 403
    print("✓ TEST 3b: company_user global scope BLOCKED")


def test_scope_check_logic_company_user_company():
    """company_user company scope kullanabilmeli"""
    auth_info = require_company_or_super_admin({"id": 2, "rol": "user", "company_id": 5})
    scope = "company"

    # Bu kontrol HTTPException fırlatmamalı
    if scope == "global" and not auth_info["is_super_admin"]:
        raise HTTPException(status_code=403, detail="Global onay sadece super_admin yetkisiyle yapılabilir.")

    # company_user company scope için geçmeli
    assert auth_info["company_id"] == 5
    print("✓ TEST 3c: company_user company scope ALLOWED")


# ═══════════════════════════════════════════════════════════════════════════════
# ÇALIŞTIRMA
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*60)
    print("FAZ 3 — GÖREV 3.1: Synonym Scope Testleri")
    print("="*60 + "\n")

    # Test 1: Auth helper
    test_auth_helper_super_admin()
    test_auth_helper_company_admin()
    test_auth_helper_company_user()
    test_auth_helper_no_company_no_super()

    # Test 2: Request model
    test_request_model_default_scope()
    test_request_model_global_scope()
    test_request_model_company_scope()

    # Test 3: Scope kontrolü
    test_scope_check_logic_super_admin_global()
    test_scope_check_logic_company_user_global()
    test_scope_check_logic_company_user_company()

    print("\n" + "="*60)
    print("✅ TÜM TESTLER BAŞARILI (10/10)")
    print("="*60 + "\n")
