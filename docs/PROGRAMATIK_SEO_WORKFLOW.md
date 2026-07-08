# Programatik SEO Büyüme Motoru — Implementasyon Workflow'u

> Bu doküman Claude Code'a verilerek programatik SEO altyapısının adım adım kodlanması için kullanılır.
> Mimariye uygun: `musical_seo/` (SEO motoru, audit.py 6 platform), `marketplace/` (FastAPI + SQLite), `web/` (Next.js App Router).
> **Pazar kararı: EN-global birincil.** Türkçe içerik ikincil (yalnızca TR araç sayfaları + `/blog/*-turkey`).
> Ortak kurallar: SSG/ISR + statik üretim, e-posta kapısı her ücretsiz sayfada, aşamalı index (spam işaretlenmemek için), anahtarsız fallback (asla çökme), idempotent üretim.

---

## 0. Acı Gerçek + Strateji Özeti

SEO "bir ayda patlatmak" değildir: minimum 3 ay, gerçek compound 6-12 ay. Ama doğru sayfa tipleriyle **ay 3'te ~$1K/ay**, **ay 6'da $3-5K**, **ay 12'de $10K+** gerçekçidir. Sır: herkes blog yazıp bekler; biz **programatik SEO** yaparız — milyonlarca otomatik üretilmiş sayfa. Tek silahımız: `audit.py` zaten 6 platformdan (Spotify/Deezer/Apple/YouTube/MusicBrainz/Last.fm) veri çekiyor. Bunu her sanatçı/şarkı/playlist için otomatik HTML'e çeviriyoruz.

**Çekirdek içgörü — "Her Sanatçının Aynası":** Her sanatçı Google'da kendi adını arar ("Drake Spotify", "kaç dinleyici", "kaç platformda"). Her sanatçı için 1 sayfa üretirsen → sıfır pazarlama ile milyonlarca organik ziyaretçi + ego-paylaşım viralitesi.

---

## İçindekiler
1. Mimari + Veri Boru Hattı
2. Tier 1 — Karşılaştırma Sayfaları (en hızlı trafik)
3. Tier 2 — Ücretsiz Araç Sayfaları (yapışkan)
4. Tier 3 — Programatik Sanatçı Sayfaları (para makinesi)
5. Tier 4 — Şarkı Sayfaları
6. Tier 5 — Playlist Sayfaları (fraud entegrasyonu)
7. Tier 6 — Blog / Uzun Kuyruk
8. Dönüşüm Hunisi + E-posta Kapısı
9. Retention Motoru (e-posta alert'leri)
10. Teknik SEO: Sitemap + IndexNow + Schema.org
11. Growth: Launch + Dağıtım
12. Üyelik / Pricing
13. Zaman Çizelgesi + Ölçüm
14. Sıralama + Claude Code Prompt'u

---

## 1. Mimari + Veri Boru Hattı

### 1.1 Katmanlar
```
musical_seo/audit.py         → 6 platform veri (mevcut)
        ↓
marketplace/seo_pages.py     → sayfa veri modeli üretimi (YENİ)
        ↓ (SQLite: seo_pages.db)
web/app/**/page.tsx (SSG/ISR)→ statik HTML üretimi
        ↓
sitemap shards + IndexNow     → arama motoruna bildir
```

### 1.2 Yeni modül: `marketplace/seo_pages.py`
```python
"""Programatik SEO sayfa üretim motoru.

audit.py çıktısını statik sayfalar için cache'lenmiş veri modeline çevirir.
Sayfa veri modelleri seo_pages.db'de tutulur; Next.js ISR bunları okur.
Aşamalı üretim: günde/ayda N sayfa (spam sinyali vermemek için).

Hata sözleşmesi: ValueError → 400. Veri eksikse sayfa 'thin' işaretlenir,
üretilmez (Google thin-content cezasından kaçış).
"""
```
Tablolar (`seo_pages.db`):
- `seo_artist_pages` (id, slug UNIQUE, artist_name, isni, score REAL, platform_count INT, findings_json, data_json, first_built_at, last_refreshed_at, indexed INT DEFAULT 0)
- `seo_song_pages` (id, isrc UNIQUE, slug, artist, title, score REAL, bpm REAL, song_key TEXT, data_json, last_refreshed_at, indexed INT)
- `seo_playlist_pages` (id, platform_playlist_id UNIQUE, slug, title, fraud_score REAL, verdict TEXT, data_json, last_refreshed_at, indexed INT)
- `build_queue` (id, page_type, ref, priority INT, status TEXT DEFAULT 'pending', created_at)

Fonksiyonlar:
- `enqueue_artist(artist_name, isni=None, priority=0)` — build_queue'ya ekle (idempotent, UNIQUE ihlali yut).
- `build_next_batch(limit=100)` — kuyruktan N al, `audit.run_audit` ile veri çıkar, seo_*_pages'e yaz; başarısız/thin olanları atla + logla. **Aşamalı üretim kalbi.**
- `get_artist_page(slug)`, `get_song_page(isrc)`, `get_playlist_page(pid)` — Next.js ISR data fetch.
- `pages_for_sitemap(page_type, offset, limit)` — sitemap shard üretimi.

### 1.3 Spotify catalog scraper (başlangıç veri seti)
`marketplace/catalog_scout.py` (mevcut `spotify_scout.py` / `import_scout.py` paternini takip et):
```python
def seed_top_artists(limit=100_000):
    """Chartmetric/Spotify chart/MusicBrainz'den top sanatçı isimlerini topla,
    seo_pages.enqueue_artist ile kuyruğa bas. Yasal/etik: sadece public API +
    sitemap + izinli kaynaklar. Rate-limit + kaldığı yerden devam (checkpoint)."""
```
Not: **Yasal veri toplama** — sadece public API'ler, robots.txt'e uy, agresif scrape yok.

---

## 2. Tier 1 — Karşılaştırma Sayfaları (EN HIZLI, ilk 2 hafta)

Düşük rekabet, yüksek satın alma niyeti. Günler-haftalar içinde sıralama. **~50 sayfa, elle yazılır (kaliteli).**

### Dosyalar
- `web/app/compare/[slug]/page.tsx` — SSG, `generateStaticParams` ile 50 slug.
- `web/content/compare/*.mdx` veya `web/lib/compareData.ts` — içerik kaynağı.

### 50 sayfa listesi (öncelik sırası)
```
submithub-vs-groover            groover-vs-playlistpush        submithub-alternatives
distrokid-vs-cdbaby             tunecore-vs-distrokid          best-spotify-playlist-submission-services
chartmetric-vs-viberate         soundcharts-vs-chartmetric     groover-alternatives
submithub-review                playlistpush-review            daily-playlists-review
best-music-distribution-2026    distrokid-alternatives         amuse-vs-distrokid
best-playlist-pitching-tools    spotify-for-artists-vs-...     how-much-does-submithub-cost
... (rakip matrisi: SubmitHub, Groover, Playlist Push, Daily Playlists, DistroKid,
    TuneCore, CD Baby, Amuse, Chartmetric, Soundcharts, Viberate, Musosoup)
```
Her sayfa: karşılaştırma tablosu, artı/eksi, fiyat, "bizim aracımız X'i ücretsiz yapıyor" CTA → e-posta kapısı. Schema: `Article` + `FAQPage`.

---

## 3. Tier 2 — Ücretsiz Araç Sayfaları (1-2 ay, yapışkan)

İnsanlar tekrar gelir → alışkanlık → üyelik. İki tanesi **dünyada tek** (niş özellikler besliyor).

### Dosyalar: `web/app/tools/[tool]/page.tsx` + backend uç noktaları
```
/tools/bpm-finder                → Deezer preview + audio.py (BPM)
/tools/song-key-detector         → audio.py tonalite
/tools/isrc-lookup               → audit.py ISRC alanı
/tools/spotify-monthly-listeners-tracker
/tools/playlist-fraud-checker    → fraud_forensics.analyze_playlist (TEK — feature#1)
/tools/cover-version-finder      → cover_hunter.run_cover_hunt (TEK — feature#4)
```
`playlist-fraud-checker` ve `cover-version-finder` niş backend'lere bağlanır; ücretsiz "önizleme" (skor + 1 bulgu) gösterir, tamı için e-posta kapısı → hesap → kredi. **Bunlar niş backlink çeker** ("free fake playlist detector" konsepti yeni).

Her araç sayfası: `SoftwareApplication` + `HowTo` schema, örnek sonuç, e-posta kapısı.

---

## 4. Tier 3 — Programatik Sanatçı Sayfaları (3-6 ay, DEVASA — para makinesi)

Her sanatçı için 1 sayfa; 8M potansiyel. Bu asıl gelir.

### Dosyalar
- `web/app/artist/[slug]/page.tsx` — ISR (`revalidate: 86400`), `generateStaticParams` ilk 10K, gerisi on-demand ISR.
- Data: `seo_pages.get_artist_page(slug)` → API `/seo/artist/{slug}`.

### Sayfa içeriği (gating)
| Katman | Görünen |
|--------|---------|
| Ücretsiz (herkes + Google) | SEO skoru (92/100), kaç platformda, 3 bulgu, `MusicGroup`+`AggregateRating` schema |
| E-posta kapısı | "Tam rapor + değişiklik takibi için e-posta gir" |
| Ücretli ($9+) | gerçek zamanlı takip, uyarılar, cover hunter, attribution |

**Ego tuzağı:** Her sanatçı kendi sayfasını görür → arkadaşına paylaşır → sosyal backlink → viral. Sayfada "Bu senin sayfan mı? Talep et" CTA.

---

## 5. Tier 4 — Şarkı Sayfaları (en yüksek hacim)

`web/app/song/[isrc]/[slug]/page.tsx` — 100M potansiyel. ISRC = Google-friendly unique ID.
İçerik: BPM, tonalite, hangi playlist'lerde, cover'lar (cover_hunter), SEO skoru. Schema: `MusicRecording`.
Data: `/seo/song/{isrc}`.

---

## 6. Tier 5 — Playlist Sayfaları (fraud dedektörü parlar)

`web/app/playlist/[pid]/page.tsx` — "Todays Top Hits: Güvenli mi? Sahte mi?"
- **Günlük güncellenir** (`revalidate: 86400`) → Google fresh content sever → daha sık tarar.
- Sanatçılar "eklendim mi?" diye her gün kontrol eder → **repeat visit**.
- `fraud_forensics` risk skoru + şeffaf sinyaller. Schema: `MusicPlaylist`.
Data: `/seo/playlist/{pid}`.

---

## 7. Tier 6 — Blog / Uzun Kuyruk

`web/app/blog/[slug]/page.tsx` (MDX). Örnekler:
```
how-to-get-on-spotify-editorial-playlists    what-is-isrc
spotify-bot-detection                         how-to-check-if-a-playlist-is-fake
submithub-alternatives-turkey (TR)            music-seo-guide-2026
```
Schema: `Article` + `FAQPage`. İç linkleme: her blog → ilgili araç/sanatçı sayfası.

---

## 8. Dönüşüm Hunisi + E-posta Kapısı

```
Google ziyaretçi (Tier 3/4/5)
  → "Skorun 45. Tam rapor için e-posta gir"  (E-POSTA KAPISI)
  → lead yakalandı
  → hesap açıldı → haftalık SEO özeti maili  (ALIŞKANLIK)
  → "Covernı 3 kişi izinsiz kullanıyor"       (ALERT → geri dönüş)
  → "Tam tespit için $19/ay"                  (ÜCRETLENDİRME)
```
**E-posta kapmadan para yok.** Her ücretsiz sayfada kapı olmalı.

### Backend
- `marketplace/leads.py` — `capture_lead(email, source_page, context)` → `leads` tablosu (email, source, created_at, context_json). Idempotent.
- API: `POST /leads/capture {email, source, context}`. Rate-limit + honeypot (CAPTCHA yerine).
- `web/components/EmailGate.tsx` — reusable; blur + "unlock" pattern.

---

## 9. Retention Motoru (en kritik — çoğu SEO aracı burada ölür)

İnsanlar ücretsiz gelir, bir kez bakar, gider. Avantajımız: **geri dönmek için sebep var.**

### E-posta alert türleri (`marketplace/alerts.py` + growth.py notifications)
1. **"Şarkının cover'ı YouTube'da bulundu"** → cover_hunter watchdog.
2. **"Playlist'inde sahte aktivite tespit edildi"** → fraud_forensics.
3. **"SEO skorun 45→52 çıktı — 3 yeni playlist"** → attribution.
4. **"Rakip X yeni şarkı çıkardı, %20 daha popüler"** → ego.

Cron: mevcut `_sla_cron` / `premium.maintenance_cycle` paternini genişlet — `alerts.run_daily()` her takip edilen varlığı tarar, değişiklik varsa mail kuyruğuna atar. Bu alert'ler olmadan kimse geri dönmez.

---

## 10. Teknik SEO: Sitemap + IndexNow + Schema.org

- `web/app/sitemap-[shard]/route.ts` — dinamik sitemap shard'ları (`pages_for_sitemap`), her shard ≤50K URL, `sitemap-index.xml`.
- `marketplace/indexnow.py` — `submit(urls)` → IndexNow API (Bing/Yandex anında index) + Google Search Console ping. Her `build_next_batch` sonrası yeni URL'leri gönder.
- Schema.org (JSON-LD, her sayfa tipinde): `MusicGroup`, `MusicRecording`, `MusicPlaylist`, `Person`, `AggregateRating`, `SoftwareApplication`, `Article`, `FAQPage`, `HowTo`. Yıldızlı/sanatçılı zengin snippet = yüksek tıklama.
- **Aşamalı index:** ayda 50K-100K yeni sayfa (hepsini birden basma = spam sinyali). `build_next_batch` günlük cron ile sınırlı.

---

## 11. Growth: Launch + Dağıtım (sıfır para)

1. **İlk 2 hafta:** 50 karşılaştırma sayfası (Tier 1) → hızlı trafik → ilk üyeler.
2. **Ay 1 launch:** Product Hunt ("I built a free tool to detect fake Spotify playlists" — viral potansiyel) + Reddit (r/WeAreTheMusicMakers 800K, r/musicproduction, r/Songwriting). İyi launch = 500-2000 signup.
3. **AppSumo LTD (opsiyonel):** 2 haftada 200-500 kullanıcı + $5-15K nakit. Lifetime verirsin → cash + taban, sonra normal üyelik.
4. **IndexNow + sitemap bombardımanı** (bkz §10).
5. **Schema zengin snippet'lar** (bkz §10).

---

## 12. Üyelik / Pricing (global USD)

| Plan | Fiyat | İçerik |
|------|-------|--------|
| Free | $0 | 3 denetim/ay, temel skor |
| Artist | $9/ay | sınırsız denetim + 1 şarkı takip + haftalık rapor |
| Pro | $29/ay | tüm özellikler (fraud + cover + attribution) + 10 şarkı takip |
| Label | $99/ay | 100 şarkı + ekip erişimi |

`marketplace/pricing.py`'a plan sabitleri; `accounts.py` plan alanı + gating. Niş özellikler (`fraud/cover/attribution`) Pro+ kapsamında.

---

## 13. Zaman Çizelgesi + Ölçüm

| Ay | Sayfa | Günlük ziyaretçi | Üye | MRR |
|----|-------|------------------|-----|-----|
| 1 | 100 (karşılaştırma+blog) | 30-100 | 5-20 | $0-100 |
| 3 | 10.000 (+sanatçı) | 300-1.000 | 50-150 | $300-1.500 |
| 6 | 100.000 | 2.000-5.000 | 200-500 | $1.500-5.000 |
| 12 | 1M+ | 10.000-50.000 | 1.000-3.000 | $10K-30K |

Ölçüm: Google Search Console (impressions/clicks/position), sayfa tipi bazlı dönüşüm, lead→hesap→ücretli huni oranları, alert açılma/geri dönüş.

### Yapma (zaman kaybı)
- ❌ TR-only odak → EN global. ❌ Sadece blog (yavaş). ❌ Backlink satın al (ceza). ❌ Pasif bekle (aktif index gerek). ❌ Tüm sayfaları aynı anda bas (spam).

---

## 14. Sıralama + Claude Code Prompt'u

**Implementasyon sırası:**
1. `seo_pages.py` + `leads.py` + `EmailGate.tsx` (altyapı — her şey buna bağlı).
2. Tier 1 (50 karşılaştırma) — hızlı trafik, elle içerik.
3. Tier 2 (araçlar) — niş backend'lere bağla (fraud/cover zaten var).
4. Sitemap + IndexNow + Schema (§10).
5. Tier 3 sanatçı sayfaları + `catalog_scout.py` seed + `build_next_batch` cron.
6. `alerts.py` retention (üye tutmanın kalbi).
7. Tier 4/5/6 hacim + blog.

**Claude Code prompt örneği:**
```
docs/PROGRAMATIK_SEO_WORKFLOW.md'yi oku ve uygula. Bölüm 1 + 8 ile başla
(seo_pages.py + leads.py + EmailGate.tsx altyapısı), sonra Tier 1. Mevcut
paternleri takip et (audit.py, marketplace/db.py, web/lib/api.ts). Türkçe
docstring, ValueError→400, idempotent üretim, aşamalı index. Her katman
bitince dur ve bilgilendir.
```

---

> **Not:** Bu programatik SEO motoru, `docs/NIS_OZELLIKLER_WORKFLOW.md`'deki 4 niş özelliği besler: `playlist-fraud-checker` ve `cover-version-finder` araç sayfaları doğrudan `fraud_forensics` ve `cover_hunter` backend'lerini kullanır — ücretsiz trafik → e-posta kapısı → Pro üyelik hunisi.
