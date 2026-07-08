# MüzikSEO — 4 Niş Özellik Implementasyon Workflow'u

> Bu doküman Claude Code'a verilerek, her özelliğin adım adım kodlanması için kullanılır.
> Sistem mimarisine uygun olarak yazılmıştır: `musical_seo/` (SEO motoru), `marketplace/` (FastAPI + SQLite), `web/` (Next.js).
> Ortak kurallar: Türkçe docstring, `ValueError → HTTP 400` hata sözleşmesi, idempotent DB işlemleri, anahtarsız fallback (asla çökme), saf fonksiyon + test edilebilirlik.

---

## İçindekiler
1. Özellik #1 — Sahte Playlist Dedektörü (Playlist Fraud Forensics)
2. Özellik #2 — Promosyon ROI Atıf Motoru (Promotion Attribution Engine)
3. Özellik #3 — Optimum Yayın Tarihi Optimizatörü (Release Timing Advisor)
4. Özellik #4 — Cover/Derivative Avcısı (Unauthorized Cover Hunter)
5. Ortak: API Router Bağlama + Web Sayfaları + Testler + Pricing

---

# ÖZELLİK #1 — Sahte Playlist Dedektörü (Playlist Fraud Forensics)

## Amaç
Sanatçı bir playlist'e yerleşmek için para ödemeden önce, o playlist'in **sahte/bot dolu** olup olmadığını adli analizle tespit eder. Spotify bot stream tespiti yapıp sanatçının telifini geri çekmesine engel olur.

## Neden Sisteme Özel
`musical_seo/audio.py` (audio profiling) + `musical_seo/audit.py` (SEO skorlama) + `musical_seo/db.py` (snapshots zaman serisi) + `marketplace/hermes_enrich.py` (web scraping) — bu 4'ü bir arada başka hiçbir araçta yok.

## Adım Adım Kodlama

### Adım 1.1 — Yeni modül: `marketplace/fraud_forensics.py`
Aşağıdaki tabloları `marketplace.db`'de oluştur (`_connect()` içinde `marketplace.db` + db şeması hazır, `radio_ads._connect()` paternini takip et):

```python
"""Sahte playlist dedektörü — adli analiz motoru.

Bir playlist'in bot/sahte dolu olma riskini 5 sinyalden hesaplar:
  1. Follower büyüme anomalisi (aniden 10K follower = satın alınmış)
  2. Track churn rate (sürekli şarkı değişimi = pay-to-play çiftliği)
  3. Coğrafi dağılım anomalisi (bot çiftlikleri kümelenir)
  4. Audio profile tutarlılığı (etiket "lo-fi" ama içinde 120 BPM trap = sahtekarlık)
  5. Listedeki şarkıların SEO skoru (düşük ortalama = sahte kitle)

Hata sözleşmesi: is kuralı ihlalleri ValueError (Türkçe) — API katmanı 400'e çevirir.
Anahtarsız/erişilemez kaynaklar None döner, fonksiyonlar asla çökmez.
"""
```

Tablolar:
- `fraud_reports` (id, created_at, playlist_url, playlist_title, owner_name, total_risk_score REAL, signal_breakdown TEXT/JSON, recommendation TEXT, report_token TEXT UNIQUE)
- `fraud_snapshots` (id, playlist_url, captured_at, follower_count INT, track_count INT, track_ids TEXT/JSON) — zaman serisi için

### Adım 1.2 — 5 Sinyal Fonksiyonu (her biri saf fonksiyon, test edilebilir)

```python
SIGNAL_WEIGHTS = {
    "follower_anomaly": 0.30,
    "track_churn": 0.20,
    "geo_cluster": 0.15,
    "audio_label_mismatch": 0.20,
    "track_seo_poverty": 0.15,
}

def signal_follower_anomaly(playlist_url: str) -> dict:
    """snapshots.db'deki playlist follower zaman serisinden büyüme anomalisi.
    Dönüş: {"score": 0..1, "detail": "...", "evidence": {...}}
    Aniden >2 std sapma artış = şüpheli. Veri yoksa None döner (score=0.5 nötr)."""

def signal_track_churn(playlist_url: str, window_days: int = 14) -> dict:
    """Playlist'in son N günde kaç şarkı ekleyip çıkardığı. Yüksek churn = pay-to-play."""

def signal_geo_cluster(playlist_url: str) -> dict:
    """Hermes bot ile playlist takipçilerinin coğrafi dağılımı.
    Tek ülke/bölge %80+ kümelenme = bot çiftliği şüphesi. None fallback."""

def signal_audio_label_mismatch(playlist_url: str) -> dict:
    """Playlist etiketi (örn. 'Lo-fi chill') ile içindeki şarkıların audio
    profilleri (musical_seo/audio.py ile BPM/enerji/parlaklık) karşılaştırması.
    Etiket lo-fi ama ortalama BPM 120 = sahtekarlık sinyali."""

def signal_track_seo_poverty(playlist_url: str) -> dict:
    """Playlist'teki örneklenmiş şarkıların musical_seo/audit.py SEO skorları.
    Ortalama skor <40 ise = sahte kitle (gerçek playlist'lerde ortalama 55+)."""
```

### Adım 1.3 — Ana orkestrasyon fonksiyonu

```python
def analyze_playlist(playlist_url: str) -> dict:
    """5 sinyali paralel topla (ThreadPoolExecutor), ağırlıklı risk skoru hesapla.
    Dönüş: {
        "playlist_url": ..., "playlist_title": ...,
        "total_risk_score": 0..100,  # 0= güvenli, 100= kesin sahte
        "verdict": "guvenli" | "riskli" | "cok_riskli" | "sahte",
        "signals": {sinyal_adı: {score, detail, evidence}},
        "recommendation": "PARA ÖDEME — %87 sahte riski" veya "Ödeyebilirsin",
        "report_token": "FRAUD-XXXX"
    }
    Sonucu fraud_reports'a kaydet, token üret (secrets.token_hex)."""
```

### Adım 1.4 — Pricing ekle (`marketplace/pricing.py`)
```python
FRAUD_REPORT_COST = 2  # kredi (Pro'ya ücretsiz)
FRAUD_REPORT_GUARANTEE_COST = 5  # sigorta: "güvenli" dedi, zarar gelirse telifi karşıla
```

### Adım 1.5 — API router: `marketplace/api_fraud.py`
```python
# POST /fraud/analyze  {playlist_url}  -> analyze_playlist()
# GET  /fraud/report/{token}  -> kayıtlı raporu döndür
# GET  /fraud/history?user_id=  -> kullanıcının geçmiş raporları
# Tümü auth gerektirir (accounts.require_auth decorator'ü, diğer api_*.py'da patern var)
```
Ana `api.py`'a `app.include_router(fraud_router)` ekle (diğer router'ların bağlandığı yer).

### Adım 1.6 — Web sayfaları (`web/app/fraud/`)
- `page.tsx` — Playlist URL girişi + "Analiz Et" butonu + pricing gösterimi
- `rapor/[token]/page.tsx` — 5 sinyalin görsel kartları + risk skoru gauge + öneri
- `lib/api.ts`'ye `analyzeFraud()`, `getFraudReport()` fonksiyonları ekle
- TR/EN çevirileri `lib/locale.tsx`'e ekle

### Adım 1.7 — Testler (`tests/test_fraud_forensics.py`)
- Her sinyal fonksiyonu için dummy veriyle test (follow норм vs anomali)
- `analyze_playlist` entegrasyon testi (gerçek playlist URL'i mock'la)
- Risk skoru aralıkları testi (0-100 sınırları, verdict eşikleri)
- İdempotency: aynı URL iki analiz → ikinci çağrıda cache'den veya yeni snapshot

### Adım 1.8 — SEO karnesi entegrasyonu
`musical_seo/report.py` HTML karnesine "Playlist Risk Uyarısı" bölümü ekle: eğer sanatçı bir playlist'e yerleşmişse ve o playlist fraud raporu varsa, karnede "⚠️ Bu playlist %X sahte riski taşıyor" rozeti göster.

---

# ÖZELLİK #2 — Promosyon ROI Atıf Motoru (Promotion Attribution Engine)

## Amaç
Sanatçının yaptığı her tanıtım yatırımının (küratör gönderimi, radyo reklamı, spot) SEO skoruna **ne kadar katkı sağladığını** ölçer. "Hangi yatırım getirdi?" sorusunu cevaplar.

## Neden Sisteme Özel
3 veri akışı aynı çatı altında: `snapshots.db` (günlük SEO skoru) + `marketplace.db` submissions (yerleşim kanıtı, tarih damgalı) + `fp_detections` (radyo çalınma, parmak iziyle kanıtlandı). Başka hiçbir araç bu üçünü entegre etmiyor.

## Adım Adım Kodlama

### Adım 2.1 — Yeni modül: `marketplace/attribution.py`

```python
"""Promosyon ROI atıf motoru.

Üç veri akışını birleştirir:
  1. SEO zaman serisi (snapshots.db — günlük skor)
  2. Yerleşim kanıtı (marketplace.db submissions — curator eklemeleri, tarih damgalı)
  3. Yayın kanıtı (fp_detections — radyo çalınma, parmak izi kanıtlı)

Atıf yöntemi: zaman serisi kırılma noktası (changepoint) tespiti + olay bazlı
katkı paylaştırma. Her tanıtım olayı (yerleşim/radyo çalınma), sonraki 7 gün
içindeki skor artışından sorumlu tutulur.

Hata sözçleşmesi: ValueError (Türkçe) → 400. Veri eksikse nötr atıf (0) döner.
"""
```

Tablolar:
- `attribution_reports` (id, created_at, user_id, track_query, period_start, period_end, total_score_delta INT, breakdown TEXT/JSON, report_token TEXT UNIQUE)
- `attribution_events` (id, report_id, event_type, event_date, source_id, attributed_delta REAL, confidence REAL) — her olayın katkısı

### Adım 2.2 — Veri toplama fonksiyonları

```python
def _collect_seo_series(track_query: str, start: str, end: str) -> list[dict]:
    """snapshots.db'den verilen tarih aralığında günlük SEO skorlarını çeker.
    Dönüş: [{"date": "2026-07-01", "score": 45}, ...]"""

def _collect_placement_events(user_id: int, start: str, end: str) -> list[dict]:
    """marketplace.db submissions'dan kabul edilen yerleşimleri (tarih + playlist)
    çeker. Sadece placement_verified=True olanlar."""

def _collect_airplay_events(user_id: int, start: str, end: str) -> list[dict]:
    """fp_detections + radio_ad_orders'dan radyo çalınma olaylarını çeker
    (parmak iziyle kanıtlanmış, detected_at tarih damgalı)."""
```

### Adım 2.3 — Changepoint tespiti (saf numpy, ek bağımlılık yok)

```python
def _detect_changepoints(scores: list[dict]) -> list[dict]:
    """Zaman serisinde anlamlı skor artışlarını tespit eder.
    Basit yöntem: 7-gün hareketli ortalama, önceki 7 güne göre >5 puan artış = changepoint.
    Dönüş: [{"date": ..., "delta": +7, "confidence": 0.8}, ...]"""

def _attribute_to_events(changepoint: dict, events: list[dict]) -> list[dict]:
    """Bir skor artışını, ondan önceki 7 gün içindeki olaylara paylaştırır.
    Ağırlıklar: radyo çalınma > playlist yerleşimi > organic.
    Dönüş: [{event_id, attributed_delta, confidence}, ...]"""
```

### Adım 2.4 — Ana rapor fonksiyonu

```python
def build_attribution_report(user_id: int, track_query: str,
                              period_start: str, period_end: str) -> dict:
    """Dönüş: {
        "track_query": ..., "period": {...},
        "total_score_delta": +17,  # dönem başı - sonu
        "breakdown": [
            {"channel": "radyo", "events": 3, "attributed_delta": 12.4, "roi_per_credit": 2.1},
            {"channel": "playlist", "events": 1, "attributed_delta": 3.1, "roi_per_credit": 0.8},
            {"channel": "organic", "events": 0, "attributed_delta": 1.5, "roi_per_credit": None}
        ],
        "recommendation": "Radyo kanalını %40 artır, playlist'i azalt — ROI 2.6x daha yüksek",
        "report_token": "ATTR-XXXX"
    }"""
```

### Adım 2.5 — Pricing (`pricing.py`)
```python
ATTRIBUTION_REPORT_COST = 1  # kredi (Pro'ya ücretsiz) — premium.py'da "etki raporu" zaten 1 kredi, bunu attribution versiyonu olarak genişlet
```

### Adım 2.6 — API router: `marketplace/api_attribution.py`
```python
# POST /attribution/report  {track_query, period_start, period_end}
# GET  /attribution/report/{token}
# GET  /attribution/history?user_id=
# auth gerektirir
```
`api.py`'a bağla.

### Adım 2.7 — Web sayfaları (`web/app/attribution/`)
- `page.tsx` — Şarkı seç + tarih aralığı + "Rapor Oluştur"
- `rapor/[token]/page.tsx` — Skor zaman serisi grafiği + changepoint işaretleri + kanal bazlı ROI kartları + öneri
- `lib/api.ts`'ye fonksiyonlar ekle
- TR/EN çevirileri

### Adım 2.8 — Testler (`tests/test_attribution.py`)
- `_detect_changepoints` düz seride [] dönmeli, artışta changepoint vermeli
- `_attribute_to_events` paylaştırma toplamı = changepoint delta'sı (korunum)
- `build_attribution_report` entegrasyon testi
- Boş dönem (veri yoksa) nötr atıf dönmeli, çökmemeli

### Adım 2.9 — premium.py entegrasyonu
`premium.py`'daki mevcut "etki raporu" (`impact_report`) fonksiyonunu `build_attribution_report` çağıracak şekilde genişlet — mevcut etki raporu attribution detayı olmadan sadece öncesi/sonrası skoru gösteriyor; bu onu geliştirir.

---

# ÖZELLİK #3 — Optimum Yayın Tarihi Optimizatörü (Release Timing Advisor)

## Amaç
Sanatçı şarkısını yanlış tarihte çıkarıp algoritma tarafından gömülmesine engel olur. "Bu tarihte çıkma, önce şunları yap, şu tarihte çık" tavsiyesi üretir.

## Neden Sisteme Özel
`musical_seo/audit.py` (SEO denetimi) + `musical_seo/keywords.py` + `sources/autocomplete` (keyword rekabeti) + `sources/musicbrainz` (yaklaşan release'ler) — hepsi `musical_seo/` çatısında. Standalone SEO araçları müzik bilmez; dağıtıcılar SEO bilmez.

## Adım Adım Kodlama

### Adım 3.1 — Yeni modül: `musical_seo/release_timing.py`

```python
"""Optimum yayın tarihi danışmanı.

Bir şarkının yayın öncesi hazırılığını + hedef tarihin rekabet durumunu
analiz eder. 4 sinyalden tavsiye üretir:
  1. Hazırlık skoru (audit.py — ISRC, metadata, presence, keyword)
  2. Hedef anahtar kelime rekabeti (autocomplete — dolu mu boş mu)
  3. Aynı hafta rakip release'ler (musicbrainz + spotify ön kayıt)
  4. Gün optimizasyonu (Cuma vs Salı — Türkiye pazarı için lokal veri)

Hata sözleşmesi: ValueError → 400. Veri eksikse nötr tavsiye.
"""
```

### Adım 3.2 — 4 Sinyal fonksiyonları

```python
def signal_readiness(track_query: str) -> dict:
    """musical_seo/audit.py ile mevcut SEO skorunu hesapla.
    Dönüş: {"score": 38, "findings": [...], "fixable_issues": [...]}
    Eğer skor <70 ise "şimdi çıkma, önce şunları düzelt" mesajı."""

def signal_keyword_competition(track_query: str) -> dict:
    """musical_seo/keywords.py + sources/autocomplete ile hedef anahtar
    kelimelerin Google/YouTube rekabet durumunu ölç.
    Dönüş: {"competition": "high"|"medium"|"low", "score": 0..1, "alternatives": [...]}
    Yüksek rekabet = aynı isimde popüler şarkı var, çıkarsa algoritma karıştırır."""

def signal_competitor_releases(target_date: str, window_days: int = 7) -> dict:
    """sources/musicbrainz + spotify ön kayıt ile hedef haftada çıkacak
    büyük release'leri tara.
    Dönüş: {"competitor_count": 3, "competitors": [{artist, title, date, popularity}],
            "risk": "high"|"medium"|"low"}"""

def signal_day_optimization(target_date: str, market: str = "TR") -> dict:
    """Türkiye pazarı için Cuma (global release day) vs Salı/Çarşamba analizi.
    Statik kural tabanı + lokal veri (ileride genişletilebilir).
    Dönüş: {"recommended_day": "Friday", "reason": "...", "score": 0..1}"""
```

### Adım 3.3 — Ana tavsiye fonksiyonu

```python
def advise_release(track_query: str, target_date: str) -> dict:
    """Dönüş: {
        "track_query": ..., "target_date": ...,
        "readiness": {score, findings, fixable_issues},
        "competition": {...}, "competitors": {...}, "day": {...},
        "overall_verdict": "hazir" | "hazirlan" | "ertele",
        "recommended_date": "2026-08-04",  # alternatif tarih
        "action_plan": [
            "ISRC kodunu ekle (+8 puan)",
            "YouTube'da resmi video aç (+5 puan)",
            "Anahtar kelime 'X' rekabeti yüksek, 'Y' kullan"
        ],
        "projected_score": 64  # tavsiyelere uyulursa hedef skor
    }"""
```

### Adım 3.4 — Pricing (`pricing.py`)
```python
RELEASE_TIMING_REPORT_COST = 1  # kredi (Pro'ya ücretsiz)
```

### Adım 3.5 — API router: `marketplace/api_release_timing.py`
```python
# POST /release-timing/advise  {track_query, target_date}
# GET  /release-timing/report/{token}
# auth gerektirir
```
`api.py`'a bağla. (Not: `musical_seo/` CLI katmanı olduğu için API `marketplace/` altında olur; `musical_seo/release_timing.py`'ı import eder.)

### Adım 3.6 — Web sayfaları (`web/app/yayin-zamanlamasi/`)
- `page.tsx` — Şarkı adı/sanatçı + hedef tarih seç + "Analiz Et"
- `rapor/[token]/page.tsx` — 4 sinyal kartı + verdict rozeti + önerilen tarih + aksiyon planı checklist
- `lib/api.ts`'ye fonksiyonlar
- TR/EN çevirileri

### Adım 3.7 — premium.py entegrasyonu
`premium.py`'da mevcut "yayın takvimi" modülü var — `advise_release()` çıktısını bu takvime enjekte et: sanatçının planlanan release'leri için otomatik tavsiye üret, takvimde "⚠️ 20 Temmuz riskli, 4 Ağustos önerilir" rozeti göster.

### Adım 3.8 — Testler (`tests/test_release_timing.py`)
- 4 sinyal fonksiyonu dummy veriyle
- `advise_release` — düşük hazırlık + yüksek rekabet = "ertele" verdict
- Yüksek hazırlık + düşük rekabet = "hazır" verdict
- Tarih hesaplama doğruluğu (alternatif tarih hesabı)

---

# ÖZELLİK #4 — Cover/Derivative Avcısı (Unauthorized Cover Hunter)

## Amaç
Bir şarkının YouTube/TikTok'ta **izinsiz cover'larını** tespit eder. Content ID sadece aynı kaydı yakalar; cover'ı (farklı kayıt, aynı melodi) yakalamaz. Telif hakkı kaybını önler.

## Neden Sisteme Özel
`musical_seo/audio.py` (audio profiling) + `marketplace/fingerprint.py` (dejavu-style hashing) + `musical_seo/sources/youtube.py` (scraping) + `marketplace/syncmarket.py` (lisanslama) — bu kombinasyon cover tespiti + otomatik lisans teklifi için gerekli.

## Adım Adım Kodlama

### Adım 4.1 — Yeni modül: `marketplace/cover_hunter.py`

```python
"""İzinsiz cover/derivative tespit motoru.

3 katmanlı tespit:
  1. Audio profile eşleştirme (BPM/tonalite/enerji/akor profili benzerliği)
  2. Söz + başlık çapraz arama (aynı sözler/başlık farklı kayıtlarda)
  3. Manuel doğrulama kuyruğu (şüpheli eşleşmeleri sanatçı onayına sunar)

Content ID sadece aynı kaydı yakalar; bu modül cover'ı (farklı kayıt, aynı
melodi/söz) yakalar. Bulunan cover'lar için lisans teklifi (syncmarket.py)
veya telif claim gönderilir.

Hata sözleşmesi: ValueError → 400. ffmpeg/librosa yoksa sessizce devre dışı.
"""
```

Tablolar (`marketplace.db`):
- `cover_hunts` (id, created_at, user_id, original_query, original_audio_profile TEXT/JSON, status TEXT, report_token TEXT UNIQUE)
- `cover_candidates` (id, hunt_id, source TEXT, url, title, channel, similarity_score REAL, match_reasons TEXT/JSON, status TEXT DEFAULT 'pending') — status: pending/approved/rejected/licensed/claimed
- `cover_licenses` (id, candidate_id, license_type, amount, status, created_at) — syncmarket entegrasyonu

### Adım 4.2 — Audio profile karşılaştırma

```python
def _audio_profile_distance(profile_a: dict, profile_b: dict) -> float:
    """İki audio profili (BPM, enerji, parlaklık, tonalite) arasındaki normalize
    mesafe 0..1. 0 = aynı, 1 = tamamen farklı. BPM toleranslı (±%5), tonalite
    harmonik (relative minor/major eşleşmesi)."""

def _original_audio_profile(track_query: str) -> dict | None:
    """musical_seo/audio.py ile orijinal şarkının audio profilini çıkar.
    Deezer preview'ından. Yoksa None (fonksiyon çökmez)."""
```

### Adım 4.3 — Aday toplama (scraping)

```python
def _collect_youtube_candidates(track_query: str, max_results: int = 50) -> list[dict]:
    """musical_seo/sources/youtube.py ile şarkı adı + 'cover'/'remix'/'version'
    sorgularıyla YouTube'da ara. Her sonucun audio profilini çıkar (preview varsa).
    Dönüş: [{url, title, channel, audio_profile}]"""

def _collect_lyrics_candidates(track_query: str) -> list[dict]:
    """Aynı sözleri/başlığı içeren farklı kayıtları bul (Genius/Genius-like search).
    Dönüş: [{url, title, source}]"""

def _collect_tiktok_candidates(track_query: str) -> list[dict:
    """TikTok'ta şarkı adıyla kullanılan sesleri tara (Hermes bot ile, opsiyonel)."""
```

### Adım 4.4 — Eşleştirme + skoring

```python
SIMILARITY_THRESHOLD = 0.65  # audio profile mesafesi < 0.35 = benzer

def score_candidates(original_profile: dict, candidates: list[dict]) -> list[dict]:
    """Her adayı orijinalle karşılaştır, similarity skoru (0..1) hesapla.
    Eşik üstü olanları cover_candidates'e 'pending' status ile yaz.
    Dönüş: [{candidate_id, similarity, match_reasons: ["audio_profile", "lyrics", "title"]}]}"""

def run_cover_hunt(user_id: int, track_query: str) -> dict:
    """Tüm akışı orkestre eder: profil çıkar → aday topla → skorla → DB'ye yaz.
    Dönüş: {
        "hunt_id": ..., "report_token": "HUNT-XXXX",
        "original_query": ...,
        "candidates_found": 12,
        "high_confidence": 5,  # similarity > 0.8
        "medium_confidence": 7,
        "estimated_unlicensed_revenue": "$1.200",  # potansiyel kayıp
        "candidates": [...]  # pending doğrulama için
    }"""
```

### Adım 4.5 — Doğrulama kuyruğu + aksiyon

```python
def review_candidate(user_id: int, candidate_id: int, verdict: str) -> dict:
    """Sanatçı adayı onaylar/reddeder. verdict: 'approved'|'rejected'.
    Onaylanan aday için:
      - syncmarket.py ile lisans teklifi üret (sync-ready pricing)
      - Veya telif claim talimatı üret (manuel gönderim için döküman)
    Dönüş: {candidate_id, verdict, next_action: "license_offer"|"claim", license_amount}"""

def generate_license_offer(candidate_id: int) -> dict:
    """syncmarket.py pricing ile cover için lisans teklifi üret.
    Dönüş: {license_type, amount, terms, message_template}"""

def generate_claim_document(candidate_id: int) -> dict:
    """Telif claim için gerekli döküman (YouTube Content ID claim talimatı,
    ISRC/ISWC referansı). Manuel gönderim için."""
```

### Adım 4.6 — Pricing (`pricing.py`)
```python
COVER_HUNT_COST = 2  # kredi — tek seferlik av (Pro'ya ücretsiz)
COVER_HUNT_WATCHDOG_COST = 5  # kredi/ay — sürekli izleme (her hafta yeni platform tarar)
COVER_LICENSE_COMMISSION = 0.15  # %15 — lisanslanırsa (syncmarket ile uyumlu)
```

### Adım 4.7 — API router: `marketplace/api_cover_hunt.py`
```python
# POST /cover-hunt/start  {track_query}  -> run_cover_hunt()
# GET  /cover-hunt/report/{token}
# GET  /cover-hunt/candidates?hunt_id=&status=pending
# POST /cover-hunt/candidates/{id}/review  {verdict}  -> review_candidate()
# POST /cover-hunt/candidates/{id}/license  -> generate_license_offer()
# POST /cover-hunt/watchdog/enable  -> sürekli izleme aboneliği
# auth gerektirir
```
`api.py`'a bağla.

### Adım 4.8 — Web sayfaları (`web/app/cover-avcisi/`)
- `page.tsx` — Şarkı seç + "Avı Başlat" + watchdog aboneliği toggle
- `rapor/[token]/page.tsx` — Aday listesi (similarity skoru sıralı) + her adayda onayla/reddet butonu
- `aday/[id]/page.tsx` — Aday detayı: orijinal vs aday audio profili karşılaştırma + lisans teklifi/claim aksiyonları
- `lib/api.ts`'ye fonksiyonlar
- TR/EN çevirileri

### Adım 4.9 — Sürekli izleme daemon'ı (opsiyonel ama değerli)
`marketplace/cover_hunt.py`'a watchdog thread ekle (fingerprint.py'deki `watch_once` paternini takip et, sürekli izleyici eksiği orada da belirtilmiş):
```python
def watch_loop(hunt_id: int, interval_hours: int = 168):
    """Her hafta yeni platformları (YouTube yeni videolar, TikTok trend)
    yeniden tarar, yeni aday bulursa cover_candidates'e ekler + kullanıcıya
    bildirim gönderir (growth.py notifications)."""
```

### Adım 4.10 — Testler (`tests/test_cover_hunt.py`)
- `_audio_profile_distance` — aynı profil = 0, farklı = yüksek, harmonik tonalite eşleşmesi
- `score_candidates` — eşik üstü/altı ayrımı
- `run_cover_hunt` entegrasyon testi (mock candidates)
- `review_candidate` — onay → lisans teklifi üretimi
- IDempotency: aynı hunt iki kez → cache/episode

---

# ORTAK BÖLÜM — Bağlama, Test, Pricing, Dokümantasyon

## A. API Router Bağlama (`marketplace/api.py`)
Her yeni router'ı ana `api.py`'a ekle (mevcut paterni takip et):
```python
from marketplace import api_fraud, api_attribution, api_release_timing, api_cover_hunt
app.include_router(api_fraud.router)
app.include_router(api_attribution.router)
app.include_router(api_release_timing.router)
app.include_router(api_cover_hunt.router)
```

## B. Pricing Özeti (`marketplace/pricing.py`'a eklenecek)
```python
# Özellik #1 — Sahte Playlist Dedektörü
FRAUD_REPORT_COST = 2
FRAUD_REPORT_GUARANTEE_COST = 5  # sigorta modeli

# Özellik #2 — ROI Atıf Motoru
ATTRIBUTION_REPORT_COST = 1  # mevcut "etki raporu"nun gelişmiş hâli

# Özellik #3 — Yayın Tarihi
RELEASE_TIMING_REPORT_COST = 1

# Özellik #4 — Cover Avcısı
COVER_HUNT_COST = 2
COVER_HUNT_WATCHDOG_COST = 5  #/ay
COVER_LICENSE_COMMISSION = 0.15
```

## C. Web Navigasyonu
`web/app/layout.tsx` veya ana navigasyon menüsüne 4 yeni link ekle:
- `/sahte-playlist` (fraud)
- `/attribution` (ROI)
- `/yayin-zamanlamasi` (release timing)
- `/cover-avcisi` (cover hunter)
TR/EN çevirileri `lib/locale.tsx`'e ekle.

## D. Test Komutu
```bash
cd C:\Users\seyha\CascadeProjects\musical-seo
python -m pytest tests/test_fraud_forensics.py tests/test_attribution.py tests/test_release_timing.py tests/test_cover_hunt.py -v
```
Hedef: her modül en az 10 test, hepsi geçmeli (mevcut sistemde 199 test geçiyor — toplam 240+ hedefi).

## E. Dokümantasyon Güncellemesi
- `docs/yazilim-genel-bakis.md`'a "Bölüm 15: Niş Özellikler (Fraud/Attribution/Timing/Cover)" ekle
- Her modülün başında Türkçe docstring (yukarıdaki şablonlara uygun)
- README'ye 4 özelliğin kısa tanıtımı

## F. Build & Run Kontrolü
```bash
# Backend
cd marketplace && uvicorn api:app --port 8100 --reload

# Frontend
cd web && npm run dev  # port 3100

# Manuel duman testi: her özelliğin ana endpoint'ini curl'la çağır
```

## G. Sıralama Önerisi (implementasyon sırası)
1. **#1 Sahte Playlist Dedektörü** (en yüksek değer, sisteme en uyumlu — audio+SEO+snapshots)
2. **#2 ROI Atıf Motoru** (#1'in verisiyle beslenir — sahte playlist'leri filtreleyince ROI doğru ölçülür)
3. **#3 Yayın Tarihi** (en hızlı ship, bağımsız modül)
4. **#4 Cover Avcısı** (en karmaşık, fingerprint+scraping+syncmarket entegrasyonu)

#1 ve #2 birlikte yapılırsa sinerji yüksek; #3 paralel ship edilebilir; #4 son.

---

## Claude Code'a Verilecek Prompt Örneği

```
Aşağıdaki workflow dokümanını oku ve uygula:
C:\Users\seyha\CascadeProjects\musical-seo\docs\NIS_OZELLIKLER_WORKFLOW.md

Özellik #1 (Sahte Playlist Dedektörü) ile başla. Adım 1.1'den 1.8'e kadar
sırayla uygula. Her dosyayı oluşturduktan sonra testlerle doğrula. Türkçe
docstring kullan, mevcut sistem paternlerini takip et (marketplace/fingerprint.py,
musical_seo/audit.py örnek al). ValueError → HTTP 400 sözleşmesine uy.

Tek bir özellik bitince dur ve beni bilgilendir, sonra sıradaki özelliğe geçelim.
```
