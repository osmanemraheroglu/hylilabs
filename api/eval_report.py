"""Degerlendirme Raporu HTML Olusturucu - v2 Puan + AI Degerlendirme"""
import base64
from datetime import datetime


def generate_eval_html(candidate_name, position_name, v2_data, ai_text, eval_date=None):
    if not eval_date:
        eval_date = datetime.now().strftime("%d.%m.%Y %H:%M")
    
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
    
    if total >= 70:
        sc = "#22c55e"
    elif total >= 50:
        sc = "#f59e0b"
    else:
        sc = "#ef4444"
    
    ai_html = ai_text.replace('\n', '<br>')
    for old, new in [('**Güçlü Yönleri:**','<b>Güçlü Yönleri:</b>'),('**Guclu Yonleri:**','<b>Güçlü Yönleri:</b>'),('**Eksiklikleri:**','<b>Eksiklikleri:</b>'),('**Genel Değerlendirme:**','<b>Genel Değerlendirme:</b>'),('**Genel Degerlendirme:**','<b>Genel Değerlendirme:</b>'),('**Alternatif Pozisyonlar:**','<b>Alternatif Pozisyonlar:</b>')]:
        ai_html = ai_html.replace(old, new)
    
    ko_html = f'<div style="background:#fef2f2;border:1px solid #ef4444;border-radius:6px;padding:10px;margin:10px 0;color:#991b1b;"><b>⛔ KNOCKOUT:</b> {knockout_reason}</div>' if knockout else ''
    
    match_chips = ' '.join(f'<span style="background:#dcfce7;color:#166534;padding:2px 8px;border-radius:12px;font-size:12px;margin:2px;">{k["keyword"] if isinstance(k, dict) else k}</span>' for k in (critical_matched[:8] if critical_matched else []))
    miss_chips = ' '.join(f'<span style="background:#fef2f2;color:#991b1b;padding:2px 8px;border-radius:12px;font-size:12px;margin:2px;">{k}</span>' for k in (critical_missing[:8] if critical_missing else []))
    
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Rapor - {candidate_name}</title>
<style>
body{{font-family:Arial,sans-serif;max-width:850px;margin:0 auto;padding:25px;color:#1a1a1a;line-height:1.5;}}
.hdr{{background:#1e3a5f;color:#fff;padding:18px 22px;border-radius:10px;margin-bottom:20px;}}
.hdr h1{{margin:0;font-size:19px;}} .hdr p{{margin:3px 0;font-size:13px;opacity:.9;}}
.row{{display:flex;gap:15px;margin-bottom:18px;}}
.total-box{{background:{sc}10;border:2px solid {sc};border-radius:10px;padding:15px;text-align:center;min-width:120px;}}
.total-box .n{{font-size:40px;font-weight:bold;color:{sc};}} .total-box .l{{font-size:12px;color:{sc};font-weight:600;}}
.scores{{flex:1;display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;}}
.sc{{background:#f1f5f9;border-radius:7px;padding:8px 10px;text-align:center;}}
.sc .n{{font-size:20px;font-weight:bold;color:#1e293b;}} .sc .l{{font-size:11px;color:#64748b;}}
.sec{{background:#f8fafc;border-radius:8px;padding:14px;margin-bottom:12px;}}
.sec h3{{margin:0 0 6px 0;font-size:14px;color:#334155;}}
.ai{{border:1px solid #e2e8f0;border-radius:8px;padding:18px;margin-top:15px;line-height:1.7;}}
.ai h2{{margin:0 0 10px 0;font-size:17px;color:#1e3a5f;}}
.ft{{text-align:center;margin-top:20px;padding-top:12px;border-top:1px solid #e2e8f0;font-size:11px;color:#94a3b8;}}
</style></head><body>
<div class="hdr"><h1>📊 Aday Değerlendirme Raporu</h1>
<p><b>Aday:</b> {candidate_name} &nbsp;|&nbsp; <b>Pozisyon:</b> {position_name} &nbsp;|&nbsp; <b>Tarih:</b> {eval_date}</p></div>

<div class="row">
<div class="total-box"><div class="n">{total}</div><div class="l">/100</div></div>
<div class="scores">
<div class="sc"><div class="n">{pos_score}</div><div class="l">Pozisyon /33</div></div>
<div class="sc"><div class="n">{technical_score}</div><div class="l">Teknik /37</div></div>
<div class="sc"><div class="n">{experience_score}</div><div class="l">Deneyim /10</div></div>
<div class="sc"><div class="n">{education_score}</div><div class="l">Eğitim /10</div></div>
<div class="sc"><div class="n">{elimination_score}</div><div class="l">Eleme /10</div></div>
<div class="sc"><div class="n" style="font-size:14px;">{title_match}</div><div class="l">Başlık Eşleşme</div></div>
</div></div>

{ko_html}

<div class="sec"><h3>📌 Detaylar</h3>
<table style="width:100%;font-size:13px;border-collapse:collapse;">
<tr><td style="padding:3px 0;color:#64748b;">Eşleşen Başlık:</td><td><b>{matched_title or '-'}</b></td></tr>
<tr><td style="padding:3px 0;color:#64748b;">Sektör:</td><td>{sector_detail or '-'}</td></tr>
<tr><td style="padding:3px 0;color:#64748b;">Lokasyon:</td><td>{location_detail or '-'}</td></tr>
</table></div>

<div class="sec"><h3>✅ Eşleşen Kritik Yetkinlikler</h3>
<div style="display:flex;flex-wrap:wrap;gap:4px;">{match_chips or '<em style="color:#94a3b8;">Yok</em>'}</div></div>

<div class="sec"><h3>❌ Eksik Kritik Yetkinlikler</h3>
<div style="display:flex;flex-wrap:wrap;gap:4px;">{miss_chips or '<em style="color:#94a3b8;">Yok</em>'}</div></div>

<div class="ai"><h2>🤖 AI Değerlendirme</h2>{ai_html}</div>
<div class="ft">TalentFlow HR — Otomatik Değerlendirme Raporu — {eval_date}</div>
</body></html>"""
    return html


def get_eval_report_b64(candidate_name, position_name, v2_data, ai_text, eval_date=None):
    html = generate_eval_html(candidate_name, position_name, v2_data, ai_text, eval_date)
    return base64.b64encode(html.encode('utf-8')).decode()
