"""
TalentFlow Email Okuyucu
IMAP ile email kutusundan CV eklerini ceker
"""

import imaplib
import email
from email.header import decode_header
from email.message import Message
from datetime import datetime
from typing import Generator
from dataclasses import dataclass

from config import EMAIL_CONFIG, SUPPORTED_EXTENSIONS


@dataclass
class EmailAttachment:
    """Email eki"""
    filename: str
    content: bytes
    content_type: str


@dataclass
class EmailMessage:
    """Email mesaji"""
    message_id: str
    sender: str
    subject: str
    date: datetime
    attachments: list[EmailAttachment]


def decode_mime_header(header_value: str) -> str:
    """MIME encoded header degerini decode et"""
    if not header_value:
        return ""

    decoded_parts = []
    for part, encoding in decode_header(header_value):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(encoding or "utf-8", errors="ignore"))
        else:
            decoded_parts.append(part)

    return "".join(decoded_parts)


def parse_email_date(date_str: str) -> datetime:
    """Email tarihini parse et"""
    if not date_str:
        return datetime.now()

    try:
        # email.utils.parsedate_to_datetime daha guvenilir
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
    except Exception:
        return datetime.now()


def is_cv_attachment(filename: str) -> bool:
    """Dosya CV olabilir mi? (uzanti kontrolu)"""
    if not filename:
        return False

    filename_lower = filename.lower()
    return any(filename_lower.endswith(ext) for ext in SUPPORTED_EXTENSIONS)


def extract_attachments(msg: Message) -> list[EmailAttachment]:
    """Email'den CV olabilecek ekleri cikar"""
    attachments = []

    for part in msg.walk():
        content_disposition = part.get("Content-Disposition", "")

        if "attachment" in content_disposition or part.get_filename():
            filename = part.get_filename()
            if filename:
                filename = decode_mime_header(filename)

            if filename and is_cv_attachment(filename):
                content = part.get_payload(decode=True)
                if content:
                    attachments.append(EmailAttachment(
                        filename=filename,
                        content=content,
                        content_type=part.get_content_type()
                    ))

    return attachments


class EmailReader:
    """IMAP email okuyucu"""

    def __init__(self, config: dict = None):
        """
        Args:
            config: Email yapilandirmasi. None ise varsayilan EMAIL_CONFIG kullanilir.
                   Beklenen anahtarlar: imap_server, imap_port, email, password, folder
        """
        self.config = config or EMAIL_CONFIG
        self.connection = None
        self.account_id = config.get("id") if config else None

    @classmethod
    def from_account(cls, account: dict) -> "EmailReader":
        """Veritabani hesabindan EmailReader olustur"""
        config = {
            "id": account.get("id"),
            "imap_server": account["imap_server"],
            "imap_port": account.get("imap_port", 993),
            "email": account["email"],
            "password": account["sifre"],
            "folder": "INBOX"
        }
        return cls(config)

    def connect(self) -> bool:
        """IMAP sunucusuna baglan"""
        try:
            self.connection = imaplib.IMAP4_SSL(
                self.config["imap_server"],
                self.config["imap_port"]
            )
            self.connection.login(
                self.config["email"],
                self.config["password"]
            )
            return True
        except Exception as e:
            print(f"Email baglanti hatasi: {e}")
            return False

    def disconnect(self):
        """Baglantivi kapat"""
        if self.connection:
            try:
                self.connection.logout()
            except Exception:
                pass
            self.connection = None

    def list_folders(self) -> list[dict]:
        """
        IMAP klasorlerini listele

        Returns:
            Liste of dict: Her klasor icin {"name": str, "flags": str, "delimiter": str}
        """
        if not self.connection:
            if not self.connect():
                return []

        folders = []
        try:
            status, folder_list = self.connection.list()
            if status != "OK":
                return []

            for folder_data in folder_list:
                if folder_data:
                    # Folder formatı: (flags) "delimiter" "name"
                    try:
                        if isinstance(folder_data, bytes):
                            folder_str = folder_data.decode('utf-8')
                        else:
                            folder_str = str(folder_data)

                        # Parse folder info
                        import re
                        match = re.match(r'\(([^)]*)\)\s+"([^"]+)"\s+"?([^"]+)"?', folder_str)
                        if match:
                            flags = match.group(1)
                            delimiter = match.group(2)
                            name = match.group(3).strip('"')

                            # Ozel karakterleri decode et (IMAP modified UTF-7)
                            try:
                                if '&' in name:
                                    # IMAP modified UTF-7 decode
                                    import codecs
                                    name = name.replace('&-', '&').replace(',', '/')
                                    # Basit decode denemesi
                                    decoded_name = name
                                    for part in name.split('&'):
                                        if part and '/' in part:
                                            try:
                                                b64_part = part.split('-')[0] if '-' in part else part
                                                decoded_name = decoded_name.replace(f'&{part}',
                                                    codecs.decode(b64_part.replace(',', '/'), 'utf-7'))
                                            except:
                                                pass
                            except:
                                pass

                            folders.append({
                                "name": name,
                                "flags": flags,
                                "delimiter": delimiter,
                                "display_name": self._get_folder_display_name(name)
                            })
                    except Exception as e:
                        print(f"Klasor parse hatasi: {e}")
                        continue

        except Exception as e:
            print(f"Klasor listeleme hatasi: {e}")

        return folders

    def _get_folder_display_name(self, folder_name: str) -> str:
        """Klasor icin kullanici dostu isim dondur"""
        # Bilinen klasor isimleri
        known_folders = {
            "INBOX": "📥 Gelen Kutusu",
            "Inbox": "📥 Gelen Kutusu",
            "Sent": "📤 Gönderilenler",
            "SENT": "📤 Gönderilenler",
            "Sent Items": "📤 Gönderilenler",
            "Sent Messages": "📤 Gönderilenler",
            "[Gmail]/Sent Mail": "📤 Gönderilenler",
            "[Gmail]/G&APY-nderilmi&AV8- postalar": "📤 Gönderilenler",
            "Drafts": "📝 Taslaklar",
            "DRAFTS": "📝 Taslaklar",
            "[Gmail]/Drafts": "📝 Taslaklar",
            "Trash": "🗑️ Çöp Kutusu",
            "TRASH": "🗑️ Çöp Kutusu",
            "[Gmail]/Trash": "🗑️ Çöp Kutusu",
            "Spam": "⚠️ Spam",
            "SPAM": "⚠️ Spam",
            "[Gmail]/Spam": "⚠️ Spam",
            "Junk": "⚠️ Spam",
            "Archive": "📦 Arşiv",
            "[Gmail]/All Mail": "📬 Tüm Postalar",
            "[Gmail]/Important": "⭐ Önemli",
            "[Gmail]/Starred": "⭐ Yıldızlı"
        }

        if folder_name in known_folders:
            return known_folders[folder_name]

        # Gmail klasorleri
        if folder_name.startswith("[Gmail]/"):
            return f"📁 {folder_name.replace('[Gmail]/', '')}"

        return f"📁 {folder_name}"

    def fetch_emails_with_attachments(
        self,
        folder: str = None,
        unseen_only: bool = True,
        limit: int = 50
    ) -> Generator[EmailMessage, None, None]:
        """
        Ekli emailleri getir

        Args:
            folder: Email klasoru (default: config'den)
            unseen_only: Sadece okunmamis emailleri getir
            limit: Maksimum email sayisi
        """
        if not self.connection:
            if not self.connect():
                return

        folder = folder or self.config["folder"]

        try:
            # Klasoru sec
            status, _ = self.connection.select(folder)
            if status != "OK":
                print(f"Klasor secilemedi: {folder}")
                return

            # Arama kriteri
            search_criteria = "UNSEEN" if unseen_only else "ALL"
            status, messages = self.connection.search(None, search_criteria)

            if status != "OK":
                return

            message_ids = messages[0].split()

            # Son N emaili al (en yeniler)
            message_ids = message_ids[-limit:] if len(message_ids) > limit else message_ids

            for msg_id in message_ids:
                try:
                    # Email'i fetch et
                    status, msg_data = self.connection.fetch(msg_id, "(RFC822)")

                    if status != "OK":
                        continue

                    # Email'i parse et
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Ekleri cikar
                    attachments = extract_attachments(msg)

                    # CV eki yoksa atla
                    if not attachments:
                        continue

                    # Message ID
                    message_id = msg.get("Message-ID", str(msg_id))

                    yield EmailMessage(
                        message_id=message_id,
                        sender=decode_mime_header(msg.get("From", "")),
                        subject=decode_mime_header(msg.get("Subject", "")),
                        date=parse_email_date(msg.get("Date")),
                        attachments=attachments
                    )

                except Exception as e:
                    print(f"Email islenirken hata (ID: {msg_id}): {e}")
                    continue

        except Exception as e:
            print(f"Email fetch hatasi: {e}")

    def mark_as_seen(self, message_id: str):
        """Emaili okundu olarak isaretle"""
        if self.connection:
            try:
                # Bu basitletirilmis bir versiyon
                # Gercek uygulamada message_id ile eslestirme gerekir
                pass
            except Exception:
                pass

    def test_connection(self) -> tuple[bool, str]:
        """Baglanti testi yap"""
        try:
            if not self.config["email"] or not self.config["password"]:
                return False, "Email veya sifre ayarlanmamis"

            if self.connect():
                # Inbox'i sec ve email sayisini al
                status, data = self.connection.select(self.config["folder"])
                if status == "OK":
                    email_count = int(data[0])
                    self.disconnect()
                    return True, f"Baglanti basarili. {email_count} email mevcut."
                else:
                    self.disconnect()
                    return False, "Klasor secilemedi"
            else:
                return False, "Baglanti kurulamadi"

        except imaplib.IMAP4.error as e:
            return False, f"IMAP hatasi: {str(e)}"
        except Exception as e:
            return False, f"Beklenmeyen hata: {str(e)}"


# Tekil instance (geriye uyumluluk icin)
email_reader = EmailReader()


def test_imap_connection(
    imap_server: str,
    imap_port: int,
    email_addr: str,
    password: str
) -> tuple[bool, str]:
    """Belirli ayarlarla IMAP baglanti testi yap"""
    try:
        connection = imaplib.IMAP4_SSL(imap_server, imap_port)
        connection.login(email_addr, password)
        status, data = connection.select("INBOX")
        if status == "OK":
            email_count = int(data[0])
            connection.logout()
            return True, f"Baglanti basarili. {email_count} email mevcut."
        else:
            connection.logout()
            return False, "Klasor secilemedi"
    except imaplib.IMAP4.error as e:
        return False, f"IMAP hatasi: {str(e)}"
    except Exception as e:
        return False, f"Beklenmeyen hata: {str(e)}"


def get_imap_folders(account: dict) -> tuple[bool, list[dict], str]:
    """
    Email hesabi icin IMAP klasorlerini listele

    Args:
        account: Email hesabi dict'i (imap_server, imap_port, email, sifre)

    Returns:
        (success, folders, message)
    """
    try:
        reader = EmailReader.from_account(account)
        if not reader.connect():
            return False, [], "Baglanti kurulamadi"

        folders = reader.list_folders()
        reader.disconnect()

        if not folders:
            return False, [], "Klasorler alinamadi"

        return True, folders, f"{len(folders)} klasor bulundu"

    except Exception as e:
        return False, [], f"Hata: {str(e)}"
