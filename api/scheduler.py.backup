"""
HyliLabs Scheduler
APScheduler ile zamanlanmis gorevler
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database import get_connection
from email_sender import send_interview_invite, send_email, format_turkish_date, get_interview_type_label
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


def _build_auto_cancel_email_body(iptal_listesi, sirket_adi):
    """
    Otomatik iptal bildirimi icin HTML email icerigi olusturur.
    iptal_listesi: list of dict — her iptal edilen mulakat icin bilgiler
    """
    rows_html = ""
    for item in iptal_listesi:
        tarih_str = item.get('tarih_formatted', '-')
        saat_str = item.get('saat', '-') or '-'
        tur_label = get_interview_type_label(item.get('tur', 'genel') or 'genel')
        pozisyon = item.get('position_title', '-') or 'Genel Basvuru'
        sebep = item.get('iptal_sebep', '-')

        rows_html += f"""
        <tr>
            <td style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb;">{item.get('ad_soyad', '-')}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb;">{pozisyon}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb;">{tarih_str}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb;">{saat_str}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb;">{tur_label}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb;">{sebep}</td>
        </tr>"""

    adet = len(iptal_listesi)
    bugun = format_turkish_date(datetime.now())

    body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 650px; margin: 0 auto;">
        <div style="background-color: #dc2626; padding: 16px 24px; border-radius: 8px 8px 0 0;">
            <h2 style="color: #ffffff; margin: 0; font-size: 18px;">
                Otomatik Mulakat Iptali Bildirimi
            </h2>
        </div>
        <div style="background-color: #ffffff; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
            <p style="color: #374151; font-size: 14px; line-height: 1.6;">
                Sayin {sirket_adi} IK Ekibi,
            </p>
            <p style="color: #374151; font-size: 14px; line-height: 1.6;">
                Asagidaki <strong>{adet}</strong> mulakat <strong>otomatik olarak iptal</strong> edilmistir.
            </p>

            <table style="width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px;">
                <thead>
                    <tr style="background-color: #f3f4f6;">
                        <th style="padding: 8px 12px; text-align: left; border-bottom: 2px solid #d1d5db;">Aday</th>
                        <th style="padding: 8px 12px; text-align: left; border-bottom: 2px solid #d1d5db;">Pozisyon</th>
                        <th style="padding: 8px 12px; text-align: left; border-bottom: 2px solid #d1d5db;">Tarih</th>
                        <th style="padding: 8px 12px; text-align: left; border-bottom: 2px solid #d1d5db;">Saat</th>
                        <th style="padding: 8px 12px; text-align: left; border-bottom: 2px solid #d1d5db;">Tur</th>
                        <th style="padding: 8px 12px; text-align: left; border-bottom: 2px solid #d1d5db;">Iptal Sebebi</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>

            <p style="color: #6b7280; font-size: 13px; line-height: 1.5;">
                Iptal edilen mulakatlarin adaylari, mulakat onaylamadiklari icin
                otomatik olarak arsive tasinmistir.
            </p>

            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 16px 0;" />
            <p style="color: #9ca3af; font-size: 12px;">
                Bu email {bugun} tarihinde HyliLabs sistemi tarafindan otomatik olarak gonderilmistir.
            </p>
        </div>
    </div>
    """
    return body


def auto_cancel_expired_interviews():
    """
    Her gun 09:05'te calisir.
    Onay suresi dolmus VEYA mulakat saati gecmis + onaylanmamis + hala planlanmis olan
    mulakatlari otomatik iptal eder ve aday durumunu gunceller.
    Onaylamayan adaylar arsive tasinir (Genel Havuz'a degil).
    Iptal edilen mulakatlar icin IK'ya email bildirimi gonderir.
    """
    logger.info("[auto-cancel] Otomatik iptal gorevi basladi")

    # Audit log kayitlarini topla, DB baglantisi kapandiktan sonra yaz
    # (audit_logger kendi baglantisi acar, ayni anda 2 baglanti SQLite'da "database is locked" verir)
    audit_entries = []

    # Email bildirimi icin veri topla — company_id bazli gruplama
    # {company_id: {"sirket_adi": str, "hr_email": str, "account": dict, "iptal_listesi": [...]}}
    email_data = {}

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Suresi dolmus VEYA mulakat saati gecmis, pending, planlanmis mulakatlari bul
            # Kosul 1: confirm_token_expires < datetime('now') — onay suresi dolmus
            # Kosul 2: datetime(tarih) < datetime('now') — mulakat saati gecmis
            cursor.execute("""
                SELECT i.id, i.candidate_id, i.company_id, i.tarih, i.saat, i.tur,
                       i.confirm_token_expires,
                       c.ad_soyad, c.durum as aday_durum,
                       co.ad as sirket_adi,
                       dp.name as position_title
                FROM interviews i
                JOIN candidates c ON c.id = i.candidate_id
                JOIN companies co ON co.id = i.company_id
                LEFT JOIN department_pools dp ON dp.id = i.position_id
                WHERE (
                    i.confirm_token_expires < datetime('now')
                    OR datetime(i.tarih) < datetime('now', '+3 hours')
                )
                  AND i.confirmation_status = 'pending'
                  AND i.durum = 'planlanmis'
            """)

            expired_interviews = [dict(row) for row in cursor.fetchall()]

            logger.info(f"[auto-cancel] Iptal edilecek mulakat sayisi: {len(expired_interviews)}")

            iptal_sayisi = 0
            for interview in expired_interviews:
                try:
                    interview_id = interview['id']
                    candidate_id = interview['candidate_id']
                    company_id = interview['company_id']
                    ad_soyad = interview['ad_soyad']
                    aday_durum = interview['aday_durum']

                    # Iptal sebebini belirle
                    # confirm_token_expires UTC'de saklanir, tarih Istanbul saatinde saklanir
                    now_utc = datetime.utcnow().isoformat()
                    token_expires = interview.get('confirm_token_expires') or ''
                    if token_expires and token_expires < now_utc:
                        iptal_sebep = "Onay suresi doldu"
                    else:
                        iptal_sebep = "Mulakat saati gecti"

                    # 1. Mulakati iptal et
                    cursor.execute(
                        "UPDATE interviews SET durum = 'iptal' WHERE id = ?",
                        (interview_id,)
                    )

                    logger.info(
                        f"[auto-cancel] Mulakat ID={interview_id}, Aday={ad_soyad}, "
                        f"sebep: {iptal_sebep} -- otomatik iptal edildi"
                    )

                    # Email verisi topla — tarih formatlama
                    tarih_formatted = '-'
                    try:
                        tarih_str = interview.get('tarih', '')
                        if tarih_str:
                            if isinstance(tarih_str, str):
                                if 'T' in tarih_str:
                                    tarih_dt = datetime.fromisoformat(tarih_str)
                                else:
                                    tarih_dt = datetime.strptime(tarih_str, '%Y-%m-%d')
                            else:
                                tarih_dt = tarih_str
                            tarih_formatted = format_turkish_date(tarih_dt)
                    except Exception:
                        tarih_formatted = str(interview.get('tarih', '-'))

                    # Company bazli email verisini hazirla
                    if company_id not in email_data:
                        # HR alici emailini bul
                        cursor.execute("""
                            SELECT email FROM users
                            WHERE company_id = ? AND aktif = 1
                            ORDER BY CASE WHEN rol = 'company_admin' THEN 0 ELSE 1 END
                            LIMIT 1
                        """, (company_id,))
                        hr_row = cursor.fetchone()
                        hr_email = hr_row['email'] if hr_row else None

                        # Email hesabini al
                        cursor.execute("""
                            SELECT * FROM email_accounts
                            WHERE company_id = ? AND varsayilan_gonderim = 1 AND aktif = 1
                            LIMIT 1
                        """, (company_id,))
                        acc_row = cursor.fetchone()
                        email_account = dict(acc_row) if acc_row else None

                        email_data[company_id] = {
                            "sirket_adi": interview.get('sirket_adi', ''),
                            "hr_email": hr_email,
                            "account": email_account,
                            "iptal_listesi": []
                        }

                    email_data[company_id]["iptal_listesi"].append({
                        "ad_soyad": ad_soyad,
                        "position_title": interview.get('position_title'),
                        "tarih_formatted": tarih_formatted,
                        "saat": interview.get('saat'),
                        "tur": interview.get('tur'),
                        "iptal_sebep": iptal_sebep,
                    })

                    # 2. Aday durum guncellemesi
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
                                "iptal_sebep": iptal_sebep,
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
                                "iptal_sebep": iptal_sebep,
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
                        # Onaylamayan aday arsive tasinir (Genel Havuz'a degil)
                        # candidates.py arsivle mantigi ile ayni pattern

                        # Eski havuz atamalarini sil
                        cursor.execute(
                            "DELETE FROM candidate_pool_assignments WHERE candidate_id = ? AND company_id = ?",
                            (candidate_id, company_id)
                        )

                        # Arsiv havuzunu bul
                        cursor.execute("""
                            SELECT id FROM department_pools
                            WHERE company_id = ? AND name = 'Arşiv' AND is_system = 1
                        """, (company_id,))
                        arsiv_row = cursor.fetchone()

                        if arsiv_row:
                            arsiv_pool_id = arsiv_row['id']
                            # Arsiv havuzuna ata
                            cursor.execute("""
                                INSERT INTO candidate_pool_assignments
                                (candidate_id, department_pool_id, company_id)
                                VALUES (?, ?, ?)
                            """, (candidate_id, arsiv_pool_id, company_id))
                        else:
                            logger.error(
                                f"[auto-cancel] Aday ID={candidate_id}: "
                                f"Arsiv havuzu bulunamadi (company_id={company_id})"
                            )

                        # Durumu guncelle
                        cursor.execute("""
                            UPDATE candidates
                            SET durum = 'arsiv', havuz = 'arsiv',
                                guncelleme_tarihi = datetime('now')
                            WHERE id = ? AND company_id = ?
                        """, (candidate_id, company_id))

                        yeni_durum = 'arsiv'
                        logger.info(
                            f"[auto-cancel] Aday ID={candidate_id} ({ad_soyad}): "
                            f"aday arsive tasindi (mulakat onaylanmadi)"
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
                            "iptal_sebep": iptal_sebep,
                            "aday_durum_degisti": True,
                            "sebep": iptal_sebep
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

    # IK email bildirimlerini gonder (DB baglantisi kapandiktan sonra — "database is locked" onlenir)
    for company_id, data in email_data.items():
        try:
            hr_email = data.get("hr_email")
            account = data.get("account")
            sirket_adi = data.get("sirket_adi", "")
            iptal_listesi = data.get("iptal_listesi", [])

            if not hr_email:
                logger.warning(
                    f"[auto-cancel] Sirket ID={company_id} icin IK email adresi bulunamadi, bildirim gonderilemedi"
                )
                continue

            if not account:
                logger.warning(
                    f"[auto-cancel] Sirket ID={company_id} icin email hesabi bulunamadi, bildirim gonderilemedi"
                )
                continue

            if not iptal_listesi:
                continue

            adet = len(iptal_listesi)
            subject = f"Otomatik Mulakat Iptali — {adet} mulakat iptal edildi"
            body = _build_auto_cancel_email_body(iptal_listesi, sirket_adi)

            success, msg = send_email(
                to_email=hr_email,
                subject=subject,
                body=body,
                account=account
            )

            if success:
                logger.info(
                    f"[auto-cancel] IK bildirim emaili gonderildi: {hr_email} "
                    f"({adet} iptal, sirket_id={company_id})"
                )
            else:
                logger.error(
                    f"[auto-cancel] IK bildirim emaili gonderilemedi ({hr_email}): {msg}"
                )

        except Exception as e:
            logger.error(f"[auto-cancel] IK email bildirimi hatasi (company_id={company_id}): {e}")


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
