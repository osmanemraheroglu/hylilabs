from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from routes.auth import get_current_user
from database import (
    create_interview, update_interview, get_interviews,
    delete_interview, get_connection
)
from models import Interview
from datetime import datetime, timedelta
from typing import Optional
import traceback
import logging
import secrets

from email_sender import send_interview_invite, generate_interview_invite_content

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


def require_company_user(current_user: dict):
    """Firma kullanicisi kontrolu - super_admin bu endpointe erisemez"""
    if current_user.get("company_id") is None:
        raise HTTPException(status_code=403, detail="Bu islem firma kullanicilarina ozeldir. Lutfen firma secin.")


@router.get("/dropdown-data")
def dropdown_data(current_user: dict = Depends(get_current_user)):
    """Mülakat formu için aday ve pozisyon listeleri"""
    require_company_user(current_user)
    try:
        company_id = current_user["company_id"]

        with get_connection() as conn:
            cursor = conn.cursor()

            # Pozisyonları department_pools tablosundan getir (pool_type='position')
            cursor.execute(
                """SELECT id, name as baslik
                   FROM department_pools
                   WHERE company_id = ? AND pool_type = 'position' AND is_active = 1
                   ORDER BY name""",
                (company_id,)
            )
            positions = [dict(row) for row in cursor.fetchall()]

            # Adayları getir (basit liste)
            cursor.execute(
                "SELECT id, ad_soyad, email FROM candidates WHERE company_id = ? ORDER BY ad_soyad",
                (company_id,)
            )
            candidates = [dict(row) for row in cursor.fetchall()]

            # Pozisyon bazlı aday eşleştirmesi (pozisyon seçilince filtreleme için)
            # NOT: Pozisyon adayları candidate_positions tablosunda tutuluyor
            position_candidates = {}
            for pos in positions:
                cursor.execute(
                    """SELECT c.id, c.ad_soyad, c.email
                       FROM candidates c
                       JOIN candidate_positions cp ON cp.candidate_id = c.id
                       WHERE cp.position_id = ? AND c.company_id = ? AND cp.status = 'aktif'
                       ORDER BY c.ad_soyad""",
                    (pos["id"], company_id)
                )
                pos_candidates = [dict(row) for row in cursor.fetchall()]
                position_candidates[str(pos["id"])] = pos_candidates

        return {"success": True, "data": {"positions": positions, "candidates": candidates, "positionCandidates": position_candidates}}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def list_interviews(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    candidate_id: Optional[int] = Query(None),
    durum: Optional[str] = Query(None),
    confirmation_status: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Mulakatlari listele"""
    require_company_user(current_user)
    try:
        company_id = current_user["company_id"]
        sd = datetime.fromisoformat(start_date) if start_date else None
        ed = datetime.fromisoformat(end_date) if end_date else None

        results = get_interviews(
            start_date=sd, end_date=ed,
            candidate_id=candidate_id, durum=durum,
            confirmation_status=confirmation_status,
            company_id=company_id
        )

        # datetime nesnelerini string yap
        for r in results:
            if isinstance(r.get("tarih"), datetime):
                r["tarih"] = r["tarih"].isoformat()
            if isinstance(r.get("olusturma_tarihi"), datetime):
                r["olusturma_tarihi"] = r["olusturma_tarihi"].isoformat()

        return {"success": True, "data": results, "total": len(results)}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_new_interview(
    body: dict,
    current_user: dict = Depends(get_current_user)
):
    """Yeni mulakat olustur"""
    require_company_user(current_user)
    try:
        company_id = current_user["company_id"]

        # Duplicate mülakat kontrolü — aktif mülakatı olan adaya ikinci mülakat engeli
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT COUNT(*) as cnt FROM interviews
                   WHERE candidate_id = ? AND durum = 'planlanmis' AND company_id = ?""",
                (body["candidate_id"], company_id)
            )
            if cursor.fetchone()['cnt'] > 0:
                raise HTTPException(
                    status_code=400,
                    detail="Bu adayın zaten planlanmış bir mülakatı bulunmaktadır"
                )

        interview_date = datetime.fromisoformat(body["tarih"])
        interview = Interview(
            candidate_id=body["candidate_id"],
            position_id=body.get("position_id"),
            tarih=interview_date,
            sure_dakika=body.get("sure_dakika", 60),
            tur=body.get("tur", "teknik"),
            lokasyon=body.get("lokasyon", "online"),
            mulakatci=body.get("mulakatci"),
            durum=body.get("durum", "planlanmis"),
            notlar=body.get("notlar")
        )

        new_id = create_interview(interview, company_id=company_id)

        # Onay token'i olustur ve kaydet
        confirm_token = secrets.token_urlsafe(32)
        onay_suresi = body.get("onay_suresi", 3)  # varsayilan 3 gun
        confirm_expires = datetime.now() + timedelta(days=onay_suresi)

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE interviews
                   SET confirm_token = ?, confirm_token_expires = ?
                   WHERE id = ?""",
                (confirm_token, confirm_expires.isoformat(), new_id)
            )

            # Aday durumunu 'mulakat' olarak guncelle
            cursor.execute(
                """UPDATE candidates
                   SET durum = 'mulakat', guncelleme_tarihi = datetime('now')
                   WHERE id = ? AND company_id = ?""",
                (body["candidate_id"], company_id)
            )
            conn.commit()

        return {
            "success": True,
            "id": new_id,
            "message": "Mülakat oluşturuldu"
        }
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{interview_id}")
def update_existing_interview(
    interview_id: int,
    body: dict,
    current_user: dict = Depends(get_current_user)
):
    """Mulakat guncelle"""
    require_company_user(current_user)
    try:
        company_id = current_user["company_id"]

        # Mulakatin candidate_id'sini al (iptal durumu icin)
        candidate_id = None
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT candidate_id FROM interviews WHERE id = ? AND company_id = ?",
                (interview_id, company_id)
            )
            row = cursor.fetchone()
            if row:
                candidate_id = row["candidate_id"]

        # tarih string ise datetime yap
        if "tarih" in body and isinstance(body["tarih"], str):
            body["tarih"] = datetime.fromisoformat(body["tarih"])

        success = update_interview(interview_id, company_id=company_id, **body)
        if not success:
            raise HTTPException(status_code=404, detail="Mülakat bulunamadı veya değişiklik yok")

        # Eger mulakat iptal edildiyse ve baska aktif mulakat yoksa, aday durumunu geri al
        if body.get("durum") == "iptal" and candidate_id:
            with get_connection() as conn:
                cursor = conn.cursor()
                # Başka aktif mülakat var mı kontrol et
                cursor.execute(
                    """SELECT COUNT(*) as cnt FROM interviews i
                       JOIN candidates c ON c.id = i.candidate_id
                       WHERE i.candidate_id = ? AND i.durum = 'planlanmis'
                       AND c.company_id = ?""",
                    (candidate_id, company_id)
                )
                active_count = cursor.fetchone()['cnt']

                if active_count == 0:
                    # Korumalı durum kontrolü — ise_alindi/arsiv adaylar downgrade edilemez
                    cursor.execute(
                        "SELECT durum FROM candidates WHERE id = ? AND company_id = ?",
                        (candidate_id, company_id)
                    )
                    cand_row = cursor.fetchone()
                    if cand_row and cand_row['durum'] in ('ise_alindi', 'arsiv'):
                        logger.info(f"Mülakat iptal: candidate_id={candidate_id} korumalı durumda ({cand_row['durum']}), durum değiştirilmedi")
                    else:
                        # Adayın gerçek durumunu belirle
                        cursor.execute(
                            "SELECT COUNT(*) as cnt FROM candidate_positions WHERE candidate_id = ? AND status = 'aktif'",
                            (candidate_id,)
                        )
                        pos_count = cursor.fetchone()['cnt']

                        if pos_count > 0:
                            cursor.execute(
                                """UPDATE candidates SET durum = 'pozisyona_atandi', havuz = 'pozisyona_aktarilan', guncelleme_tarihi = datetime('now')
                                   WHERE id = ? AND company_id = ?""",
                                (candidate_id, company_id)
                            )
                        else:
                            cursor.execute(
                                """UPDATE candidates SET durum = 'yeni', havuz = 'genel_havuz', guncelleme_tarihi = datetime('now')
                                   WHERE id = ? AND company_id = ?""",
                                (candidate_id, company_id)
                            )
                conn.commit()

        return {"success": True, "message": "Mülakat güncellendi"}
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{interview_id}")
def delete_existing_interview(
    interview_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Mulakat sil"""
    require_company_user(current_user)
    try:
        company_id = current_user["company_id"]

        # Silmeden once candidate_id'yi al
        candidate_id = None
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT candidate_id FROM interviews WHERE id = ? AND company_id = ?",
                (interview_id, company_id)
            )
            row = cursor.fetchone()
            if row:
                candidate_id = row["candidate_id"]

        success = delete_interview(interview_id, company_id=company_id)
        if not success:
            raise HTTPException(status_code=404, detail="Mülakat bulunamadı")

        # Silme sonrasi: baska aktif mulakat yoksa aday durumunu geri al
        if candidate_id:
            with get_connection() as conn:
                cursor = conn.cursor()
                # Başka aktif mülakat var mı kontrol et
                cursor.execute(
                    """SELECT COUNT(*) as cnt FROM interviews i
                       JOIN candidates c ON c.id = i.candidate_id
                       WHERE i.candidate_id = ? AND i.durum = 'planlanmis'
                       AND c.company_id = ?""",
                    (candidate_id, company_id)
                )
                active_count = cursor.fetchone()['cnt']

                if active_count == 0:
                    # Korumalı durum kontrolü — ise_alindi/arsiv adaylar downgrade edilemez
                    cursor.execute(
                        "SELECT durum FROM candidates WHERE id = ? AND company_id = ?",
                        (candidate_id, company_id)
                    )
                    cand_row = cursor.fetchone()
                    if cand_row and cand_row['durum'] in ('ise_alindi', 'arsiv'):
                        logger.info(f"Mülakat silme: candidate_id={candidate_id} korumalı durumda ({cand_row['durum']}), durum değiştirilmedi")
                    else:
                        # Adayın gerçek durumunu belirle
                        cursor.execute(
                            "SELECT COUNT(*) as cnt FROM candidate_positions WHERE candidate_id = ? AND status = 'aktif'",
                            (candidate_id,)
                        )
                        pos_count = cursor.fetchone()['cnt']

                        if pos_count > 0:
                            cursor.execute(
                                """UPDATE candidates SET durum = 'pozisyona_atandi', havuz = 'pozisyona_aktarilan', guncelleme_tarihi = datetime('now')
                                   WHERE id = ? AND company_id = ?""",
                                (candidate_id, company_id)
                            )
                        else:
                            cursor.execute(
                                """UPDATE candidates SET durum = 'yeni', havuz = 'genel_havuz', guncelleme_tarihi = datetime('now')
                                   WHERE id = ? AND company_id = ?""",
                                (candidate_id, company_id)
                            )
                conn.commit()

        return {"success": True, "message": "Mülakat silindi"}
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{interview_id}/email-preview")
def get_email_preview(
    interview_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Mülakat davet emaili önizleme"""
    require_company_user(current_user)
    try:
        company_id = current_user["company_id"]

        with get_connection() as conn:
            cursor = conn.cursor()

            # Mülakat bilgilerini al
            cursor.execute(
                """SELECT i.*, c.ad_soyad, c.email as candidate_email, dp.name as position_title, co.ad as sirket_adi
                   FROM interviews i
                   JOIN candidates c ON c.id = i.candidate_id
                   LEFT JOIN department_pools dp ON dp.id = i.position_id
                   LEFT JOIN companies co ON co.id = i.company_id
                   WHERE i.id = ? AND i.company_id = ?""",
                (interview_id, company_id)
            )
            interview = cursor.fetchone()

            if not interview:
                raise HTTPException(status_code=404, detail="Mülakat bulunamadı")

            interview = dict(interview)

            # tarih string ise datetime'a çevir
            tarih = interview["tarih"]
            if isinstance(tarih, str):
                tarih = datetime.fromisoformat(tarih)

            # Onay linki oluştur
            confirm_url = None
            onay_suresi = 3  # varsayılan
            if interview.get("confirm_token"):
                confirm_url = f"http://***REMOVED***:8000/api/interviews/confirm/{interview['confirm_token']}"
                # onay_suresi hesapla (confirm_token_expires - olusturma_tarihi)
                if interview.get("confirm_token_expires") and interview.get("olusturma_tarihi"):
                    try:
                        expires = datetime.fromisoformat(interview["confirm_token_expires"])
                        created = datetime.fromisoformat(interview["olusturma_tarihi"])
                        onay_suresi = max(1, (expires - created).days)
                    except:
                        pass

            # Email içeriğini oluştur
            content = generate_interview_invite_content(
                candidate_name=interview["ad_soyad"],
                interview_date=tarih,
                duration=interview.get("sure_dakika", 60),
                interview_type=interview.get("tur", "teknik"),
                location=interview.get("lokasyon", "online"),
                position_title=interview.get("position_title") or "Genel Başvuru",
                interviewer=interview.get("mulakatci"),
                notes=interview.get("notlar"),
                confirm_url=confirm_url,
                onay_suresi=onay_suresi,
                sirket_adi=interview.get("sirket_adi")
            )

            return {
                "success": True,
                "data": {
                    "konu": content["konu"],
                    "icerik": content["icerik"],
                    "to_email": interview["candidate_email"],
                    "aday_adi": interview["ad_soyad"]
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{interview_id}/send-email")
def send_interview_email(
    interview_id: int,
    body: dict,
    current_user: dict = Depends(get_current_user)
):
    """Mülakat davet emaili gönder"""
    require_company_user(current_user)
    try:
        company_id = current_user["company_id"]
        to_email = body.get("to_email")

        if not to_email:
            raise HTTPException(status_code=400, detail="Email adresi gerekli")

        with get_connection() as conn:
            cursor = conn.cursor()

            # Mülakat bilgilerini al
            cursor.execute(
                """SELECT i.*, c.ad_soyad, dp.name as position_title, co.ad as sirket_adi
                   FROM interviews i
                   JOIN candidates c ON c.id = i.candidate_id
                   LEFT JOIN department_pools dp ON dp.id = i.position_id
                   LEFT JOIN companies co ON co.id = i.company_id
                   WHERE i.id = ? AND i.company_id = ?""",
                (interview_id, company_id)
            )
            interview = cursor.fetchone()

            if not interview:
                raise HTTPException(status_code=404, detail="Mülakat bulunamadı")

            interview = dict(interview)

            # Email hesabını al (varsayılan gönderim hesabı)
            cursor.execute(
                """SELECT * FROM email_accounts
                   WHERE company_id = ? AND aktif = 1 AND varsayilan_gonderim = 1
                   LIMIT 1""",
                (company_id,)
            )
            email_account = cursor.fetchone()
            email_account = dict(email_account) if email_account else None

            # tarih string ise datetime'a çevir
            tarih = interview["tarih"]
            if isinstance(tarih, str):
                tarih = datetime.fromisoformat(tarih)

            # Onay linki oluştur
            confirm_url = None
            onay_suresi = 3  # varsayılan
            if interview.get("confirm_token"):
                confirm_url = f"http://***REMOVED***:8000/api/interviews/confirm/{interview['confirm_token']}"
                # onay_suresi hesapla (confirm_token_expires - olusturma_tarihi)
                if interview.get("confirm_token_expires") and interview.get("olusturma_tarihi"):
                    try:
                        expires = datetime.fromisoformat(interview["confirm_token_expires"])
                        created = datetime.fromisoformat(interview["olusturma_tarihi"])
                        onay_suresi = max(1, (expires - created).days)
                    except:
                        pass

            # Email gönder
            success, msg = send_interview_invite(
                candidate_name=interview["ad_soyad"],
                candidate_email=to_email,
                interview_date=tarih,
                duration=interview.get("sure_dakika", 60),
                interview_type=interview.get("tur", "teknik"),
                location=interview.get("lokasyon", "online"),
                position_title=interview.get("position_title") or "Genel Başvuru",
                interviewer=interview.get("mulakatci"),
                notes=interview.get("notlar"),
                account=email_account,
                confirm_url=confirm_url,
                onay_suresi=onay_suresi,
                sirket_adi=interview.get("sirket_adi")
            )

            if not success:
                raise HTTPException(status_code=500, detail=f"Email gönderilemedi: {msg}")

            return {
                "success": True,
                "message": "Email başarıyla gönderildi"
            }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/confirm/{token}")
def confirm_interview(token: str):
    """Mulakat onay linki - public endpoint (auth gerektirmez)"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Token'i bul
            cursor.execute(
                """SELECT id, company_id, candidate_id, confirmation_status, confirm_token_expires
                   FROM interviews WHERE confirm_token = ?""",
                (token,)
            )
            interview = cursor.fetchone()

            if not interview:
                return HTMLResponse("""
                <html>
                <head><meta charset="UTF-8"><title>Hata</title></head>
                <body style="font-family:Arial;text-align:center;padding:50px">
                <h1 style="color:#dc2626">Gecersiz Onay Linki</h1>
                <p>Bu link geçersiz veya bulunamadı.</p>
                </body>
                </html>
                """, status_code=404)

            interview = dict(interview)

            # Zaten onaylanmis mi?
            if interview.get('confirmation_status') == 'confirmed':
                return HTMLResponse("""
                <html>
                <head><meta charset="UTF-8"><title>Zaten Onaylandi</title></head>
                <body style="font-family:Arial;text-align:center;padding:50px">
                <h1 style="color:#16a34a">✅ Bu Mulakat Zaten Onaylandi</h1>
                <p>Mulakatiniz daha once onaylanmistir.</p>
                <p>Gorusmek uzere!</p>
                </body>
                </html>
                """)

            # Sure dolmus mu?
            if interview.get('confirm_token_expires'):
                expires = datetime.fromisoformat(interview['confirm_token_expires'])
                if datetime.now() > expires:
                    return HTMLResponse("""
                    <html>
                    <head><meta charset="UTF-8"><title>Sure Doldu</title></head>
                    <body style="font-family:Arial;text-align:center;padding:50px">
                    <h1 style="color:#dc2626">Onay Linki Suresi Dolmus</h1>
                    <p>Bu onay linkinin suresi dolmustur.</p>
                    <p>Lutfen firma ile iletisime gecin.</p>
                    </body>
                    </html>
                    """, status_code=410)

            # Onayla
            cursor.execute(
                """UPDATE interviews
                   SET confirmation_status = 'confirmed', confirmed_at = datetime('now')
                   WHERE confirm_token = ?""",
                (token,)
            )
            conn.commit()

            return HTMLResponse("""
            <html>
            <head><meta charset="UTF-8"><title>Onaylandi</title></head>
            <body style="font-family:Arial;text-align:center;padding:50px;background:#f0fdf4">
            <h1 style="color:#16a34a">✅ Mulakatiniz Onaylandi!</h1>
            <p style="font-size:18px">Mulakat davetinizi onayladiginiz icin tesekkur ederiz.</p>
            <p style="margin-top:30px">Gorusmek uzere!</p>
            </body>
            </html>
            """)

    except Exception as e:
        logger.error(f"Mulakat onay hatasi: {e}")
        traceback.print_exc()
        return HTMLResponse("""
        <html>
        <head><meta charset="UTF-8"><title>Hata</title></head>
        <body style="font-family:Arial;text-align:center;padding:50px">
        <h1 style="color:#dc2626">Bir Hata Olustu</h1>
        <p>Lutfen daha sonra tekrar deneyin.</p>
        </body>
        </html>
        """, status_code=500)
