# -*- coding: utf-8 -*-
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
import json
import sqlite3

# Turkce font
pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DejaVuBold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
FONT = 'DejaVu'
FONT_B = 'DejaVuBold'

# Renkler
PRIMARY = colors.HexColor('#1E3A5F')
SECONDARY = colors.HexColor('#3498DB')
SUCCESS = colors.HexColor('#27AE60')
WARNING = colors.HexColor('#F39C12')
DANGER = colors.HexColor('#E74C3C')
LIGHT = colors.HexColor('#F8F9FA')

DB_PATH = '/var/www/hylilabs/api/data/talentflow.db'

def get_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""SELECT id, name, keywords, gerekli_deneyim_yil, gerekli_egitim, lokasyon
        FROM department_pools WHERE pool_type='position' AND keywords IS NOT NULL LIMIT 5""")
    positions = [dict(r) for r in c.fetchall()]

    c.execute("""SELECT position_id, title, category FROM approved_title_mappings WHERE is_approved=1""")
    tm = {}
    for r in c.fetchall():
        pid = r['position_id']
        if pid not in tm:
            tm[pid] = {'exact': [], 'close': [], 'partial': []}
        if r['category'] in tm[pid]:
            tm[pid][r['category']].append(r['title'])

    c.execute("""SELECT position_id, keyword, category, priority FROM position_keywords_v2""")
    kw = {}
    for r in c.fetchall():
        pid = r['position_id']
        if pid not in kw:
            kw[pid] = {'must_have': [], 'critical': [], 'important': [], 'bonus': []}
        cat = r['priority'] or r['category'] or 'important'
        if cat in kw[pid]:
            kw[pid][cat].append(r['keyword'])

    c.execute("""
        SELECT c.id, c.ad_soyad, c.mevcut_pozisyon, c.teknik_beceriler,
               c.toplam_deneyim_yil, c.egitim, c.lokasyon,
               m.uyum_puani, m.beceri_puani, m.deneyim_puani, m.egitim_puani, m.detayli_analiz,
               dp.name as position_name
        FROM candidates c
        JOIN matches m ON c.id = m.candidate_id
        JOIN department_pools dp ON m.position_id = dp.id
        ORDER BY m.uyum_puani DESC LIMIT 12""")
    candidates = [dict(r) for r in c.fetchall()]

    conn.close()
    return positions, tm, kw, candidates

def create_pie_chart():
    d = Drawing(300, 200)
    pie = Pie()
    pie.x = 80
    pie.y = 30
    pie.width = 120
    pie.height = 120
    pie.data = [33, 37, 20, 10]
    pie.labels = ['Pozisyon %33', 'Teknik %37', 'Yetkinlik %20', 'Eleme %10']
    pie.slices.strokeWidth = 0.5
    pie.slices[0].fillColor = PRIMARY
    pie.slices[1].fillColor = SUCCESS
    pie.slices[2].fillColor = WARNING
    pie.slices[3].fillColor = DANGER
    pie.slices[0].popout = 5
    d.add(pie)
    return d

def create_bar_chart(candidates):
    d = Drawing(700, 250)
    bc = VerticalBarChart()
    bc.x = 50
    bc.y = 50
    bc.width = 600
    bc.height = 150

    scores = [int(c['uyum_puani'] or 0) for c in candidates[:9]]
    names = [c['ad_soyad'].split()[0][:8] for c in candidates[:9]]

    bc.data = [scores]
    bc.categoryAxis.categoryNames = names
    bc.categoryAxis.labels.fontName = FONT
    bc.categoryAxis.labels.fontSize = 8
    bc.categoryAxis.labels.angle = 30
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = 60
    bc.valueAxis.valueStep = 10
    bc.bars[0].fillColor = SECONDARY
    bc.bars[0].strokeWidth = 0

    for i, score in enumerate(scores):
        x = bc.x + (i + 0.5) * (bc.width / len(scores))
        y = bc.y + (score / 60) * bc.height + 5
        d.add(String(x, y, str(score), fontName=FONT_B, fontSize=9, textAnchor='middle'))

    d.add(bc)
    return d

def create_pdf():
    doc = SimpleDocTemplate("/home/claude/HyliLabs_Puanlama_Sunum_v2.pdf",
        pagesize=landscape(A4), rightMargin=1*cm, leftMargin=1*cm, topMargin=1*cm, bottomMargin=1*cm)

    styles = getSampleStyleSheet()
    title_s = ParagraphStyle('T', fontName=FONT_B, fontSize=24, textColor=PRIMARY, spaceAfter=15, alignment=1)
    head_s = ParagraphStyle('H', fontName=FONT_B, fontSize=14, textColor=PRIMARY, spaceBefore=10, spaceAfter=6)
    sub_s = ParagraphStyle('S', fontName=FONT_B, fontSize=11, textColor=SECONDARY, spaceBefore=6, spaceAfter=4)
    body_s = ParagraphStyle('B', fontName=FONT, fontSize=9, spaceBefore=2, spaceAfter=2)

    positions, tm, kw, candidates = get_data()
    story = []

    # KAPAK
    story.append(Spacer(1, 1.5*inch))
    story.append(Paragraph("HyliLabs", title_s))
    story.append(Paragraph("Aday-Pozisyon Eslestirme ve Puanlama Sistemi", head_s))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("Detayli Teknik Degerlendirme Raporu", sub_s))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("Analiz: {} Pozisyon, {} Aday".format(len(positions), len(candidates)), body_s))
    story.append(Paragraph("Tarih: 26 Subat 2026", body_s))
    story.append(PageBreak())

    # ICINDEKILER
    story.append(Paragraph("Icindekiler", title_s))
    toc = [["1.", "Puanlama Sistemi Genel Bakis", "3"],
        ["2.", "Puan Kategorileri ve Dagilimi", "4"],
        ["3.", "Pozisyon Detaylari", "5-7"],
        ["4.", "Aday Degerlendirme Raporlari", "8-16"],
        ["5.", "Karsilastirmali Sonuclar", "17-18"]]
    t = Table(toc, colWidths=[0.5*inch, 5*inch, 0.8*inch])
    t.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), FONT), ('FONTSIZE', (0,0), (-1,-1), 11),
        ('TEXTCOLOR', (0,0), (-1,-1), PRIMARY), ('BOTTOMPADDING', (0,0), (-1,-1), 8)]))
    story.append(t)
    story.append(PageBreak())

    # PUANLAMA + PIE
    story.append(Paragraph("1. Puanlama Sistemi Genel Bakis", title_s))
    story.append(Paragraph("Sistem, adaylari 4 ana kategoride degerlendirir:", body_s))
    score_data = [["Kategori", "Max", "Agirlik", "Aciklama"],
        ["Pozisyon Uyumu", "33", "%33", "Unvan eslesmesi, sektor, kidem"],
        ["Teknik Beceriler", "37", "%37", "Must-have, Critical, Important keyword"],
        ["Genel Yetkinlik", "20", "%20", "Deneyim yili (10) + Egitim (10)"],
        ["Eleme Kriterleri", "10", "%10", "Lokasyon ve ozel gereksinimler"],
        ["TOPLAM", "100", "%100", "-"]]
    t = Table(score_data, colWidths=[1.8*inch, 0.8*inch, 0.8*inch, 4*inch])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), PRIMARY), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,-1), FONT), ('FONTSIZE', (0,0), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.gray), ('ALIGN', (1,0), (2,-1), 'CENTER'),
        ('BACKGROUND', (0,-1), (-1,-1), LIGHT), ('FONTNAME', (0,-1), (-1,-1), FONT_B)]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("Puan Dagilimi Grafigi:", head_s))
    story.append(create_pie_chart())
    story.append(PageBreak())

    # KEYWORD
    story.append(Paragraph("2. Keyword Eslestirme Sistemi", title_s))
    story.append(Paragraph("Turkce - Ingilizce Synonym Ornekleri:", head_s))
    syn_data = [["Turkce Keyword", "Ingilizce Esdegerleri"],
        ["bakim-onarim", "maintenance, repair"],
        ["is makinalari", "heavy equipment, construction machinery"],
        ["proje yonetimi", "project management"],
        ["onleyici bakim", "preventive maintenance"],
        ["kalite kontrol", "quality control, QC"],
        ["ekipman yonetimi", "equipment management"]]
    t = Table(syn_data, colWidths=[2.5*inch, 5*inch])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), WARNING), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,-1), FONT), ('FONTSIZE', (0,0), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.gray), ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT])]))
    story.append(t)
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("3 Katmanli Eslestirme:", head_s))
    story.append(Paragraph("1. Exact Match: Birebir kelime eslesmesi", body_s))
    story.append(Paragraph("2. Synonym Match: 78 anahtar kelimelik TR-EN sozluk", body_s))
    story.append(Paragraph("3. Fuzzy Match: %80+ benzerlik orani", body_s))
    story.append(PageBreak())

    # POZISYONLAR
    for i, pos in enumerate(positions[:3]):
        story.append(Paragraph("3.{} Pozisyon: {}".format(i+1, pos['name']), title_s))
        basic = [["Ozellik", "Deger"],
            ["Pozisyon ID", str(pos['id'])],
            ["Gerekli Deneyim", "{} yil".format(pos['gerekli_deneyim_yil'] or 0)],
            ["Gerekli Egitim", pos['gerekli_egitim'] or "Belirtilmemis"],
            ["Lokasyon", pos['lokasyon'] or "Belirtilmemis"]]
        bt = Table(basic, colWidths=[1.5*inch, 3*inch])
        bt.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), PRIMARY), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,-1), FONT), ('GRID', (0,0), (-1,-1), 0.5, colors.gray)]))
        story.append(bt)
        story.append(Spacer(1, 0.15*inch))

        if pos['id'] in kw:
            k = kw[pos['id']]
            story.append(Paragraph("Aranan Keywords:", head_s))
            kw_data = [["Oncelik", "Anahtar Kelimeler"]]
            if k['must_have']: kw_data.append(["Must-Have", ", ".join(k['must_have'][:6])])
            if k['critical']: kw_data.append(["Critical", ", ".join(k['critical'][:8])])
            if k['important']: kw_data.append(["Important", ", ".join(k['important'][:6])])
            if k['bonus']: kw_data.append(["Bonus", ", ".join(k['bonus'][:4])])
            kt = Table(kw_data, colWidths=[1.8*inch, 5.5*inch])
            kt.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), SUCCESS), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,-1), FONT), ('FONTSIZE', (0,0), (-1,-1), 9),
                ('GRID', (0,0), (-1,-1), 0.5, colors.gray)]))
            story.append(kt)

        if pos['id'] in tm:
            t_m = tm[pos['id']]
            story.append(Spacer(1, 0.15*inch))
            story.append(Paragraph("AI Esdeger Unvanlar:", head_s))
            tm_data = [["Tip", "Unvanlar"]]
            if t_m['exact']: tm_data.append(["Exact", ", ".join(t_m['exact'][:5])])
            if t_m['close']: tm_data.append(["Close", ", ".join(t_m['close'][:5])])
            tmt = Table(tm_data, colWidths=[1.8*inch, 5.5*inch])
            tmt.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), SECONDARY), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,-1), FONT), ('FONTSIZE', (0,0), (-1,-1), 9),
                ('GRID', (0,0), (-1,-1), 0.5, colors.gray)]))
            story.append(tmt)
        story.append(PageBreak())

    # ADAYLAR
    for i, cand in enumerate(candidates[:9]):
        story.append(Paragraph("4.{} Aday: {}".format(i+1, cand['ad_soyad']), title_s))
        story.append(Paragraph("Pozisyon: {}".format(cand['position_name']), sub_s))

        cd = [["Ozellik", "Deger"],
            ["Mevcut Pozisyon", cand['mevcut_pozisyon'] or "-"],
            ["Toplam Deneyim", "{} yil".format(cand['toplam_deneyim_yil'] or 0)],
            ["Egitim", cand['egitim'] or "-"],
            ["Lokasyon", cand['lokasyon'] or "-"]]
        ct = Table(cd, colWidths=[1.5*inch, 4*inch])
        ct.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), PRIMARY), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,-1), FONT), ('GRID', (0,0), (-1,-1), 0.5, colors.gray)]))
        story.append(ct)
        story.append(Spacer(1, 0.1*inch))

        if cand['teknik_beceriler']:
            skills = cand['teknik_beceriler'][:180] + "..." if len(cand['teknik_beceriler'] or "") > 180 else cand['teknik_beceriler']
            story.append(Paragraph("<b>Teknik Beceriler:</b> {}".format(skills), body_s))

        story.append(Paragraph("Puan Dagilimi:", head_s))
        total = cand['uyum_puani'] or 0
        tech = cand['beceri_puani'] or 0
        exp = cand['deneyim_puani'] or 0
        edu = cand['egitim_puani'] or 0

        sd = [["Kategori", "Puan", "Max", "Yuzde"],
            ["TOPLAM UYUM", str(int(total)), "100", "%{}".format(int(total))],
            ["Teknik Beceri", str(int(tech)), "37", "%{}".format(int(tech/37*100) if tech else 0)],
            ["Deneyim", str(int(exp)), "10", "%{}".format(int(exp/10*100) if exp else 0)],
            ["Egitim", str(int(edu)), "10", "%{}".format(int(edu/10*100) if edu else 0)]]
        bg = colors.HexColor('#D4EDDA') if total >= 40 else colors.HexColor('#FFF3CD') if total >= 25 else colors.HexColor('#F8D7DA')
        st = Table(sd, colWidths=[1.5*inch, 0.8*inch, 0.8*inch, 0.8*inch])
        st.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), SUCCESS), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,-1), FONT), ('ALIGN', (1,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.gray), ('BACKGROUND', (0,1), (-1,1), bg)]))
        story.append(st)

        if cand['detayli_analiz']:
            try:
                d = json.loads(cand['detayli_analiz'])
                story.append(Spacer(1, 0.1*inch))
                story.append(Paragraph("Detayli Analiz:", head_s))
                if d.get('critical_matched'):
                    story.append(Paragraph("<b>Eslesen Critical:</b> {}".format(", ".join(d['critical_matched'][:5])), body_s))
                if d.get('important_matched'):
                    story.append(Paragraph("<b>Eslesen Important:</b> {}".format(", ".join(d['important_matched'][:4])), body_s))
                if d.get('critical_missing'):
                    story.append(Paragraph("<b>Eksik Critical:</b> {}".format(", ".join(d['critical_missing'][:5])), body_s))
                if d.get('title_match_level'):
                    level = d['title_match_level']
                    level_tr = {'exact': 'Birebir', 'close': 'Yakin', 'partial': 'Kismi', 'none': 'Yok'}.get(level, level)
                    story.append(Paragraph("<b>Unvan Eslesmesi:</b> {}".format(level_tr), body_s))
            except: pass

        story.append(Spacer(1, 0.1*inch))
        if total >= 40:
            story.append(Paragraph("<b>Degerlendirme:</b> Mulakata cagrilabilir", body_s))
        elif total >= 25:
            story.append(Paragraph("<b>Degerlendirme:</b> IK degerlendirmesi onerilir", body_s))
        else:
            story.append(Paragraph("<b>Degerlendirme:</b> Pozisyon icin uygun degil", body_s))

        story.append(PageBreak())

    # KARSILASTIRMA
    story.append(Paragraph("5. Karsilastirmali Sonuclar", title_s))
    sum_data = [["Aday", "Pozisyon", "Toplam", "Teknik", "Deneyim", "Egitim", "Durum"]]
    for cand in candidates[:12]:
        total = cand['uyum_puani'] or 0
        status = "Uygun" if total >= 40 else "Degerlendir" if total >= 25 else "Dusuk"
        sum_data.append([cand['ad_soyad'][:20], (cand['position_name'] or "")[:18],
            str(int(total)), str(int(cand['beceri_puani'] or 0)),
            str(int(cand['deneyim_puani'] or 0)), str(int(cand['egitim_puani'] or 0)), status])
    sumt = Table(sum_data, colWidths=[2*inch, 2*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.7*inch, 1.1*inch])
    sumt.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), PRIMARY), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), FONT_B), ('FONTNAME', (0,1), (-1,-1), FONT),
        ('FONTSIZE', (0,0), (-1,-1), 8), ('ALIGN', (2,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.gray), ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT])]))
    story.append(sumt)
    story.append(PageBreak())

    # BAR CHART
    story.append(Paragraph("Aday Skorlari Karsilastirmasi", title_s))
    story.append(Spacer(1, 0.2*inch))
    story.append(create_bar_chart(candidates))
    story.append(Spacer(1, 0.3*inch))

    scores = [c['uyum_puani'] or 0 for c in candidates]
    story.append(Paragraph("Ozet Istatistikler:", head_s))
    stats_data = [["Metrik", "Deger"],
        ["Toplam Aday", str(len(candidates))],
        ["Ortalama Skor", "{:.1f}".format(sum(scores)/len(scores))],
        ["En Yuksek Skor", "{:.0f}".format(max(scores))],
        ["En Dusuk Skor", "{:.0f}".format(min(scores))],
        ["Mulakata Uygun (>=40)", str(len([s for s in scores if s >= 40]))],
        ["Degerlendirilmeli (25-39)", str(len([s for s in scores if 25 <= s < 40]))]]
    st = Table(stats_data, colWidths=[2.5*inch, 1.5*inch])
    st.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), PRIMARY), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,-1), FONT), ('GRID', (0,0), (-1,-1), 0.5, colors.gray),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT])]))
    story.append(st)

    doc.build(story)
    print("PDF olusturuldu: /home/claude/HyliLabs_Puanlama_Sunum_v2.pdf")

if __name__ == "__main__":
    create_pdf()
