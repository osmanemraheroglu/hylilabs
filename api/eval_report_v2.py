"""Değerlendirme Raporu HTML Oluşturucu v2 - Modern Infographic Tasarım
1 A4 sayfaya sığan, SVG radar chart'lı, print-ready rapor.
"""
import base64
import re
from datetime import datetime


def extract_skills_from_text(text):
    """AI metnindeki parantez içi yazılım/beceri isimlerini ayıkla.

    Örnek: "Yapısal tasarım yazılımları (Tekla, SAP2000, ETABS) bilgisi yok"
    → ['Tekla', 'SAP2000', 'ETABS']
    """
    skills = []
    pattern = r'\(([^)]+)\)'
    matches = re.findall(pattern, text)
    for match in matches:
        items = re.split(r'[,،]\s*|\s+ve\s+', match)
        for item in items:
            item = item.strip()
            if item and len(item) <= 25 and not item.lower().startswith(('vb', 'vs', 'gibi', 'örn')):
                skills.append(item)
    return skills[:6]


def _parse_ai_sections(ai_text):
    """AI değerlendirme metnini bölümlere ayır.

    Args:
        ai_text: AI'dan gelen değerlendirme metni

    Returns:
        dict: {'guclu': [], 'eksik': [], 'genel': '', 'alternatif': []}
    """
    sections = {"guclu": [], "eksik": [], "genel": "", "alternatif": []}
    current_section = None

    for line in ai_text.split('\n'):
        # ** markdown temizle
        line = line.replace('**', '').strip()
        if not line:
            continue

        lower = line.lower()

        # Başlık tespiti: liste maddesi DEĞİL + 50 char'dan kısa + : ile biter
        is_list_item = line.startswith('-') or line.startswith('•')
        is_short = len(line) < 50
        ends_with_colon = line.endswith(':')

        if not is_list_item and is_short and ends_with_colon:
            # Başlık satırı - hangi bölüm?
            if 'güçlü' in lower or 'guclu' in lower:
                current_section = 'guclu'
            elif 'eksik' in lower or 'zayıf' in lower:
                current_section = 'eksik'
            elif 'genel' in lower and ('değerlendirme' in lower or 'degerlendirme' in lower):
                current_section = 'genel'
            elif 'alternatif' in lower or 'öneri' in lower:
                current_section = 'alternatif'
        elif is_list_item:
            # Liste maddesi
            item = line.lstrip('-•').strip()
            if item and current_section in ['guclu', 'eksik', 'alternatif']:
                sections[current_section].append(item)
        elif line and current_section == 'genel':
            # Genel değerlendirme içerik satırı
            sections['genel'] += (' ' if sections['genel'] else '') + line

    # Genel değerlendirme max 320 karakter
    if len(sections['genel']) > 320:
        sections['genel'] = sections['genel'][:320]

    return sections


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
    location_detail = v2_data.get('location_detail', '')
    critical_matched = v2_data.get('critical_matched', [])
    critical_missing = v2_data.get('critical_missing', [])
    knockout = v2_data.get('knockout', False)
    knockout_reason = v2_data.get('knockout_reason', '')

    # Renk kodlaması
    if total >= 70:
        main_color = "#22c55e"
        verdict = "Güçlü Aday"
        verdict_bg = "#dcfce7"
    elif total >= 40:
        main_color = "#f59e0b"
        verdict = "Değerlendirilebilir"
        verdict_bg = "#fef3c7"
    else:
        main_color = "#ef4444"
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

    # SVG radar chart koordinatları (pentagon) - 180x180 boyut
    import math
    def radar_point(value, angle_deg, cx=90, cy=90, max_r=70):
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

    def grid_points(pct):
        return ' '.join([radar_point(pct, a) for a in [0, 72, 144, 216, 288]])

    # AI metni işleme
    ai_sections = _parse_ai_sections(ai_text)

    # critical_missing boşsa AI metninden ayıkla
    if not critical_missing and ai_sections['eksik']:
        extracted_skills = []
        for raw_line in ai_sections['eksik']:
            skills = extract_skills_from_text(raw_line)
            extracted_skills.extend(skills)
        if extracted_skills:
            critical_missing = extracted_skills[:6]

    # Genel değerlendirme
    genel_text = ai_sections['genel'] if ai_sections['genel'] else 'Değerlendirme metni bulunamadı.'
    if len(genel_text) > 320:
        genel_text = genel_text[:320] + '...'

    # Yetkinlik tag'leri - slice kaldırıldı, tam metin
    def make_tags(items, color, bg):
        if not items:
            return '<span style="color:#94a3b8;font-size:0.65rem;">-</span>'
        return ''.join(f'<span style="background:{bg};color:{color};padding:1px 5px;border-radius:8px;font-size:0.6rem;margin:1px;display:inline-block;word-break:break-word;overflow-wrap:break-word;">{item}</span>' for item in items[:5])

    matched_tags = make_tags(critical_matched, "#166534", "#dcfce7")
    missing_tags = make_tags(critical_missing, "#991b1b", "#fef2f2")

    # Güçlü/Eksik listeler - slice kaldırıldı, tam metin
    def make_list(items, max_items=3):
        if not items:
            return '<div style="color:#94a3b8;font-size:0.65rem;">Belirtilmedi</div>'
        return ''.join(f'<div style="font-size:0.65rem;margin:1px 0;line-height:1.25;word-break:break-word;overflow-wrap:break-word;">• {item}</div>' for item in items[:max_items])

    guclu_list = make_list(ai_sections['guclu'])
    eksik_list = make_list(ai_sections['eksik'])
    alternatif_tags = make_tags(ai_sections['alternatif'][:3], "#1e40af", "#dbeafe") if ai_sections['alternatif'] else '<span style="color:#94a3b8;font-size:0.65rem;">-</span>'

    # Knockout banner
    knockout_html = f'''<div style="background:#fef2f2;border:1px solid #ef4444;border-radius:4px;padding:6px 10px;margin-bottom:8px;display:flex;align-items:center;gap:6px;">
        <span style="font-size:14px;">⛔</span>
        <div style="flex:1;word-break:break-word;overflow-wrap:break-word;"><span style="font-size:0.7rem;font-weight:600;color:#991b1b;">KNOCKOUT:</span>
        <span style="font-size:0.65rem;color:#b91c1c;">{knockout_reason[:50]}</span></div>
    </div>''' if knockout else ''

    # Progress bar helper - tek satır flex layout, tam label
    def progress_bar(value, max_val, label):
        pct = min(100, (value / max_val) * 100) if max_val else 0
        return f'''<div style="display:flex;align-items:center;gap:4px;margin:2px 0;">
            <span style="width:60px;font-size:0.65rem;color:#64748b;flex-shrink:0;">{label}</span>
            <div style="flex:1;height:5px;background:#e8e8ec;border-radius:3px;overflow:hidden;">
                <div style="height:100%;width:{pct}%;background:{main_color};border-radius:3px;"></div>
            </div>
            <span style="width:34px;text-align:right;font-size:0.65rem;font-family:'JetBrains Mono',monospace;color:#1e293b;flex-shrink:0;">{value}/{max_val}</span>
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
body {{ font-family: 'DM Sans', sans-serif; max-width: 800px; margin: 0 auto; padding: 10px; color: #1e293b; font-size: 0.7rem; line-height: 1.3; background: #fff; }}
.rpt {{ overflow: hidden; }}
.header {{ display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); border-radius: 6px; color: #fff; margin-bottom: 8px; }}
.avatar {{ width: 36px; height: 36px; background: rgba(255,255,255,0.2); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700; flex-shrink: 0; }}
.hinfo {{ flex: 1; min-width: 0; word-break: break-word; overflow-wrap: break-word; }}
.hinfo h1 {{ font-size: 0.85rem; font-weight: 600; margin-bottom: 1px; word-break: break-word; overflow-wrap: break-word; }}
.hinfo p {{ font-size: 0.65rem; opacity: 0.85; word-break: break-word; overflow-wrap: break-word; }}
.hdate {{ text-align: right; font-size: 0.6rem; opacity: 0.75; flex-shrink: 0; }}
.top {{ display: flex; gap: 10px; margin-bottom: 8px; }}
.radar-box {{ width: 180px; flex-shrink: 0; background: #f8fafc; border-radius: 6px; padding: 6px; text-align: center; overflow: hidden; }}
.radar-box svg {{ display: block; margin: 0 auto; }}
.total-display {{ margin-top: 4px; }}
.total-num {{ font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: 700; color: {main_color}; line-height: 1; }}
.total-label {{ font-size: 0.55rem; color: #64748b; }}
.verdict-badge {{ display: inline-block; background: {verdict_bg}; color: {main_color}; padding: 2px 8px; border-radius: 10px; font-size: 0.6rem; font-weight: 600; margin-top: 3px; }}
.scores-box {{ flex: 1; background: #f8fafc; border-radius: 6px; padding: 8px; min-width: 0; }}
.verdicts {{ display: flex; gap: 6px; margin-bottom: 8px; }}
.vcard {{ flex: 1; background: #f8fafc; border-radius: 6px; padding: 6px 8px; text-align: center; word-break: break-word; overflow-wrap: break-word; }}
.vcard .lbl {{ font-size: 0.55rem; color: #94a3b8; margin-bottom: 2px; }}
.vcard .val {{ font-size: 0.7rem; font-weight: 600; color: #1e293b; word-break: break-word; overflow-wrap: break-word; }}
.two-col {{ display: flex; gap: 8px; margin-bottom: 8px; }}
.two-col > div {{ flex: 1; background: #f8fafc; border-radius: 6px; padding: 8px; word-break: break-word; overflow-wrap: break-word; }}
.card-title {{ font-size: 0.6rem; font-weight: 600; color: #64748b; margin-bottom: 4px; }}
.tags {{ display: flex; flex-wrap: wrap; gap: 2px; word-break: break-word; overflow-wrap: break-word; }}
.ai-box {{ background: #f8fafc; border-radius: 6px; padding: 8px; margin-bottom: 6px; word-break: break-word; overflow-wrap: break-word; }}
.ai-title {{ font-size: 0.7rem; font-weight: 600; color: #1e3a5f; margin-bottom: 4px; display: flex; align-items: center; gap: 4px; }}
.ai-text {{ font-size: 0.65rem; color: #475569; line-height: 1.4; word-break: break-word; overflow-wrap: break-word; }}
.alt-row {{ display: flex; align-items: center; gap: 4px; margin-top: 6px; padding-top: 6px; border-top: 1px solid #e2e8f0; word-break: break-word; overflow-wrap: break-word; }}
.alt-row .lbl {{ font-size: 0.6rem; color: #64748b; flex-shrink: 0; }}
.footer {{ text-align: center; padding-top: 6px; border-top: 1px solid #e2e8f0; font-size: 0.55rem; color: #94a3b8; }}
</style>
</head>
<body>
<div class="rpt">
<div class="header">
    <div class="avatar">{initials}</div>
    <div class="hinfo">
        <h1>{candidate_name}</h1>
        <p>{position_name}</p>
    </div>
    <div class="hdate">
        <div>Değerlendirme</div>
        <div style="font-weight:600;">{eval_date}</div>
    </div>
</div>

{knockout_html}

<div class="top">
    <div class="radar-box">
        <svg width="180" height="180" viewBox="0 0 180 180">
            <polygon points="{grid_points(100)}" fill="none" stroke="#e2e8f0" stroke-width="1"/>
            <polygon points="{grid_points(75)}" fill="none" stroke="#e2e8f0" stroke-width="0.5"/>
            <polygon points="{grid_points(50)}" fill="none" stroke="#e2e8f0" stroke-width="0.5"/>
            <polygon points="{grid_points(25)}" fill="none" stroke="#e2e8f0" stroke-width="0.5"/>
            <line x1="90" y1="90" x2="90" y2="20" stroke="#e2e8f0" stroke-width="0.5"/>
            <line x1="90" y1="90" x2="156.6" y2="68.4" stroke="#e2e8f0" stroke-width="0.5"/>
            <line x1="90" y1="90" x2="131.1" y2="146.6" stroke="#e2e8f0" stroke-width="0.5"/>
            <line x1="90" y1="90" x2="48.9" y2="146.6" stroke="#e2e8f0" stroke-width="0.5"/>
            <line x1="90" y1="90" x2="23.4" y2="68.4" stroke="#e2e8f0" stroke-width="0.5"/>
            <polygon points="{radar_points}" fill="{main_color}22" stroke="{main_color}" stroke-width="2"/>
            <text x="90" y="12" text-anchor="middle" font-size="9" fill="#64748b">Poz</text>
            <text x="172" y="72" text-anchor="end" font-size="9" fill="#64748b">Teknik</text>
            <text x="138" y="162" text-anchor="middle" font-size="9" fill="#64748b">Den</text>
            <text x="42" y="162" text-anchor="middle" font-size="9" fill="#64748b">Eği</text>
            <text x="8" y="72" text-anchor="start" font-size="9" fill="#64748b">Ele</text>
        </svg>
        <div class="total-display">
            <div class="total-num">{total}</div>
            <div class="total-label">/ 100 Puan</div>
            <div class="verdict-badge">{verdict}</div>
        </div>
    </div>
    <div class="scores-box">
        {progress_bar(pos_score, 33, 'Pozisyon')}
        {progress_bar(technical_score, 37, 'Teknik')}
        {progress_bar(experience_score, 10, 'Deneyim')}
        {progress_bar(education_score, 10, 'Eğitim')}
        {progress_bar(elimination_score, 10, 'Eleme')}
    </div>
</div>

<div class="verdicts">
    <div class="vcard">
        <div class="lbl">Sonuç</div>
        <div class="val" style="color:{main_color};">{verdict}</div>
    </div>
    <div class="vcard">
        <div class="lbl">Başlık Eşleşme</div>
        <div class="val">{title_match}</div>
    </div>
    <div class="vcard">
        <div class="lbl">Lokasyon</div>
        <div class="val">{location_detail or '-'}</div>
    </div>
</div>

<div class="two-col">
    <div>
        <div class="card-title">✅ Eşleşen Yetkinlikler</div>
        <div class="tags">{matched_tags}</div>
    </div>
    <div>
        <div class="card-title">❌ Eksik Yetkinlikler</div>
        <div class="tags">{missing_tags}</div>
    </div>
</div>

<div class="two-col">
    <div>
        <div class="card-title">💪 Güçlü Yönleri</div>
        {guclu_list}
    </div>
    <div>
        <div class="card-title">⚠️ Eksiklikleri</div>
        {eksik_list}
    </div>
</div>

<div class="ai-box">
    <div class="ai-title">🤖 Genel Değerlendirme</div>
    <div class="ai-text">{genel_text}</div>
    <div class="alt-row">
        <span class="lbl">💡 Alternatif Pozisyonlar:</span>
        <div class="tags">{alternatif_tags}</div>
    </div>
</div>

<div class="footer">
    HyliLabs HR — Otomatik Değerlendirme Raporu — {eval_date}
</div>
</div>
</body>
</html>'''

    return html


def get_eval_report_b64(candidate_name, position_name, v2_data, ai_text, eval_date=None):
    """Base64 encoded HTML raporu döndür."""
    html = generate_eval_html(candidate_name, position_name, v2_data, ai_text, eval_date)
    return base64.b64encode(html.encode('utf-8')).decode()
