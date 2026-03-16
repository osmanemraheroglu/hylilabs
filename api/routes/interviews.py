from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form
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
from rate_limiter import check_rate_limit, record_action

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

        # Değerlendirme durumuna göre aday taşıma aksiyonu
        sonuc_karari = body.get("sonuc_karari")
        if sonuc_karari in ("genel_havuz", "arsiv", "kara_liste", "ise_alindi") and candidate_id:
            with get_connection() as conn:
                cursor = conn.cursor()
                # company_id ile aday sahiplik kontrolü
                cursor.execute(
                    "SELECT id, durum FROM candidates WHERE id = ? AND company_id = ?",
                    (candidate_id, company_id)
                )
                cand_check = cursor.fetchone()
                if cand_check:
                    if sonuc_karari == "genel_havuz":
                        # Pozisyon atamasını sil
                        cursor.execute("DELETE FROM candidate_positions WHERE candidate_id = ?", (candidate_id,))
                        # Eski havuz atamasını sil
                        cursor.execute(
                            "DELETE FROM candidate_pool_assignments WHERE candidate_id = ? AND company_id = ?",
                            (candidate_id, company_id)
                        )
                        # Genel Havuz'a ekle
                        cursor.execute(
                            "SELECT id FROM department_pools WHERE company_id = ? AND name = 'Genel Havuz' AND is_system = 1",
                            (company_id,)
                        )
                        genel_pool = cursor.fetchone()
                        if genel_pool:
                            cursor.execute(
                                "INSERT OR IGNORE INTO candidate_pool_assignments (candidate_id, department_pool_id, company_id) VALUES (?, ?, ?)",
                                (candidate_id, genel_pool["id"], company_id)
                            )
                        cursor.execute(
                            "UPDATE candidates SET durum = 'yeni', havuz = 'genel_havuz', guncelleme_tarihi = datetime('now') WHERE id = ? AND company_id = ?",
                            (candidate_id, company_id)
                        )
                        logger.info(f"Değerlendirme: candidate_id={candidate_id} Genel Havuz'a taşındı (company_id={company_id})")

                    elif sonuc_karari in ("arsiv", "kara_liste"):
                        # Pozisyon atamasını sil
                        cursor.execute("DELETE FROM candidate_positions WHERE candidate_id = ?", (candidate_id,))
                        # Eski havuz atamasını sil
                        cursor.execute("DELETE FROM candidate_pool_assignments WHERE candidate_id = ?", (candidate_id,))
                        # Arşiv havuzuna ekle
                        cursor.execute(
                            "SELECT id FROM department_pools WHERE company_id = ? AND name = 'Arşiv' AND is_system = 1",
                            (company_id,)
                        )
                        arsiv_pool = cursor.fetchone()
                        if arsiv_pool:
                            cursor.execute(
                                "INSERT INTO candidate_pool_assignments (candidate_id, department_pool_id, company_id) VALUES (?, ?, ?)",
                                (candidate_id, arsiv_pool["id"], company_id)
                            )
                        cursor.execute(
                            "UPDATE candidates SET durum = 'arsiv', havuz = 'arsiv', guncelleme_tarihi = datetime('now') WHERE id = ? AND company_id = ?",
                            (candidate_id, company_id)
                        )
                        log_msg = "Arşiv'e" if sonuc_karari == "arsiv" else "Arşiv'e (Kara Liste)"
                        logger.info(f"Değerlendirme: candidate_id={candidate_id} {log_msg} taşındı (company_id={company_id})")

                    elif sonuc_karari == "ise_alindi":
                        # FAZ 10.1: Pozisyon ID'lerini al ÖNCE silmeden
                        try:
                            from database import update_hired_stats
                            cursor.execute(
                                "SELECT position_id FROM candidate_positions WHERE candidate_id = ?",
                                (candidate_id,)
                            )
                            position_ids = [row[0] for row in cursor.fetchall()]
                            for position_id in position_ids:
                                update_hired_stats(candidate_id, position_id)
                        except Exception as e:
                            logger.warning(f"update_hired_stats hatası: {e}")
                        # Pozisyon atamasını sil
                        cursor.execute("DELETE FROM candidate_positions WHERE candidate_id = ?", (candidate_id,))
                        # Havuz atamasını sil
                        cursor.execute(
                            "DELETE FROM candidate_pool_assignments WHERE candidate_id = ? AND company_id = ?",
                            (candidate_id, company_id)
                        )
                        cursor.execute(
                            "UPDATE candidates SET durum = 'ise_alindi', havuz = NULL, guncelleme_tarihi = datetime('now') WHERE id = ? AND company_id = ?",
                            (candidate_id, company_id)
                        )
                        logger.info(f"Değerlendirme: candidate_id={candidate_id} İşe Alındı (company_id={company_id})")

                conn.commit()

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


KVKK_CONSENT_TEXT = """
6698 sayılı Kişisel Verilerin Korunması Kanunu ("KVKK") kapsamında, mülakat sürecinde
kişisel verilerinizin işlenmesine ilişkin aşağıdaki hususlarda bilgilendirilmektesiniz:

1. VERİ SORUMLUSU
Mülakat davetini gönderen firma, kişisel verilerinizin veri sorumlusudur.

2. İŞLENEN KİŞİSEL VERİLER
Mülakat sürecinde aşağıdaki kişisel verileriniz işlenmektedir:
- Kimlik bilgileri (ad, soyad)
- İletişim bilgileri (e-posta, telefon)
- Mülakat katılım ve onay bilgileri
- Mülakat değerlendirme sonuçları

3. İŞLEME AMACI
Kişisel verileriniz, işe alım sürecinin yürütülmesi, mülakat organizasyonu ve
değerlendirme süreçlerinin gerçekleştirilmesi amacıyla işlenmektedir.

4. VERİ AKTARIMI
Kişisel verileriniz, işe alım sürecinde görev alan yetkili kişilerle paylaşılabilir.
Verileriniz yurt dışına aktarılmamaktadır.

5. SAKLAMA SÜRESİ
Kişisel verileriniz, işe alım sürecinin tamamlanmasından itibaren en fazla 2 yıl
süreyle saklanacaktır.

6. HAKLARINIZ
KVKK'nın 11. maddesi uyarınca aşağıdaki haklara sahipsiniz:
- Kişisel verilerinizin işlenip işlenmediğini öğrenme
- İşlenmişse buna ilişkin bilgi talep etme
- İşlenme amacını ve bunların amacına uygun kullanılıp kullanılmadığını öğrenme
- Yurt içinde veya yurt dışında aktarıldığı üçüncü kişileri bilme
- Eksik veya yanlış işlenmiş olması halinde düzeltilmesini isteme
- Silinmesini veya yok edilmesini isteme
- Düzeltme, silme veya yok etme işlemlerinin aktarıldığı üçüncü kişilere bildirilmesini isteme
- Münhasıran otomatik sistemler vasıtasıyla analiz edilmesi suretiyle aleyhinize bir sonucun ortaya çıkmasına itiraz etme
- Kanuna aykırı olarak işlenmesi sebebiyle zarara uğramanız halinde zararın giderilmesini talep etme

Bu haklarınızı kullanmak için mülakat davetini gönderen firma ile iletişime geçebilirsiniz.
""".strip()

KVKK_METIN_VERSIYONU = "v1.0"


def _validate_confirm_token(token: str):
    """Token doğrulama — ortak mantık (GET ve POST için)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT i.id, i.company_id, i.candidate_id, i.confirmation_status, i.confirm_token_expires,
                      c.ad_soyad, c.email, c.telefon
               FROM interviews i
               JOIN candidates c ON c.id = i.candidate_id
               WHERE i.confirm_token = ?""",
            (token,)
        )
        row = cursor.fetchone()
        if not row:
            return None, "not_found"
        interview = dict(row)
        if interview.get('confirmation_status') == 'confirmed':
            return interview, "already_confirmed"
        if interview.get('confirm_token_expires'):
            expires = datetime.fromisoformat(interview['confirm_token_expires'])
            if datetime.now() > expires:
                return interview, "expired"
        return interview, "valid"


@router.get("/confirm/{token}")
def confirm_interview(token: str):
    """Mulakat onay linki - KVKK onay sayfasi gosterir (public endpoint)"""
    try:
        interview, status = _validate_confirm_token(token)

        if status == "not_found":
            return HTMLResponse("""
            <html>
            <head><meta charset="UTF-8"><title>Hata</title></head>
            <body style="font-family:Arial;text-align:center;padding:50px">
            <h1 style="color:#dc2626">Geçersiz Onay Linki</h1>
            <p>Bu link geçersiz veya bulunamadı.</p>
            </body>
            </html>
            """, status_code=404)

        if status == "already_confirmed":
            return HTMLResponse("""
            <html>
            <head><meta charset="UTF-8"><title>Zaten Onaylandı</title></head>
            <body style="font-family:Arial;text-align:center;padding:50px">
            <h1 style="color:#16a34a">&#10003; Bu Mülakat Zaten Onaylandı</h1>
            <p>Mülakatınız daha önce onaylanmıştır.</p>
            <p>Görüşmek üzere!</p>
            </body>
            </html>
            """)

        if status == "expired":
            return HTMLResponse("""
            <html>
            <head><meta charset="UTF-8"><title>Süre Doldu</title></head>
            <body style="font-family:Arial;text-align:center;padding:50px">
            <h1 style="color:#dc2626">Onay Linki Süresi Dolmuş</h1>
            <p>Bu onay linkinin süresi dolmuştur.</p>
            <p>Lütfen firma ile iletişime geçin.</p>
            </body>
            </html>
            """, status_code=410)

        # KVKK onay sayfasi goster
        kvkk_html = KVKK_CONSENT_TEXT.replace('\n', '<br>')
        ad_soyad = interview.get('ad_soyad', '')

        return HTMLResponse(f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Mülakat Onayı — KVKK Aydınlatma</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; color: #1e293b; line-height: 1.6; }}
                .container {{ max-width: 700px; margin: 30px auto; padding: 0 20px; }}
                .card {{ background: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }}
                .header {{ background: #1e40af; color: white; padding: 24px; text-align: center; }}
                .header h1 {{ font-size: 20px; margin-bottom: 4px; }}
                .header p {{ font-size: 14px; opacity: 0.9; }}
                .content {{ padding: 24px; }}
                .greeting {{ font-size: 16px; margin-bottom: 16px; }}
                .kvkk-box {{ background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; max-height: 300px; overflow-y: auto; font-size: 13px; line-height: 1.7; margin-bottom: 20px; }}
                .consent-form {{ border-top: 1px solid #e2e8f0; padding-top: 20px; }}
                .checkbox-row {{ display: flex; align-items: flex-start; gap: 10px; margin-bottom: 20px; }}
                .checkbox-row input {{ margin-top: 4px; width: 18px; height: 18px; cursor: pointer; }}
                .checkbox-row label {{ font-size: 14px; cursor: pointer; }}
                .btn {{ display: block; width: 100%; padding: 14px; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; transition: background 0.2s; }}
                .btn-primary {{ background: #16a34a; color: white; }}
                .btn-primary:hover {{ background: #15803d; }}
                .btn-primary:disabled {{ background: #94a3b8; cursor: not-allowed; }}
                .version {{ text-align: center; margin-top: 16px; font-size: 11px; color: #94a3b8; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <div class="header">
                        <h1>Mülakat Onayı</h1>
                        <p>Kişisel Verilerin Korunması Aydınlatma Metni</p>
                    </div>
                    <div class="content">
                        <p class="greeting">Sayın <strong>{ad_soyad}</strong>,</p>
                        <p style="margin-bottom:16px;font-size:14px;">Mülakat davetinizi onaylamadan önce, kişisel verilerinizin işlenmesine ilişkin aşağıdaki aydınlatma metnini okuyunuz:</p>

                        <div class="kvkk-box">
                            {kvkk_html}
                        </div>

                        <form class="consent-form" method="POST" action="/api/interviews/confirm/{token}/kvkk">
                            <div class="checkbox-row">
                                <input type="checkbox" id="kvkk_onay" name="kvkk_onay" value="1" onchange="document.getElementById('submitBtn').disabled = !this.checked">
                                <label for="kvkk_onay">Yukarıdaki KVKK aydınlatma metnini okudum, anladım ve kişisel verilerimin belirtilen amaçlarla işlenmesine açık rıza veriyorum.</label>
                            </div>
                            <button type="submit" id="submitBtn" class="btn btn-primary" disabled>Mülakatı Onayla</button>
                        </form>

                        <p class="version">KVKK Aydınlatma Metni Versiyon: {KVKK_METIN_VERSIYONU}</p>
                    </div>
                </div>
            </div>
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
        <h1 style="color:#dc2626">Bir Hata Oluştu</h1>
        <p>Lütfen daha sonra tekrar deneyin.</p>
        </body>
        </html>
        """, status_code=500)


@router.post("/confirm/{token}/kvkk")
async def confirm_interview_kvkk(token: str, request: Request, kvkk_onay: str = Form(default="")):
    """Mulakat KVKK onay + mulakat onaylama — public endpoint (auth gerektirmez)"""
    try:
        # Rate limiting — 10 istek/saat/IP
        client_ip = request.client.host if request.client else "unknown"
        allowed, count, remaining = check_rate_limit(client_ip, "interview_confirm", 10, 60)
        if not allowed:
            return HTMLResponse("""
            <html>
            <head><meta charset="UTF-8"><title>Çok Fazla İstek</title></head>
            <body style="font-family:Arial;text-align:center;padding:50px">
            <h1 style="color:#dc2626">Çok Fazla İstek</h1>
            <p>Lütfen bir süre bekleyip tekrar deneyin.</p>
            </body>
            </html>
            """, status_code=429)

        # Rate limit kaydi
        record_action(client_ip, "interview_confirm")

        # KVKK onay kontrolu
        if kvkk_onay != "1":
            return HTMLResponse("""
            <html>
            <head><meta charset="UTF-8"><title>KVKK Onayı Gerekli</title></head>
            <body style="font-family:Arial;text-align:center;padding:50px">
            <h1 style="color:#dc2626">KVKK Onayı Gerekli</h1>
            <p>Mülakatınızı onaylamak için KVKK aydınlatma metnini onaylamanız gerekmektedir.</p>
            <p style="margin-top:20px"><a href="/api/interviews/confirm/{token}" style="color:#1e40af">Geri Dön</a></p>
            </body>
            </html>
            """, status_code=400)

        # Token dogrulama
        interview, status = _validate_confirm_token(token)

        if status == "not_found":
            return HTMLResponse("""
            <html>
            <head><meta charset="UTF-8"><title>Hata</title></head>
            <body style="font-family:Arial;text-align:center;padding:50px">
            <h1 style="color:#dc2626">Geçersiz Onay Linki</h1>
            <p>Bu link geçersiz veya bulunamadı.</p>
            </body>
            </html>
            """, status_code=404)

        if status == "already_confirmed":
            return HTMLResponse("""
            <html>
            <head><meta charset="UTF-8"><title>Zaten Onaylandı</title></head>
            <body style="font-family:Arial;text-align:center;padding:50px">
            <h1 style="color:#16a34a">&#10003; Bu Mülakat Zaten Onaylandı</h1>
            <p>Mülakatınız daha önce onaylanmıştır.</p>
            <p>Görüşmek üzere!</p>
            </body>
            </html>
            """)

        if status == "expired":
            return HTMLResponse("""
            <html>
            <head><meta charset="UTF-8"><title>Süre Doldu</title></head>
            <body style="font-family:Arial;text-align:center;padding:50px">
            <h1 style="color:#dc2626">Onay Linki Süresi Dolmuş</h1>
            <p>Bu onay linkinin süresi dolmuştur.</p>
            <p>Lütfen firma ile iletişime geçin.</p>
            </body>
            </html>
            """, status_code=410)

        # User-Agent al
        user_agent = request.headers.get("user-agent", "")

        # KVKK onay kaydi + mulakat onaylama — tek transaction
        with get_connection() as conn:
            cursor = conn.cursor()

            # KVKK consent kaydi (immutable — sadece INSERT)
            cursor.execute(
                """INSERT INTO kvkk_consents
                   (interview_id, candidate_id, company_id, ad_soyad, email, telefon,
                    consent_given, consent_text, kvkk_metin_versiyonu, confirm_token,
                    ip_address, user_agent)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)""",
                (
                    interview['id'],
                    interview['candidate_id'],
                    interview['company_id'],
                    interview.get('ad_soyad', ''),
                    interview.get('email', ''),
                    interview.get('telefon', ''),
                    KVKK_CONSENT_TEXT,
                    KVKK_METIN_VERSIYONU,
                    token,
                    client_ip,
                    user_agent
                )
            )

            # Mulakat onaylama
            cursor.execute(
                """UPDATE interviews
                   SET confirmation_status = 'confirmed', confirmed_at = datetime('now')
                   WHERE confirm_token = ?""",
                (token,)
            )
            conn.commit()

        logger.info(f"Mulakat onaylandi (KVKK dahil): interview_id={interview['id']}, candidate_id={interview['candidate_id']}, IP={client_ip}")

        return HTMLResponse("""
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Onaylandı</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0fdf4; color: #1e293b; }
                .container { max-width: 500px; margin: 60px auto; text-align: center; padding: 0 20px; }
                .icon { font-size: 64px; margin-bottom: 16px; }
                h1 { color: #16a34a; margin-bottom: 12px; }
                p { font-size: 16px; margin-bottom: 8px; }
                .note { margin-top: 24px; font-size: 13px; color: #64748b; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">&#10003;</div>
                <h1>Mülakatınız Onaylandı!</h1>
                <p>Mülakat davetinizi onayladığınız için teşekkür ederiz.</p>
                <p>KVKK aydınlatma metni onayınız kaydedilmiştir.</p>
                <p style="margin-top:30px;font-weight:600;">Görüşmek üzere!</p>
                <p class="note">Bu sayfayı kapatabilirsiniz.</p>
            </div>
        </body>
        </html>
        """)

    except Exception as e:
        logger.error(f"Mulakat KVKK onay hatasi: {e}")
        traceback.print_exc()
        return HTMLResponse("""
        <html>
        <head><meta charset="UTF-8"><title>Hata</title></head>
        <body style="font-family:Arial;text-align:center;padding:50px">
        <h1 style="color:#dc2626">Bir Hata Oluştu</h1>
        <p>Lütfen daha sonra tekrar deneyin.</p>
        </body>
        </html>
        """, status_code=500)


@router.get("/kvkk-consents")
def list_kvkk_consents(
    current_user: dict = Depends(get_current_user)
):
    """KVKK onay kayıtlarını listele — firma bazlı"""
    require_company_user(current_user)
    try:
        company_id = current_user["company_id"]

        with get_connection() as conn:
            cursor = conn.cursor()

            # Tüm KVKK onay kayıtlarını getir
            cursor.execute(
                """SELECT kc.id, kc.ad_soyad, kc.email, kc.telefon,
                          kc.consent_given, kc.consent_text, kc.kvkk_metin_versiyonu,
                          kc.confirm_token, kc.ip_address, kc.user_agent, kc.created_at,
                          i.tarih as mulakat_tarih, i.durum as mulakat_durum,
                          dp.name as pozisyon
                   FROM kvkk_consents kc
                   JOIN interviews i ON i.id = kc.interview_id
                   LEFT JOIN department_pools dp ON dp.id = i.position_id
                   WHERE kc.company_id = ?
                   ORDER BY kc.created_at DESC""",
                (company_id,)
            )
            rows = [dict(row) for row in cursor.fetchall()]

            # İstatistikler
            toplam = len(rows)

            # Bu ay
            cursor.execute(
                """SELECT COUNT(*) as cnt FROM kvkk_consents
                   WHERE company_id = ? AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')""",
                (company_id,)
            )
            bu_ay = cursor.fetchone()['cnt']

            # Aktif mülakat (KVKK onaylı + planlanmış)
            cursor.execute(
                """SELECT COUNT(*) as cnt FROM kvkk_consents kc
                   JOIN interviews i ON i.id = kc.interview_id
                   WHERE kc.company_id = ? AND i.durum = 'planlanmis'""",
                (company_id,)
            )
            aktif_mulakat = cursor.fetchone()['cnt']

            metin_versiyonu = KVKK_METIN_VERSIYONU

        return {
            "success": True,
            "data": rows,
            "stats": {
                "toplam": toplam,
                "bu_ay": bu_ay,
                "aktif_mulakat": aktif_mulakat,
                "metin_versiyonu": metin_versiyonu
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"KVKK consents listeleme hatasi: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="KVKK onay kayıtları yüklenemedi")
