from fastapi import APIRouter, Depends, HTTPException
from routes.auth import get_current_user
from database import (
    create_email_account, get_all_email_accounts, update_email_account,
    delete_email_account, verify_email_account_ownership,
    set_default_email_account
)
import traceback
import imaplib

router = APIRouter(prefix="/api/emails", tags=["emails"])


def mask_password(accounts: list[dict]) -> list[dict]:
    """Sifreleri maskele - frontend'e gonderme"""
    for acc in accounts:
        if acc.get("sifre"):
            acc["sifre"] = "****"
    return accounts


@router.get("")
def list_email_accounts(current_user: dict = Depends(get_current_user)):
    """Email hesaplarini listele"""
    try:
        company_id = current_user["company_id"]
        accounts = get_all_email_accounts(only_active=False, company_id=company_id)
        return {"success": True, "data": mask_password(accounts), "total": len(accounts)}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_new_email_account(body: dict, current_user: dict = Depends(get_current_user)):
    """Yeni email hesabi ekle"""
    try:
        company_id = current_user["company_id"]
        required = ["ad", "saglayici", "email", "sifre", "imap_server", "smtp_server"]
        for field in required:
            if not body.get(field):
                raise HTTPException(status_code=400, detail=f"{field} zorunludur")

        new_id = create_email_account(
            ad=body["ad"],
            saglayici=body["saglayici"],
            email=body["email"],
            sifre=body["sifre"],
            imap_server=body["imap_server"],
            smtp_server=body["smtp_server"],
            imap_port=body.get("imap_port", 993),
            smtp_port=body.get("smtp_port", 587),
            sender_name=body.get("sender_name"),
            company_id=company_id
        )
        return {"success": True, "id": new_id, "message": "Email hesabi eklendi"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=409, detail="Bu email adresi zaten kayitli")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{account_id}")
def update_existing_email_account(
    account_id: int, body: dict, current_user: dict = Depends(get_current_user)
):
    """Email hesabi guncelle"""
    try:
        company_id = current_user["company_id"]
        fields = {k: v for k, v in body.items() if k != "id"}
        if not fields:
            raise HTTPException(status_code=400, detail="Guncellenecek alan yok")

        success = update_email_account(account_id, company_id=company_id, **fields)
        if not success:
            raise HTTPException(status_code=404, detail="Hesap bulunamadi veya degisiklik yok")
        return {"success": True, "message": "Hesap guncellendi"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{account_id}")
def delete_existing_email_account(
    account_id: int, current_user: dict = Depends(get_current_user)
):
    """Email hesabi sil"""
    try:
        company_id = current_user["company_id"]
        success = delete_email_account(account_id, company_id=company_id)
        if not success:
            raise HTTPException(status_code=404, detail="Hesap bulunamadi")
        return {"success": True, "message": "Hesap silindi"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/test")
def test_email_connection(
    account_id: int, current_user: dict = Depends(get_current_user)
):
    """IMAP baglanti testi"""
    try:
        company_id = current_user["company_id"]
        if not verify_email_account_ownership(account_id, company_id):
            raise HTTPException(status_code=403, detail="Bu hesaba erisim yetkiniz yok")

        # Hesap bilgilerini al (sifre cozulmus olarak)
        accounts = get_all_email_accounts(only_active=False, company_id=company_id)
        account = next((a for a in accounts if a["id"] == account_id), None)
        if not account:
            raise HTTPException(status_code=404, detail="Hesap bulunamadi")

        # IMAP baglanti testi
        try:
            mail = imaplib.IMAP4_SSL(account["imap_server"], account["imap_port"], timeout=10)
            mail.login(account["email"], account["sifre"])
            status, folders = mail.list()
            folder_count = len(folders) if folders else 0
            mail.logout()
            return {
                "success": True,
                "message": f"Baglanti basarili! {folder_count} klasor bulundu.",
                "folders": folder_count
            }
        except imaplib.IMAP4.error as imap_err:
            return {"success": False, "message": f"IMAP hatasi: {str(imap_err)}"}
        except TimeoutError:
            return {"success": False, "message": "Baglanti zaman asimina ugradi (10sn)"}
        except Exception as conn_err:
            return {"success": False, "message": f"Baglanti hatasi: {str(conn_err)}"}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{account_id}/default")
def set_default_account(
    account_id: int, body: dict, current_user: dict = Depends(get_current_user)
):
    """Varsayilan email hesabi ayarla"""
    try:
        company_id = current_user["company_id"]
        if not verify_email_account_ownership(account_id, company_id):
            raise HTTPException(status_code=403, detail="Bu hesaba erisim yetkiniz yok")

        for_reading = body.get("for_reading", False)
        for_sending = body.get("for_sending", False)

        if not for_reading and not for_sending:
            raise HTTPException(status_code=400, detail="for_reading veya for_sending belirtilmeli")

        set_default_email_account(account_id, for_reading=for_reading, for_sending=for_sending)
        return {"success": True, "message": "Varsayilan hesap ayarlandi"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
