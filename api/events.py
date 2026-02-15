"""
TalentFlow - Event/Hook sistemi
Workflow entegrasyonu ve agent sistemi için altyapı

Event'ler tüm önemli işlemleri loglar ve ileride
- Webhook entegrasyonları
- Real-time bildirimler
- Audit logging
- Agent tetiklemeleri
için kullanılabilir.
"""

from datetime import datetime
from typing import Callable, Dict, Any, List
import json

# Event handler registry
EVENT_HANDLERS: Dict[str, List[Callable]] = {
    # CV İşlemleri
    "cv_uploaded": [],
    "cv_parsed": [],
    "cv_parse_failed": [],
    "cv_parse_error": [],
    "cv_process_error": [],

    # Aday İşlemleri
    "candidate_created": [],
    "candidate_updated": [],
    "candidate_deleted": [],
    "candidate_matched": [],
    "candidate_duplicate_found": [],
    "candidate_duplicate_merged": [],
    "candidate_status_changed": [],
    "status_change_error": [],
    "bulk_status_change_started": [],
    "bulk_status_change_completed": [],

    # Başvuru İşlemleri
    "application_received": [],
    "application_created": [],
    "application_error": [],

    # Eşleştirme İşlemleri
    "matching_started": [],
    "matching_completed": [],
    "matching_error": [],
    "auto_matching_started": [],
    "auto_matching_completed": [],
    "auto_matching_error": [],
    "criteria_matching_started": [],
    "criteria_matching_completed": [],

    # Havuz İşlemleri
    "pool_candidate_added": [],
    "pool_candidate_removed": [],
    "pool_status_changed": [],

    # Pozisyon İşlemleri
    "position_created": [],
    "position_updated": [],
    "position_deleted": [],
    "position_closed": [],

    # Mülakat İşlemleri
    "interview_scheduled": [],
    "interview_updated": [],
    "interview_cancelled": [],
    "interview_completed": [],
    "interview_reminder_sent": [],

    # Workflow İşlemleri
    "workflow_started": [],
    "workflow_completed": [],
    "workflow_error": [],

    # Bildirim İşlemleri
    "notification_sent": [],
    "email_sent": [],

    # Sistem İşlemleri
    "user_login": [],
    "user_logout": [],
    "settings_changed": [],
    "api_limit_warning": [],
}

# Event log (in-memory, son 1000 event)
EVENT_LOG: List[Dict[str, Any]] = []
MAX_LOG_SIZE = 1000


def register_handler(event_name: str, handler_func: Callable) -> bool:
    """
    Event handler kaydet

    Args:
        event_name: Event adı
        handler_func: Handler fonksiyonu

    Returns:
        bool: Başarılı mı
    """
    if event_name not in EVENT_HANDLERS:
        # Yeni event tipi oluştur
        EVENT_HANDLERS[event_name] = []

    if handler_func not in EVENT_HANDLERS[event_name]:
        EVENT_HANDLERS[event_name].append(handler_func)
        return True
    return False


def unregister_handler(event_name: str, handler_func: Callable) -> bool:
    """
    Event handler kaldır

    Args:
        event_name: Event adı
        handler_func: Handler fonksiyonu

    Returns:
        bool: Başarılı mı
    """
    if event_name in EVENT_HANDLERS and handler_func in EVENT_HANDLERS[event_name]:
        EVENT_HANDLERS[event_name].remove(handler_func)
        return True
    return False


def trigger_event(event_name: str, data: Dict[str, Any]) -> None:
    """
    Event tetikle, tüm handler'ları çalıştır

    Args:
        event_name: Event adı
        data: Event verisi
    """
    # Event'i logla
    log_entry = {
        "event": event_name,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }

    EVENT_LOG.append(log_entry)

    # Log boyutunu kontrol et
    if len(EVENT_LOG) > MAX_LOG_SIZE:
        EVENT_LOG.pop(0)

    # Event tipi yoksa oluştur
    if event_name not in EVENT_HANDLERS:
        EVENT_HANDLERS[event_name] = []
        return

    # Handler'ları çalıştır
    for handler in EVENT_HANDLERS[event_name]:
        try:
            handler(data)
        except Exception as e:
            print(f"Event handler error ({event_name}): {e}")


def get_event_log(event_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Event loglarını getir

    Args:
        event_name: Filtrelenecek event adı (None = tümü)
        limit: Maksimum kayıt sayısı

    Returns:
        list: Event logları
    """
    if event_name:
        filtered = [e for e in EVENT_LOG if e["event"] == event_name]
        return filtered[-limit:]
    return EVENT_LOG[-limit:]


def clear_event_log() -> None:
    """Event loglarını temizle"""
    EVENT_LOG.clear()


def get_event_stats() -> Dict[str, int]:
    """Event istatistiklerini getir"""
    stats = {}
    for entry in EVENT_LOG:
        event_name = entry["event"]
        stats[event_name] = stats.get(event_name, 0) + 1
    return stats


def get_registered_events() -> List[str]:
    """Kayıtlı event tiplerini getir"""
    return list(EVENT_HANDLERS.keys())


# ============================================================
# ÖRNEK HANDLER'LAR
# ============================================================

def log_to_console(data: Dict[str, Any]) -> None:
    """Konsola loglama handler"""
    print(f"[EVENT] {datetime.now().strftime('%H:%M:%S')} - {json.dumps(data, ensure_ascii=False)[:200]}")


def log_candidate_created(data: Dict[str, Any]) -> None:
    """Aday oluşturulduğunda loglama"""
    print(f"[CANDIDATE] Yeni aday: {data.get('ad_soyad')} (ID: {data.get('candidate_id')})")


def log_status_changed(data: Dict[str, Any]) -> None:
    """Durum değişikliği loglama"""
    print(f"[STATUS] {data.get('candidate_name')}: {data.get('old_status')} -> {data.get('new_status')}")


def log_matching_completed(data: Dict[str, Any]) -> None:
    """Eşleştirme tamamlandığında loglama"""
    print(f"[MATCH] Aday {data.get('candidate_id')}: {data.get('match_count')} eşleşme bulundu")


# ============================================================
# WEBHOOK HANDLER (İleride kullanılacak)
# ============================================================

class WebhookHandler:
    """Webhook gönderen handler sınıfı"""

    def __init__(self, webhook_url: str, events: List[str] = None):
        self.webhook_url = webhook_url
        self.events = events or []

    def __call__(self, data: Dict[str, Any]) -> None:
        """Webhook'u tetikle"""
        # TODO: HTTP POST isteği gönder
        # import requests
        # requests.post(self.webhook_url, json=data, timeout=5)
        pass


# ============================================================
# EVENT LISTENER DECORATOR
# ============================================================

def on_event(event_name: str):
    """
    Event listener decorator

    Kullanım:
    @on_event("candidate_created")
    def my_handler(data):
        print(f"Yeni aday: {data}")
    """
    def decorator(func: Callable):
        register_handler(event_name, func)
        return func
    return decorator


# ============================================================
# VARSAYILAN HANDLER'LAR (Debug modunda aktif)
# ============================================================

# Debug modunda tüm event'leri konsola yazdır
DEBUG_MODE = False

if DEBUG_MODE:
    for event_name in EVENT_HANDLERS:
        register_handler(event_name, log_to_console)
