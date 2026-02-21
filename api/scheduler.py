"""
HyliLabs Scheduler
APScheduler ile zamanlanmis gorevler
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database import get_connection
from email_sender import send_interview_invite
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

    scheduler.start()
    logger.info("Scheduler baslatildi - her gun 09:00'da hatirlatma emaili gonderilecek")
    return scheduler
