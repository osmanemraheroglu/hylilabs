"""
HyliLabs Scheduler
APScheduler ile zamanlanmis gorevler
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database import get_connection
from email_sender import send_interview_invite
from audit_logger import log_action, AuditAction, EntityType
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)


def send_reminder_emails():
    """
    Her gun 09:00'da calisir.
    Yarin suresi dolacak, hala pending olan mulakatlari bulur
    ve hatirlatma emaili gonderir.
    """
    logger.info("Hatirlatma email gorevi basladi")

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Yarin suresi dolacak, hala pending olanlari bul
            yarin = (date.today() + timedelta(days=1)).isoformat()

            cursor.execute("""
                SELECT
                    i.id, i.candidate_id, i.position_id, i.tarih, i.saat,
                    i.sure_dakika, i.tur, i.lokasyon, i.mulakatci, i.notlar,
                    i.confirm_token, i.confirm_token_expires, i.company_id,
                    i.onay_suresi, i.hatirlatma_gonderildi,
                    c.ad_soyad, c.email as candidate_email,
                    co.ad as sirket_adi,
                    dp.name as position_title
                FROM interviews i
                JOIN candidates c ON c.id = i.candidate_id
                JOIN companies co ON co.id = i.company_id
                LEFT JOIN department_pools dp ON dp.id = i.position_id
                WHERE i.confirmation_status = 'pending'
                  AND date(i.confirm_token_expires) = ?
                  AND (i.hatirlatma_gonderildi IS NULL OR i.hatirlatma_gonderildi = 0)
                  AND c.email IS NOT NULL
                  AND c.email != ''
            """, (yarin,))

            interviews = [dict(row) for row in cursor.fetchall()]

            logger.info(f"Hatirlatma gonderilecek mulakat sayisi: {len(interviews)}")

            for interview in interviews:
                try:
                    # Her sirketin kendi email hesabini al
                    cursor.execute("""
                        SELECT * FROM email_accounts
                        WHERE company_id = ? AND varsayilan_gonderim = 1 AND aktif = 1
                        LIMIT 1
                    """, (interview['company_id'],))
                    account_row = cursor.fetchone()
                    account = dict(account_row) if account_row else None

                    if not account:
                        logger.warning(f"Sirket {interview['company_id']} icin email hesabi bulunamadi")
                        continue

                    # Tarih parse
                    tarih_str = interview['tarih']
                    if isinstance(tarih_str, str):
                        if 'T' in tarih_str:
                            interview_date = datetime.fromisoformat(tarih_str)
                        else:
                            interview_date = datetime.strptime(tarih_str, '%Y-%m-%d')
                    else:
                        interview_date = tarih_str

                    # Onay suresi
                    onay_suresi = interview['onay_suresi'] or 3

                    # Confirm URL
                    confirm_url = None
                    if interview['confirm_token']:
                        confirm_url = f"http://***REMOVED***:8000/api/interviews/confirm/{interview['confirm_token']}"

                    # Hatirlatma emaili gonder
                    success, msg = send_interview_invite(
                        candidate_name=interview['ad_soyad'],
                        candidate_email=interview['candidate_email'],
                        interview_date=interview_date,
                        duration=interview['sure_dakika'] or 60,
                        interview_type=interview['tur'] or 'teknik',
                        location=interview['lokasyon'] or 'online',
                        position_title=interview['position_title'] or 'Genel Basvuru',
                        interviewer=interview['mulakatci'],
                        notes=interview['notlar'],
                        sirket_adi=interview['sirket_adi'],
                        confirm_url=confirm_url,
                        onay_suresi=onay_suresi,
                        account=account,
                        is_reminder=True
                    )

                    if success:
                        # Hatirlatma gonderildi olarak isaretle
                        cursor.execute(
                            "UPDATE interviews SET hatirlatma_gonderildi = 1 WHERE id = ?",
                            (interview['id'],)
                        )
                        conn.commit()
                        logger.info(f"Hatirlatma emaili gonderildi: {interview['candidate_email']}")
                    else:
                        logger.error(f"Hatirlatma emaili gonderilemedi: {msg}")

                except Exception as e:
                    logger.error(f"Hatirlatma emaili gonderilemedi (interview_id={interview['id']}): {e}")

    except Exception as e:
        logger.error(f"send_reminder_emails hatasi: {e}")


def auto_cancel_expired_interviews():
    """
    Her gun 09:05'te calisir.
    Onay suresi dolmus + onaylanmamis + hala planlanmis olan
    mulakatlari otomatik iptal eder ve aday durumunu gunceller.
    """
    logger.info("[auto-cancel] Otomatik iptal gorevi basladi")

    # Audit log kayitlarini topla, DB baglantisi kapandiktan sonra yaz
    # (audit_logger kendi baglantisi acar, ayni anda 2 baglanti SQLite'da "database is locked" verir)
    audit_entries = []

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Suresi dolmus, pending, planlanmis mulakatlari bul
            cursor.execute("""
                SELECT i.id, i.candidate_id, i.company_id,
                       c.ad_soyad, c.durum as aday_durum
                FROM interviews i
                JOIN candidates c ON c.id = i.candidate_id
                WHERE i.confirm_token_expires < datetime('now')
                  AND i.confirmation_status = 'pending'
                  AND i.durum = 'planlanmis'
            """)

            expired_interviews = [dict(row) for row in cursor.fetchall()]

            logger.info(f"[auto-cancel] Suresi dolmus mulakat sayisi: {len(expired_interviews)}")

            iptal_sayisi = 0
            for interview in expired_interviews:
                try:
                    interview_id = interview['id']
                    candidate_id = interview['candidate_id']
                    company_id = interview['company_id']
                    ad_soyad = interview['ad_soyad']
                    aday_durum = interview['aday_durum']

                    # 1. Mulakati iptal et
                    cursor.execute(
                        "UPDATE interviews SET durum = 'iptal_edildi' WHERE id = ?",
                        (interview_id,)
                    )

                    logger.info(
                        f"[auto-cancel] Mulakat ID={interview_id}, Aday={ad_soyad}, "
                        f"sure doldu -- otomatik iptal edildi"
                    )

                    # 2. Aday durum guncellemesi (interviews.py cancel mantigi ile ayni)
                    # Baska aktif mulakat var mi kontrol et
                    cursor.execute("""
                        SELECT COUNT(*) as cnt FROM interviews i
                        JOIN candidates c ON c.id = i.candidate_id
                        WHERE i.candidate_id = ? AND i.durum = 'planlanmis'
                        AND c.company_id = ?
                    """, (candidate_id, company_id))
                    active_count = cursor.fetchone()['cnt']

                    if active_count > 0:
                        logger.info(
                            f"[auto-cancel] Aday ID={candidate_id} ({ad_soyad}): "
                            f"{active_count} aktif mulakat var, durum degistirilmedi"
                        )
                        audit_entries.append({
                            "company_id": company_id,
                            "entity_type": EntityType.INTERVIEW.value,
                            "entity_id": interview_id,
                            "entity_name": ad_soyad,
                            "details": {
                                "islem": "otomatik_iptal",
                                "mulakat_id": interview_id,
                                "aday_durum_degisti": False,
                                "sebep": f"{active_count} aktif mulakat mevcut"
                            }
                        })
                        iptal_sayisi += 1
                        continue

                    # Korumali durum kontrolu — ise_alindi/arsiv adaylar downgrade edilemez
                    if aday_durum in ('ise_alindi', 'arsiv'):
                        logger.info(
                            f"[auto-cancel] Aday ID={candidate_id} ({ad_soyad}): "
                            f"korumali durumda ({aday_durum}), durum degistirilmedi"
                        )
                        audit_entries.append({
                            "company_id": company_id,
                            "entity_type": EntityType.INTERVIEW.value,
                            "entity_id": interview_id,
                            "entity_name": ad_soyad,
                            "details": {
                                "islem": "otomatik_iptal",
                                "mulakat_id": interview_id,
                                "aday_durum_degisti": False,
                                "sebep": f"korumali durum: {aday_durum}"
                            }
                        })
                        iptal_sayisi += 1
                        continue

                    # Adayin gercek durumunu belirle
                    cursor.execute(
                        "SELECT COUNT(*) as cnt FROM candidate_positions WHERE candidate_id = ? AND status = 'aktif'",
                        (candidate_id,)
                    )
                    pos_count = cursor.fetchone()['cnt']

                    eski_durum = aday_durum
                    if pos_count > 0:
                        cursor.execute("""
                            UPDATE candidates
                            SET durum = 'pozisyona_atandi', havuz = 'pozisyona_aktarilan',
                                guncelleme_tarihi = datetime('now')
                            WHERE id = ? AND company_id = ?
                        """, (candidate_id, company_id))
                        yeni_durum = 'pozisyona_atandi'
                        logger.info(
                            f"[auto-cancel] Aday ID={candidate_id} ({ad_soyad}): "
                            f"durum={yeni_durum} (candidate_positions kaydi var)"
                        )
                    else:
                        cursor.execute("""
                            UPDATE candidates
                            SET durum = 'yeni', havuz = 'genel_havuz',
                                guncelleme_tarihi = datetime('now')
                            WHERE id = ? AND company_id = ?
                        """, (candidate_id, company_id))

                        # Genel Havuz'a ekle
                        cursor.execute("""
                            SELECT id FROM department_pools
                            WHERE company_id = ? AND name = 'Genel Havuz' AND is_system = 1
                        """, (company_id,))
                        genel_pool = cursor.fetchone()
                        if genel_pool:
                            cursor.execute("""
                                INSERT OR IGNORE INTO candidate_pool_assignments
                                (candidate_id, department_pool_id, company_id)
                                VALUES (?, ?, ?)
                            """, (candidate_id, genel_pool['id'], company_id))

                        yeni_durum = 'yeni'
                        logger.info(
                            f"[auto-cancel] Aday ID={candidate_id} ({ad_soyad}): "
                            f"durum={yeni_durum}, Genel Havuz'a eklendi"
                        )

                    # Audit log verisini topla (baglanti kapandiktan sonra yazilacak)
                    audit_entries.append({
                        "company_id": company_id,
                        "entity_type": EntityType.CANDIDATE.value,
                        "entity_id": candidate_id,
                        "entity_name": ad_soyad,
                        "old_values": {"durum": eski_durum},
                        "new_values": {"durum": yeni_durum},
                        "details": {
                            "islem": "otomatik_iptal",
                            "mulakat_id": interview_id,
                            "aday_durum_degisti": True,
                            "sebep": "onay suresi doldu"
                        }
                    })

                    iptal_sayisi += 1

                except Exception as e:
                    logger.error(
                        f"[auto-cancel] Mulakat iptal hatasi (interview_id={interview['id']}): {e}"
                    )

            # Tum iptalleri commit et
            conn.commit()

            logger.info(f"[auto-cancel] Toplam {iptal_sayisi} mulakat otomatik iptal edildi")

    except Exception as e:
        logger.error(f"[auto-cancel] auto_cancel_expired_interviews hatasi: {e}")

    # Audit log kayitlarini yaz (DB baglantisi kapandiktan sonra — "database is locked" onlenir)
    for entry in audit_entries:
        try:
            log_action(
                action=AuditAction.CANDIDATE_UPDATE.value,
                company_id=entry.get("company_id"),
                entity_type=entry.get("entity_type"),
                entity_id=entry.get("entity_id"),
                entity_name=entry.get("entity_name"),
                old_values=entry.get("old_values"),
                new_values=entry.get("new_values"),
                details=entry.get("details")
            )
        except Exception as e:
            logger.error(f"[auto-cancel] Audit log yazma hatasi: {e}")


def start_scheduler():
    """Scheduler'i baslat"""
    scheduler = BackgroundScheduler(timezone='Europe/Istanbul')

    # Her gun 09:00'da hatirlatma emailleri gonder
    scheduler.add_job(
        send_reminder_emails,
        CronTrigger(hour=9, minute=0),
        id='reminder_emails',
        replace_existing=True
    )

    # Her gun 09:05'te suresi dolmus mulakatlari otomatik iptal et
    scheduler.add_job(
        auto_cancel_expired_interviews,
        CronTrigger(hour=9, minute=5),
        id='auto_cancel_expired',
        replace_existing=True
    )

    scheduler.start()
    logger.info(
        "Scheduler baslatildi - 09:00 hatirlatma emaili, 09:05 otomatik iptal kontrolu"
    )
    return scheduler
