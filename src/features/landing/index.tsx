import { useEffect, useRef, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'

/* ─── İkonlar (inline SVG) ─── */
const icons = {
  cv: (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
  ),
  match: (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/><line x1="11" y1="8" x2="11" y2="14"/></svg>
  ),
  pool: (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
  ),
  calendar: (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
  ),
  ai: (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2a4 4 0 0 1 4 4v1h1a3 3 0 0 1 3 3v1a3 3 0 0 1-3 3h-1v4a4 4 0 0 1-8 0v-4H7a3 3 0 0 1-3-3v-1a3 3 0 0 1 3-3h1V6a4 4 0 0 1 4-4z"/><circle cx="9" cy="10" r="1"/><circle cx="15" cy="10" r="1"/></svg>
  ),
  shield: (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
  ),
  check: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
  ),
  arrow: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
  ),
  menu: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
  ),
  close: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
  ),
  mail: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
  ),
  phone: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.362 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.338 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
  ),
  location: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
  ),
}

/* ─── Veri ─── */
const features = [
  { icon: icons.cv, title: 'AI CV Analizi', desc: 'Yapay zeka ile CV\'leri saniyeler içinde analiz edin. Aday yetkinliklerini, deneyimlerini ve eğitim bilgilerini otomatik çıkarın.' },
  { icon: icons.match, title: 'Akıllı Eşleştirme', desc: 'Pozisyon gereksinimlerinize en uygun adayları %95 doğruluk oranıyla eşleştirin. Keyword bazlı ve semantik analiz birlikte çalışır.' },
  { icon: icons.pool, title: 'Havuz Yönetimi', desc: 'Adaylarınızı genel havuz, pozisyon havuzları ve arşiv olarak organize edin. Otomatik kategorizasyon ile veri kaybını önleyin.' },
  { icon: icons.calendar, title: 'Mülakat Planlama', desc: 'Mülakat takvimi oluşturun, adaylara otomatik davetiye gönderin. Onay takibi ve hatırlatma emaillerini yönetin.' },
  { icon: icons.ai, title: 'AI Değerlendirme', desc: 'Çoklu AI modeli (Claude, Gemini, OpenAI) ile adayları değerlendirin. Konsensüs bazlı puanlama ile objektif sonuçlar alın.' },
  { icon: icons.shield, title: 'KVKK Uyumlu', desc: 'Tüm süreçlerde KVKK uyumluluğu sağlanır. Aydınlatma metni, açık rıza ve audit log mekanizmaları yerleşiktir.' },
]

const steps = [
  { num: '01', title: 'CV Toplama', desc: 'Email veya manuel yükleme ile CV\'leri toplayın. Otomatik PDF dönüşümü ve AI ile veri çıkarma.' },
  { num: '02', title: 'Akıllı Eşleştirme', desc: '100 puanlık skorlama sistemi ile adayları pozisyonlarla eşleştirin. Teknik beceri, deneyim ve uyum analizi.' },
  { num: '03', title: 'Değerlendirme', desc: 'AI destekli çoklu model değerlendirmesi. Mülakat planlama ve İK notları ile kapsamlı aday profili.' },
  { num: '04', title: 'İşe Alım', desc: 'En uygun adayı seçin, işe alım sürecini tamamlayın. Tüm geçmiş veriler arşivde korunur.' },
]

const plans = [
  {
    name: 'Başlangıç',
    price: 'Yakında',
    desc: 'Küçük ekipler için ideal',
    features: ['10 aktif pozisyon', '500 aday kapasitesi', 'AI CV analizi', 'Email entegrasyonu', 'Temel raporlama'],
    highlight: false,
  },
  {
    name: 'Profesyonel',
    price: 'Yakında',
    desc: 'Büyüyen şirketler için',
    features: ['Sınırsız pozisyon', '5.000 aday kapasitesi', 'Çoklu AI değerlendirme', 'Mülakat yönetimi', 'Gelişmiş raporlama', 'Öncelikli destek'],
    highlight: true,
  },
  {
    name: 'Kurumsal',
    price: 'Yakında',
    desc: 'Büyük organizasyonlar için',
    features: ['Sınırsız her şey', 'Özel AI modeli eğitimi', 'API erişimi', 'Çoklu firma desteği', 'SLA garantisi', '7/24 destek'],
    highlight: false,
  },
]

const navLinks = [
  { label: 'Ana Sayfa', href: '#hero' },
  { label: 'Özellikler', href: '#ozellikler' },
  { label: 'Nasıl Çalışır?', href: '#nasil-calisir' },
  { label: 'Fiyatlandırma', href: '#fiyatlandirma' },
  { label: 'İletişim', href: '#iletisim' },
]

/* ─── Scroll Reveal Hook ─── */
function useReveal() {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true) },
      { threshold: 0.15 }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return { ref, visible }
}

function RevealSection({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  const { ref, visible } = useReveal()
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(32px)',
        transition: 'opacity 0.7s cubic-bezier(.16,1,.3,1), transform 0.7s cubic-bezier(.16,1,.3,1)',
      }}
    >
      {children}
    </div>
  )
}

/* ─── Ana Bileşen ─── */
export function LandingPage() {
  const navigate = useNavigate()
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [formData, setFormData] = useState({ ad: '', email: '', sirket: '', mesaj: '' })
  const [formSending, setFormSending] = useState(false)
  const [formSent, setFormSent] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  function scrollTo(id: string) {
    setMobileOpen(false)
    const el = document.getElementById(id.replace('#', ''))
    if (el) el.scrollIntoView({ behavior: 'smooth' })
  }

  function handleFormSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormSending(true)
    // Simüle — gerçek API entegrasyonu sonra eklenecek
    setTimeout(() => {
      setFormSending(false)
      setFormSent(true)
      setFormData({ ad: '', email: '', sirket: '', mesaj: '' })
    }, 1200)
  }

  return (
    <div style={{ fontFamily: "'DM Sans', 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", color: '#0B1222' }}>

      {/* ─── Google Fonts ─── */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,100..1000;1,9..40,100..1000&family=Outfit:wght@300;400;500;600;700;800&display=swap');

        .landing-gradient-text {
          background: linear-gradient(135deg, #1746A2, #2563EB, #3B82F6);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }
        .landing-gradient-bg {
          background: linear-gradient(135deg, #1746A2 0%, #2563EB 50%, #3B82F6 100%);
        }
        .landing-gradient-bg-hover:hover {
          background: linear-gradient(135deg, #123D8F 0%, #1D4ED8 50%, #2563EB 100%);
        }
        .landing-card-hover {
          transition: transform 0.3s cubic-bezier(.16,1,.3,1), box-shadow 0.3s ease;
        }
        .landing-card-hover:hover {
          transform: translateY(-6px);
          box-shadow: 0 20px 40px rgba(23,70,162,0.12);
        }
        .landing-hero-pattern {
          background-image: radial-gradient(circle at 20% 50%, rgba(37,99,235,0.06) 0%, transparent 50%),
                            radial-gradient(circle at 80% 20%, rgba(23,70,162,0.05) 0%, transparent 40%),
                            radial-gradient(circle at 60% 80%, rgba(59,130,246,0.04) 0%, transparent 40%);
        }
        @keyframes landing-float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-10px); }
        }
        .landing-stat-item { animation: landing-float 4s ease-in-out infinite; }
        .landing-stat-item:nth-child(2) { animation-delay: 0.5s; }
        .landing-stat-item:nth-child(3) { animation-delay: 1s; }
        .landing-stat-item:nth-child(4) { animation-delay: 1.5s; }
      `}</style>

      {/* ═══════════ NAVBAR ═══════════ */}
      <nav
        style={{
          position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50,
          background: scrolled ? 'rgba(255,255,255,0.85)' : 'transparent',
          backdropFilter: scrolled ? 'blur(16px)' : 'none',
          borderBottom: scrolled ? '1px solid rgba(23,70,162,0.08)' : '1px solid transparent',
          transition: 'all 0.3s ease',
        }}
      >
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 72 }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }} onClick={() => scrollTo('#hero')}>
            <img src="/images/Logo_400x120.png" alt="HyliLabs" style={{ height: 56, width: 'auto' }} />
          </div>

          {/* Desktop Links */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 32 }} className="landing-nav-desktop">
            {navLinks.map(link => (
              <button
                key={link.href}
                onClick={() => scrollTo(link.href)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 15, fontWeight: 500, color: '#5A6B82', padding: '4px 0', transition: 'color 0.2s' }}
                onMouseEnter={e => (e.currentTarget.style.color = '#1746A2')}
                onMouseLeave={e => (e.currentTarget.style.color = '#5A6B82')}
              >
                {link.label}
              </button>
            ))}
          </div>

          {/* Desktop CTA */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }} className="landing-nav-desktop">
            <button
              onClick={() => navigate({ to: '/sign-in' })}
              style={{ background: 'none', border: '1.5px solid #1746A2', borderRadius: 8, padding: '8px 20px', fontSize: 14, fontWeight: 600, color: '#1746A2', cursor: 'pointer', transition: 'all 0.2s' }}
              onMouseEnter={e => { e.currentTarget.style.background = '#1746A2'; e.currentTarget.style.color = '#fff' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'none'; e.currentTarget.style.color = '#1746A2' }}
            >
              Giriş Yap
            </button>
            <button
              onClick={() => scrollTo('#iletisim')}
              className="landing-gradient-bg landing-gradient-bg-hover"
              style={{ border: 'none', borderRadius: 8, padding: '8px 20px', fontSize: 14, fontWeight: 600, color: '#fff', cursor: 'pointer', transition: 'all 0.2s' }}
            >
              Demo Talep Et
            </button>
          </div>

          {/* Mobile Hamburger */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            style={{ display: 'none', background: 'none', border: 'none', cursor: 'pointer', color: '#0B1222' }}
            className="landing-nav-mobile-btn"
          >
            {mobileOpen ? icons.close : icons.menu}
          </button>
        </div>

        {/* Mobile Menu */}
        {mobileOpen && (
          <div style={{ background: '#fff', borderTop: '1px solid #e5e7eb', padding: '16px 24px' }} className="landing-nav-mobile-menu">
            {navLinks.map(link => (
              <button
                key={link.href}
                onClick={() => scrollTo(link.href)}
                style={{ display: 'block', width: '100%', textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, fontWeight: 500, color: '#5A6B82', padding: '12px 0', borderBottom: '1px solid #f3f4f6' }}
              >
                {link.label}
              </button>
            ))}
            <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
              <button
                onClick={() => navigate({ to: '/sign-in' })}
                style={{ flex: 1, background: 'none', border: '1.5px solid #1746A2', borderRadius: 8, padding: '10px', fontSize: 14, fontWeight: 600, color: '#1746A2', cursor: 'pointer' }}
              >
                Giriş Yap
              </button>
              <button
                onClick={() => scrollTo('#iletisim')}
                className="landing-gradient-bg"
                style={{ flex: 1, border: 'none', borderRadius: 8, padding: '10px', fontSize: 14, fontWeight: 600, color: '#fff', cursor: 'pointer' }}
              >
                Demo Talep Et
              </button>
            </div>
          </div>
        )}

        {/* Responsive CSS */}
        <style>{`
          @media (max-width: 768px) {
            .landing-nav-desktop { display: none !important; }
            .landing-nav-mobile-btn { display: block !important; }
          }
          @media (min-width: 769px) {
            .landing-nav-mobile-menu { display: none !important; }
          }
        `}</style>
      </nav>

      {/* ═══════════ HERO ═══════════ */}
      <section id="hero" className="landing-hero-pattern" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', paddingTop: 72 }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '80px 24px', textAlign: 'center', width: '100%' }}>
          <RevealSection>
            <div style={{ display: 'inline-block', padding: '6px 16px', borderRadius: 100, background: 'rgba(23,70,162,0.08)', fontSize: 13, fontWeight: 600, color: '#1746A2', marginBottom: 24, letterSpacing: '0.02em' }}>
              Türkiye'nin AI Destekli İK Platformu
            </div>
          </RevealSection>

          <RevealSection>
            <h1 style={{ fontFamily: "'Outfit', sans-serif", fontSize: 'clamp(36px, 5vw, 64px)', fontWeight: 800, lineHeight: 1.1, marginBottom: 24, maxWidth: 800, marginLeft: 'auto', marginRight: 'auto' }}>
              İşe Alım Sürecinizi{' '}
              <span className="landing-gradient-text">Yapay Zeka</span>{' '}
              ile Dönüştürün
            </h1>
          </RevealSection>

          <RevealSection>
            <p style={{ fontSize: 'clamp(16px, 2vw, 20px)', color: '#5A6B82', maxWidth: 640, margin: '0 auto 40px', lineHeight: 1.6 }}>
              CV analizi, aday eşleştirme, mülakat planlama ve değerlendirme süreçlerinizi
              tek bir platformda yapay zeka ile yönetin. Doğru adayı daha hızlı bulun.
            </p>
          </RevealSection>

          <RevealSection>
            <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 64 }}>
              <button
                onClick={() => scrollTo('#iletisim')}
                className="landing-gradient-bg landing-gradient-bg-hover"
                style={{ border: 'none', borderRadius: 12, padding: '14px 32px', fontSize: 16, fontWeight: 600, color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, transition: 'all 0.2s', boxShadow: '0 4px 16px rgba(23,70,162,0.3)' }}
              >
                Demo Talep Et {icons.arrow}
              </button>
              <button
                onClick={() => scrollTo('#ozellikler')}
                style={{ background: '#fff', border: '1.5px solid #e2e8f0', borderRadius: 12, padding: '14px 32px', fontSize: 16, fontWeight: 600, color: '#0B1222', cursor: 'pointer', transition: 'all 0.2s', boxShadow: '0 2px 8px rgba(0,0,0,0.04)' }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = '#1746A2'; e.currentTarget.style.color = '#1746A2' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.color = '#0B1222' }}
              >
                Özellikleri Keşfet
              </button>
            </div>
          </RevealSection>

          {/* İstatistik Bandı */}
          <RevealSection>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 'clamp(24px, 4vw, 64px)', flexWrap: 'wrap' }}>
              {[
                { value: '%95', label: 'Eşleştirme Doğruluğu' },
                { value: '10x', label: 'Daha Hızlı Analiz' },
                { value: '100+', label: 'AI Değerlendirme Kriteri' },
                { value: '%100', label: 'KVKK Uyumlu' },
              ].map((stat, i) => (
                <div key={i} className="landing-stat-item" style={{ textAlign: 'center' }}>
                  <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: 'clamp(28px, 3vw, 40px)', fontWeight: 800 }} className="landing-gradient-text">{stat.value}</div>
                  <div style={{ fontSize: 14, color: '#5A6B82', fontWeight: 500, marginTop: 4 }}>{stat.label}</div>
                </div>
              ))}
            </div>
          </RevealSection>
        </div>
      </section>

      {/* ═══════════ ÖZELLİKLER ═══════════ */}
      <section id="ozellikler" style={{ padding: '100px 24px', background: '#f8fafc' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <RevealSection>
            <div style={{ textAlign: 'center', marginBottom: 64 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#1746A2', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>ÖZELLİKLER</div>
              <h2 style={{ fontFamily: "'Outfit', sans-serif", fontSize: 'clamp(28px, 3vw, 42px)', fontWeight: 700, marginBottom: 16 }}>
                İşe Alımda <span className="landing-gradient-text">Güçlü Araçlar</span>
              </h2>
              <p style={{ fontSize: 17, color: '#5A6B82', maxWidth: 560, margin: '0 auto' }}>
                Tüm işe alım süreçlerinizi tek platformdan yönetin
              </p>
            </div>
          </RevealSection>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 24 }}>
            {features.map((f, i) => (
              <RevealSection key={i}>
                <div
                  className="landing-card-hover"
                  style={{
                    background: '#fff', borderRadius: 16, padding: 32, border: '1px solid #e2e8f0',
                    borderTop: '3px solid transparent',
                    position: 'relative', overflow: 'hidden',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.borderTopColor = '#2563EB')}
                  onMouseLeave={e => (e.currentTarget.style.borderTopColor = 'transparent')}
                >
                  <div style={{ width: 56, height: 56, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(23,70,162,0.08)', color: '#1746A2', marginBottom: 20 }}>
                    {f.icon}
                  </div>
                  <h3 style={{ fontFamily: "'Outfit', sans-serif", fontSize: 20, fontWeight: 600, marginBottom: 10 }}>{f.title}</h3>
                  <p style={{ fontSize: 15, color: '#5A6B82', lineHeight: 1.6, margin: 0 }}>{f.desc}</p>
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════ NASIL ÇALIŞIR ═══════════ */}
      <section id="nasil-calisir" style={{ padding: '100px 24px', background: '#fff' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <RevealSection>
            <div style={{ textAlign: 'center', marginBottom: 64 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#1746A2', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>NASIL ÇALIŞIR?</div>
              <h2 style={{ fontFamily: "'Outfit', sans-serif", fontSize: 'clamp(28px, 3vw, 42px)', fontWeight: 700, marginBottom: 16 }}>
                <span className="landing-gradient-text">4 Adımda</span> İşe Alım
              </h2>
              <p style={{ fontSize: 17, color: '#5A6B82', maxWidth: 560, margin: '0 auto' }}>
                Karmaşık süreçler artık geride kaldı
              </p>
            </div>
          </RevealSection>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 32 }}>
            {steps.map((s, i) => (
              <RevealSection key={i}>
                <div style={{ textAlign: 'center', position: 'relative' }}>
                  <div
                    className="landing-gradient-text"
                    style={{ fontFamily: "'Outfit', sans-serif", fontSize: 48, fontWeight: 800, marginBottom: 16, opacity: 0.3 }}
                  >
                    {s.num}
                  </div>
                  <h3 style={{ fontFamily: "'Outfit', sans-serif", fontSize: 20, fontWeight: 600, marginBottom: 10 }}>{s.title}</h3>
                  <p style={{ fontSize: 15, color: '#5A6B82', lineHeight: 1.6, margin: 0 }}>{s.desc}</p>
                  {i < steps.length - 1 && (
                    <div style={{ position: 'absolute', top: 32, right: -16, color: '#d1d5db', display: 'none' }} className="landing-step-arrow">
                      {icons.arrow}
                    </div>
                  )}
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════ ÇÖZÜM ORTAKLARI ═══════════ */}
      <section id="cozum-ortaklari" style={{ padding: '80px 24px', background: '#fff' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <RevealSection>
            <div style={{ textAlign: 'center', marginBottom: 48 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#1746A2', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>ÇÖZÜM ORTAKLARIMIZ</div>
              <h2 style={{ fontFamily: "'Outfit', sans-serif", fontSize: 'clamp(28px, 3vw, 42px)', fontWeight: 700, marginBottom: 16 }}>
                Güvenilir <span className="landing-gradient-text">Teknoloji Ortaklarımız</span>
              </h2>
              <p style={{ fontSize: 17, color: '#5A6B82', maxWidth: 560, margin: '0 auto' }}>
                Güvenilir teknoloji ortaklarımız ile birlikte çalışıyoruz
              </p>
            </div>
          </RevealSection>

          <RevealSection>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 'clamp(32px, 5vw, 64px)', flexWrap: 'wrap' }}>
              {[
                { src: '/images/anthropic.png', alt: 'Anthropic' },
                { src: '/images/openai.png', alt: 'OpenAI' },
                { src: '/images/nous.png', alt: 'Nous Research' },
                { src: '/images/google.png', alt: 'Google' },
              ].map((partner, i) => (
                <img
                  key={i}
                  src={partner.src}
                  alt={partner.alt}
                  style={{
                    height: 40,
                    width: 'auto',
                    filter: 'grayscale(100%)',
                    opacity: 0.6,
                    transition: 'filter 0.3s ease, opacity 0.3s ease',
                    cursor: 'default',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.filter = 'grayscale(0%)'; e.currentTarget.style.opacity = '1' }}
                  onMouseLeave={e => { e.currentTarget.style.filter = 'grayscale(100%)'; e.currentTarget.style.opacity = '0.6' }}
                />
              ))}
            </div>
          </RevealSection>
        </div>
      </section>

      {/* ═══════════ FİYATLANDIRMA ═══════════ */}
      <section id="fiyatlandirma" style={{ padding: '100px 24px', background: '#f8fafc' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <RevealSection>
            <div style={{ textAlign: 'center', marginBottom: 64 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#1746A2', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>FİYATLANDIRMA</div>
              <h2 style={{ fontFamily: "'Outfit', sans-serif", fontSize: 'clamp(28px, 3vw, 42px)', fontWeight: 700, marginBottom: 16 }}>
                Her Ölçeğe <span className="landing-gradient-text">Uygun Plan</span>
              </h2>
              <p style={{ fontSize: 17, color: '#5A6B82', maxWidth: 560, margin: '0 auto' }}>
                İhtiyacınıza göre esnek fiyatlandırma
              </p>
            </div>
          </RevealSection>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 24, maxWidth: 1000, margin: '0 auto' }}>
            {plans.map((p, i) => (
              <RevealSection key={i}>
                <div
                  className="landing-card-hover"
                  style={{
                    background: p.highlight ? 'linear-gradient(135deg, #1746A2, #2563EB)' : '#fff',
                    borderRadius: 20, padding: 36,
                    border: p.highlight ? 'none' : '1px solid #e2e8f0',
                    color: p.highlight ? '#fff' : '#0B1222',
                    position: 'relative',
                    boxShadow: p.highlight ? '0 20px 40px rgba(23,70,162,0.25)' : 'none',
                  }}
                >
                  {p.highlight && (
                    <div style={{ position: 'absolute', top: -12, left: '50%', transform: 'translateX(-50%)', background: '#f59e0b', color: '#fff', fontSize: 12, fontWeight: 700, padding: '4px 16px', borderRadius: 100, letterSpacing: '0.04em' }}>
                      EN POPÜLER
                    </div>
                  )}
                  <h3 style={{ fontFamily: "'Outfit', sans-serif", fontSize: 22, fontWeight: 600, marginBottom: 4 }}>{p.name}</h3>
                  <p style={{ fontSize: 14, opacity: 0.7, marginBottom: 20, margin: '0 0 20px' }}>{p.desc}</p>
                  <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: 36, fontWeight: 800, marginBottom: 24 }}>{p.price}</div>
                  <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 28px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {p.features.map((feat, fi) => (
                      <li key={fi} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 15 }}>
                        <span style={{ color: p.highlight ? '#86efac' : '#22c55e', flexShrink: 0 }}>{icons.check}</span>
                        {feat}
                      </li>
                    ))}
                  </ul>
                  <button
                    onClick={() => scrollTo('#iletisim')}
                    style={{
                      width: '100%', padding: '12px 0', borderRadius: 10, fontSize: 15, fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s',
                      background: p.highlight ? '#fff' : 'transparent',
                      color: p.highlight ? '#1746A2' : '#1746A2',
                      border: p.highlight ? 'none' : '1.5px solid #1746A2',
                    }}
                    onMouseEnter={e => {
                      if (!p.highlight) { e.currentTarget.style.background = '#1746A2'; e.currentTarget.style.color = '#fff' }
                      else { e.currentTarget.style.background = '#f0f4ff' }
                    }}
                    onMouseLeave={e => {
                      if (!p.highlight) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#1746A2' }
                      else { e.currentTarget.style.background = '#fff' }
                    }}
                  >
                    Demo Talep Et
                  </button>
                </div>
              </RevealSection>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════ İLETİŞİM ═══════════ */}
      <section id="iletisim" style={{ padding: '100px 24px', background: '#fff' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <RevealSection>
            <div style={{ textAlign: 'center', marginBottom: 64 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#1746A2', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>İLETİŞİM</div>
              <h2 style={{ fontFamily: "'Outfit', sans-serif", fontSize: 'clamp(28px, 3vw, 42px)', fontWeight: 700, marginBottom: 16 }}>
                <span className="landing-gradient-text">Demo</span> Talep Edin
              </h2>
              <p style={{ fontSize: 17, color: '#5A6B82', maxWidth: 560, margin: '0 auto' }}>
                Ekibimiz sizinle en kısa sürede iletişime geçecektir
              </p>
            </div>
          </RevealSection>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 48, maxWidth: 900, margin: '0 auto' }}>
            {/* Form */}
            <RevealSection>
              {formSent ? (
                <div style={{ background: '#f0fdf4', borderRadius: 16, padding: 40, textAlign: 'center', border: '1px solid #bbf7d0' }}>
                  <div style={{ fontSize: 48, marginBottom: 16 }}>&#10003;</div>
                  <h3 style={{ fontFamily: "'Outfit', sans-serif", fontSize: 22, fontWeight: 600, marginBottom: 8 }}>Talebiniz Alındı!</h3>
                  <p style={{ color: '#5A6B82', fontSize: 15 }}>En kısa sürede sizinle iletişime geçeceğiz.</p>
                  <button
                    onClick={() => setFormSent(false)}
                    style={{ marginTop: 20, background: 'none', border: '1.5px solid #1746A2', borderRadius: 8, padding: '8px 24px', fontSize: 14, fontWeight: 600, color: '#1746A2', cursor: 'pointer' }}
                  >
                    Yeni Talep
                  </button>
                </div>
              ) : (
                <form onSubmit={handleFormSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <div>
                    <label style={{ display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 6 }}>Ad Soyad *</label>
                    <input
                      type="text" required value={formData.ad} onChange={e => setFormData({ ...formData, ad: e.target.value })}
                      style={{ width: '100%', padding: '10px 14px', borderRadius: 10, border: '1px solid #d1d5db', fontSize: 15, outline: 'none', transition: 'border 0.2s', boxSizing: 'border-box' }}
                      onFocus={e => (e.currentTarget.style.borderColor = '#2563EB')}
                      onBlur={e => (e.currentTarget.style.borderColor = '#d1d5db')}
                      placeholder="Adınız Soyadınız"
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 6 }}>Email *</label>
                    <input
                      type="email" required value={formData.email} onChange={e => setFormData({ ...formData, email: e.target.value })}
                      style={{ width: '100%', padding: '10px 14px', borderRadius: 10, border: '1px solid #d1d5db', fontSize: 15, outline: 'none', transition: 'border 0.2s', boxSizing: 'border-box' }}
                      onFocus={e => (e.currentTarget.style.borderColor = '#2563EB')}
                      onBlur={e => (e.currentTarget.style.borderColor = '#d1d5db')}
                      placeholder="ornek@sirket.com"
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 6 }}>Şirket</label>
                    <input
                      type="text" value={formData.sirket} onChange={e => setFormData({ ...formData, sirket: e.target.value })}
                      style={{ width: '100%', padding: '10px 14px', borderRadius: 10, border: '1px solid #d1d5db', fontSize: 15, outline: 'none', transition: 'border 0.2s', boxSizing: 'border-box' }}
                      onFocus={e => (e.currentTarget.style.borderColor = '#2563EB')}
                      onBlur={e => (e.currentTarget.style.borderColor = '#d1d5db')}
                      placeholder="Şirket adınız"
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: 14, fontWeight: 500, color: '#374151', marginBottom: 6 }}>Mesaj</label>
                    <textarea
                      rows={4} value={formData.mesaj} onChange={e => setFormData({ ...formData, mesaj: e.target.value })}
                      style={{ width: '100%', padding: '10px 14px', borderRadius: 10, border: '1px solid #d1d5db', fontSize: 15, outline: 'none', resize: 'vertical', transition: 'border 0.2s', boxSizing: 'border-box' }}
                      onFocus={e => (e.currentTarget.style.borderColor = '#2563EB')}
                      onBlur={e => (e.currentTarget.style.borderColor = '#d1d5db')}
                      placeholder="Mesajınız (opsiyonel)"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={formSending}
                    className="landing-gradient-bg landing-gradient-bg-hover"
                    style={{ border: 'none', borderRadius: 10, padding: '12px 0', fontSize: 16, fontWeight: 600, color: '#fff', cursor: formSending ? 'not-allowed' : 'pointer', opacity: formSending ? 0.7 : 1, transition: 'all 0.2s' }}
                  >
                    {formSending ? 'Gönderiliyor...' : 'Demo Talep Et'}
                  </button>
                </form>
              )}
            </RevealSection>

            {/* İletişim Bilgileri */}
            <RevealSection>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 28, paddingTop: 8 }}>
                <div>
                  <h3 style={{ fontFamily: "'Outfit', sans-serif", fontSize: 20, fontWeight: 600, marginBottom: 20 }}>İletişim Bilgileri</h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(23,70,162,0.08)', color: '#1746A2', flexShrink: 0 }}>
                    {icons.mail}
                  </div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 2 }}>Email</div>
                    <div style={{ fontSize: 15, color: '#5A6B82' }}>info@hylilabs.com</div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(23,70,162,0.08)', color: '#1746A2', flexShrink: 0 }}>
                    {icons.phone}
                  </div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 2 }}>Telefon</div>
                    <div style={{ fontSize: 15, color: '#5A6B82' }}>+90 (212) 000 00 00</div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(23,70,162,0.08)', color: '#1746A2', flexShrink: 0 }}>
                    {icons.location}
                  </div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 2 }}>Adres</div>
                    <div style={{ fontSize: 15, color: '#5A6B82' }}>İstanbul, Türkiye</div>
                  </div>
                </div>

                <div style={{ background: '#f8fafc', borderRadius: 12, padding: 20, marginTop: 12, border: '1px solid #e2e8f0' }}>
                  <p style={{ fontSize: 14, color: '#5A6B82', lineHeight: 1.6, margin: 0 }}>
                    Platformumuzu ücretsiz deneyebilirsiniz. Demo talebi oluşturduktan sonra
                    ekibimiz sizinle <strong style={{ color: '#0B1222' }}>24 saat içinde</strong> iletişime geçecektir.
                  </p>
                </div>
              </div>
            </RevealSection>
          </div>
        </div>
      </section>

      {/* ═══════════ FOOTER ═══════════ */}
      <footer style={{ background: '#0B1222', color: '#94a3b8', padding: '60px 24px 32px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 40, marginBottom: 48 }}>
            {/* Logo + Açıklama */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
                <img src="/images/footer_logo_600x400.png" alt="HyliLabs" style={{ height: 80, width: 'auto' }} />
              </div>
              <p style={{ fontSize: 14, lineHeight: 1.6, margin: 0 }}>
                Yapay zeka destekli işe alım platformu.
                Doğru adayı daha hızlı, daha akıllı bulun.
              </p>
            </div>

            {/* Platform */}
            <div>
              <h4 style={{ color: '#fff', fontSize: 15, fontWeight: 600, marginBottom: 16, fontFamily: "'Outfit', sans-serif" }}>Platform</h4>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[{ label: 'Özellikler', href: '#ozellikler' }, { label: 'Nasıl Çalışır?', href: '#nasil-calisir' }, { label: 'Fiyatlandırma', href: '#fiyatlandirma' }, { label: 'Demo Talep Et', href: '#iletisim' }].map(l => (
                  <li key={l.href}>
                    <button
                      onClick={() => scrollTo(l.href)}
                      style={{ background: 'none', border: 'none', color: '#94a3b8', fontSize: 14, cursor: 'pointer', padding: 0, transition: 'color 0.2s' }}
                      onMouseEnter={e => (e.currentTarget.style.color = '#fff')}
                      onMouseLeave={e => (e.currentTarget.style.color = '#94a3b8')}
                    >
                      {l.label}
                    </button>
                  </li>
                ))}
              </ul>
            </div>

            {/* Yasal */}
            <div>
              <h4 style={{ color: '#fff', fontSize: 15, fontWeight: 600, marginBottom: 16, fontFamily: "'Outfit', sans-serif" }}>Yasal</h4>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
                {['Gizlilik Politikası', 'Kullanım Koşulları', 'KVKK Aydınlatma Metni', 'Çerez Politikası'].map(l => (
                  <li key={l}>
                    <span style={{ fontSize: 14, cursor: 'pointer', transition: 'color 0.2s' }}
                      onMouseEnter={e => (e.currentTarget.style.color = '#fff')}
                      onMouseLeave={e => (e.currentTarget.style.color = '#94a3b8')}
                    >
                      {l}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {/* İletişim */}
            <div>
              <h4 style={{ color: '#fff', fontSize: 15, fontWeight: 600, marginBottom: 16, fontFamily: "'Outfit', sans-serif" }}>İletişim</h4>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
                <li style={{ fontSize: 14 }}>info@hylilabs.com</li>
                <li style={{ fontSize: 14 }}>+90 (212) 000 00 00</li>
                <li style={{ fontSize: 14 }}>İstanbul, Türkiye</li>
              </ul>
            </div>
          </div>

          {/* Alt çizgi */}
          <div style={{ borderTop: '1px solid rgba(148,163,184,0.15)', paddingTop: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
            <p style={{ fontSize: 13, margin: 0 }}>&copy; 2026 NETA BİLGİ TEKNOLOJİLERİ. Tüm hakları saklıdır.</p>
            <button
              onClick={() => navigate({ to: '/sign-in' })}
              style={{ background: 'none', border: '1px solid rgba(148,163,184,0.3)', borderRadius: 8, padding: '6px 16px', fontSize: 13, fontWeight: 500, color: '#94a3b8', cursor: 'pointer', transition: 'all 0.2s' }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = '#fff'; e.currentTarget.style.color = '#fff' }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(148,163,184,0.3)'; e.currentTarget.style.color = '#94a3b8' }}
            >
              Giriş Yap
            </button>
          </div>
        </div>
      </footer>
    </div>
  )
}
