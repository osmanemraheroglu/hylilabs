"""Değerlendirme Raporu HTML Oluşturucu v2 - Modern Infographic Tasarım
1 A4 sayfaya sığan, SVG radar chart'lı, print-ready rapor.
"""
import base64
from datetime import datetime


def generate_eval_html(candidate_name, position_name, v2_data, ai_text, eval_date=None):
    """Modern infographic değerlendirme raporu oluştur.

    Args:
        candidate_name: Aday adı soyadı
        position_name: Pozisyon adı
        v2_data: Skor verileri dict
        ai_text: AI değerlendirme metni
        eval_date: Değerlendirme tarihi (opsiyonel)

    Returns:
        HTML string
    """
    if not eval_date:
        eval_date = datetime.now().strftime("%d.%m.%Y %H:%M")

    # Skorları al
    total = v2_data.get('total', 0)
    pos_score = v2_data.get('pos_score', 0)
    technical_score = v2_data.get('technical_score', 0)
    experience_score = v2_data.get('experience_score', 0)
    education_score = v2_data.get('education_score', 0)
    elimination_score = v2_data.get('elimination_score', 0)
    title_match = v2_data.get('title_match_level', '-')
    matched_title = v2_data.get('matched_title', '')
    sector_detail = v2_data.get('sector_detail', '')
    location_detail = v2_data.get('location_detail', '')
    critical_matched = v2_data.get('critical_matched', [])
    critical_missing = v2_data.get('critical_missing', [])
    knockout = v2_data.get('knockout', False)
    knockout_reason = v2_data.get('knockout_reason', '')

    # Renk kodlaması
    if total >= 70:
        main_color = "#22c55e"  # Yeşil
        verdict = "Güçlü Aday"
        verdict_bg = "#dcfce7"
    elif total >= 40:
        main_color = "#f59e0b"  # Turuncu
        verdict = "Değerlendirilebilir"
        verdict_bg = "#fef3c7"
    else:
        main_color = "#ef4444"  # Kırmızı
        verdict = "Uygun Değil"
        verdict_bg = "#fef2f2"

    # Avatar (baş harfler)
    initials = ''.join([n[0].upper() for n in candidate_name.split()[:2]]) if candidate_name else "?"

    # Radar chart için normalize (0-100 arası)
    radar_pos = min(100, (pos_score / 33) * 100) if pos_score else 0
    radar_tech = min(100, (technical_score / 37) * 100) if technical_score else 0
    radar_exp = min(100, (experience_score / 10) * 100) if experience_score else 0
    radar_edu = min(100, (education_score / 10) * 100) if education_score else 0
    radar_elim = min(100, (elimination_score / 10) * 100) if elimination_score else 0

    # SVG radar chart koordinatları (pentagon)
    import math
    def radar_point(value, angle_deg, cx=60, cy=60, max_r=45):
        angle_rad = math.radians(angle_deg - 90)
        r = (value / 100) * max_r
        x = cx + r * math.cos(angle_rad)
        y = cy + r * math.sin(angle_rad)
        return f"{x:.1f},{y:.1f}"

    radar_points = ' '.join([
        radar_point(radar_pos, 0),
        radar_point(radar_tech, 72),
        radar_point(radar_exp, 144),
        radar_point(radar_edu, 216),
        radar_point(radar_elim, 288)
    ])

    # Grid çizgileri için
    def grid_points(pct):
        return ' '.join([radar_point(pct, a) for a in [0, 72, 144, 216, 288]])

    # AI metni işleme
    ai_sections = {"guclu": [], "eksik": [], "genel": "", "alternatif": []}
    current_section = None

    for line in ai_text.split('\n'):
        line = line.strip()
        lower = line.lower()
        if 'güçlü' in lower or 'guclu' in lower:
            current_section = 'guclu'
        elif 'eksik' in lower:
            current_section = 'eksik'
        elif 'genel' in lower and 'değerlendirme' in lower.replace('ğ','g'):
            current_section = 'genel'
        elif 'alternatif' in lower:
            current_section = 'alternatif'
        elif line.startswith('-') or line.startswith('•'):
            item = line.lstrip('-•').strip()
            if item and current_section in ['guclu', 'eksik', 'alternatif']:
                ai_sections[current_section].append(item)
        elif line and current_section == 'genel' and not line.endswith(':'):
            ai_sections['genel'] += (' ' if ai_sections['genel'] else '') + line

    # Genel değerlendirme max 320 karakter
    genel_text = ai_sections['genel'][:320] + ('...' if len(ai_sections['genel']) > 320 else '')

    # Yetkinlik tag'leri
    def make_tags(items, color, bg):
        return ''.join(f'<span style="background:{bg};color:{color};padding:2px 6px;border-radius:10px;font-size:9px;margin:1px;display:inline-block;">{item[:20]}</span>' for item in items[:6])

    matched_tags = make_tags(critical_matched, "#166534", "#dcfce7") if critical_matched else '<em style="color:#94a3b8;font-size:9px;">-</em>'
    missing_tags = make_tags(critical_missing, "#991b1b", "#fef2f2") if critical_missing else '<em style="color:#94a3b8;font-size:9px;">-</em>'

    # Güçlü/Eksik listeler
    def make_list(items, max_items=3):
        return ''.join(f'<div style="font-size:9px;margin:2px 0;line-height:1.3;">• {item[:40]}</div>' for item in items[:max_items])

    guclu_list = make_list(ai_sections['guclu']) or '<em style="color:#94a3b8;font-size:9px;">Belirtilmedi</em>'
    eksik_list = make_list(ai_sections['eksik']) or '<em style="color:#94a3b8;font-size:9px;">Belirtilmedi</em>'
    alternatif_list = ', '.join(ai_sections['alternatif'][:2]) if ai_sections['alternatif'] else '-'

    # Knockout banner
    knockout_html = f'''<div style="background:#fef2f2;border:2px solid #ef4444;border-radius:6px;padding:8px 12px;margin:8px 0;display:flex;align-items:center;gap:8px;">
        <span style="font-size:18px;">⛔</span>
        <div><div style="font-size:10px;font-weight:600;color:#991b1b;">KNOCKOUT</div>
        <div style="font-size:9px;color:#b91c1c;">{knockout_reason[:60]}</div></div>
    </div>''' if knockout else ''

    # Progress bar helper
    def progress_bar(value, max_val, label):
        pct = min(100, (value / max_val) * 100) if max_val else 0
        return f'''<div style="margin:3px 0;">
            <div style="display:flex;justify-content:space-between;font-size:8px;color:#64748b;margin-bottom:1px;">
                <span>{label}</span><span style="font-family:'JetBrains Mono',monospace;">{value}/{max_val}</span>
            </div>
            <div style="background:#e2e8f0;border-radius:2px;height:6px;overflow:hidden;">
                <div style="background:{main_color};width:{pct}%;height:100%;border-radius:2px;"></div>
            </div>
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>Rapor - {candidate_name}</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
@page {{ size: A4; margin: 6mm; }}
@media print {{ body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }} }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'DM Sans', sans-serif; max-width: 210mm; margin: 0 auto; padding: 12px; color: #1e293b; font-size: 10px; line-height: 1.4; background: #fff; }}
.header {{ display: flex; align-items: center; gap: 12px; padding: 10px 14px; background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); border-radius: 8px; color: #fff; margin-bottom: 10px; }}
.avatar {{ width: 42px; height: 42px; background: rgba(255,255,255,0.2); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 700; }}
.header-info {{ flex: 1; }}
.header-info h1 {{ font-size: 14px; font-weight: 600; margin-bottom: 2px; }}
.header-info p {{ font-size: 9px; opacity: 0.85; }}
.header-date {{ text-align: right; font-size: 8px; opacity: 0.75; }}
.main-grid {{ display: grid; grid-template-columns: 140px 1fr; gap: 10px; }}
.left-col {{ display: flex; flex-direction: column; gap: 8px; }}
.card {{ background: #f8fafc; border-radius: 6px; padding: 10px; }}
.card-title {{ font-size: 9px; font-weight: 600; color: #64748b; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }}
.total-score {{ text-align: center; padding: 12px; }}
.total-num {{ font-family: 'JetBrains Mono', monospace; font-size: 36px; font-weight: 700; color: {main_color}; line-height: 1; }}
.total-label {{ font-size: 10px; color: #64748b; margin-top: 2px; }}
.verdict {{ display: inline-block; background: {verdict_bg}; color: {main_color}; padding: 3px 10px; border-radius: 12px; font-size: 9px; font-weight: 600; margin-top: 6px; }}
.radar-wrap {{ display: flex; justify-content: center; }}
.right-col {{ display: flex; flex-direction: column; gap: 8px; }}
.verdicts {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }}
.verdict-card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px; text-align: center; }}
.verdict-card .label {{ font-size: 8px; color: #94a3b8; margin-bottom: 3px; }}
.verdict-card .value {{ font-size: 11px; font-weight: 600; color: #1e293b; }}
.scores-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
.tags-section {{ display: flex; flex-wrap: wrap; gap: 2px; }}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
.ai-section {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; margin-top: 8px; }}
.ai-title {{ font-size: 10px; font-weight: 600; color: #1e3a5f; margin-bottom: 6px; display: flex; align-items: center; gap: 4px; }}
.ai-text {{ font-size: 9px; color: #475569; line-height: 1.5; }}
.footer {{ text-align: center; margin-top: 10px; padding-top: 8px; border-top: 1px solid #e2e8f0; font-size: 8px; color: #94a3b8; }}
</style>
</head>
<body>
<div class="header">
    <div class="avatar">{initials}</div>
    <div class="header-info">
        <h1>{candidate_name}</h1>
        <p>{position_name}</p>
    </div>
    <div class="header-date">
        <div>Değerlendirme Tarihi</div>
        <div style="font-weight:600;">{eval_date}</div>
    </div>
</div>

{knockout_html}

<div class="main-grid">
    <div class="left-col">
        <div class="card total-score">
            <div class="total-num">{total}</div>
            <div class="total-label">/ 100 Puan</div>
            <div class="verdict">{verdict}</div>
        </div>

        <div class="card">
            <div class="card-title">Yetkinlik Radarı</div>
            <div class="radar-wrap">
                <svg width="120" height="120" viewBox="0 0 120 120">
                    <polygon points="{grid_points(100)}" fill="none" stroke="#e2e8f0" stroke-width="1"/>
                    <polygon points="{grid_points(75)}" fill="none" stroke="#e2e8f0" stroke-width="0.5"/>
                    <polygon points="{grid_points(50)}" fill="none" stroke="#e2e8f0" stroke-width="0.5"/>
                    <polygon points="{grid_points(25)}" fill="none" stroke="#e2e8f0" stroke-width="0.5"/>
                    <line x1="60" y1="60" x2="60" y2="15" stroke="#e2e8f0" stroke-width="0.5"/>
                    <line x1="60" y1="60" x2="102.8" y2="45.9" stroke="#e2e8f0" stroke-width="0.5"/>
                    <line x1="60" y1="60" x2="86.5" y2="99.4" stroke="#e2e8f0" stroke-width="0.5"/>
                    <line x1="60" y1="60" x2="33.5" y2="99.4" stroke="#e2e8f0" stroke-width="0.5"/>
                    <line x1="60" y1="60" x2="17.2" y2="45.9" stroke="#e2e8f0" stroke-width="0.5"/>
                    <polygon points="{radar_points}" fill="{main_color}20" stroke="{main_color}" stroke-width="2"/>
                    <text x="60" y="8" text-anchor="middle" font-size="7" fill="#64748b">Poz</text>
                    <text x="110" y="48" text-anchor="start" font-size="7" fill="#64748b">Tek</text>
                    <text x="92" y="108" text-anchor="middle" font-size="7" fill="#64748b">Den</text>
                    <text x="28" y="108" text-anchor="middle" font-size="7" fill="#64748b">Eği</text>
                    <text x="10" y="48" text-anchor="end" font-size="7" fill="#64748b">Ele</text>
                </svg>
            </div>
        </div>

        <div class="card">
            <div class="card-title">Puan Dağılımı</div>
            {progress_bar(pos_score, 33, 'Pozisyon')}
            {progress_bar(technical_score, 37, 'Teknik')}
            {progress_bar(experience_score, 10, 'Deneyim')}
            {progress_bar(education_score, 10, 'Eğitim')}
            {progress_bar(elimination_score, 10, 'Eleme')}
        </div>
    </div>

    <div class="right-col">
        <div class="verdicts">
            <div class="verdict-card">
                <div class="label">Sonuç</div>
                <div class="value" style="color:{main_color};">{verdict}</div>
            </div>
            <div class="verdict-card">
                <div class="label">Başlık Eşleşme</div>
                <div class="value">{title_match}</div>
            </div>
            <div class="verdict-card">
                <div class="label">Lokasyon</div>
                <div class="value">{location_detail or '-'}</div>
            </div>
        </div>

        <div class="scores-grid">
            <div class="card">
                <div class="card-title">✅ Eşleşen Yetkinlikler</div>
                <div class="tags-section">{matched_tags}</div>
            </div>
            <div class="card">
                <div class="card-title">❌ Eksik Yetkinlikler</div>
                <div class="tags-section">{missing_tags}</div>
            </div>
        </div>

        <div class="two-col">
            <div class="card">
                <div class="card-title">💪 Güçlü Yönleri</div>
                {guclu_list}
            </div>
            <div class="card">
                <div class="card-title">⚠️ Eksiklikleri</div>
                {eksik_list}
            </div>
        </div>

        <div class="card">
            <div class="card-title">📋 Detaylar</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:9px;">
                <div><span style="color:#94a3b8;">Eşleşen Başlık:</span> <b>{matched_title or '-'}</b></div>
                <div><span style="color:#94a3b8;">Sektör:</span> {sector_detail or '-'}</div>
                <div><span style="color:#94a3b8;">Alternatif Poz.:</span> {alternatif_list}</div>
            </div>
        </div>
    </div>
</div>

<div class="ai-section">
    <div class="ai-title">🤖 AI Genel Değerlendirme</div>
    <div class="ai-text">{genel_text or 'Değerlendirme metni bulunamadı.'}</div>
</div>

<div class="footer">
    HyliLabs HR — Otomatik Değerlendirme Raporu — {eval_date}
</div>
</body>
</html>'''

    return html


def get_eval_report_b64(candidate_name, position_name, v2_data, ai_text, eval_date=None):
    """Base64 encoded HTML raporu döndür."""
    html = generate_eval_html(candidate_name, position_name, v2_data, ai_text, eval_date)
    return base64.b64encode(html.encode('utf-8')).decode()
