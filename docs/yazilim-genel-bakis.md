# MüzikSEO — Yazılımın Tam Teknik ve İş Dokümanı

*Sanatçı ve müzik profesyonelleri için görünürlük ölçme, dağıtım ve kanıtlama platformu.*

Bu doküman yazılımın **ne yaptığını, nasıl çalıştığını, hangi parçalardan oluştuğunu ve her parçanın iş mantığını** eksiksiz anlatır. Özet değildir; sistemin tamamını modül modül açar.

---

## 1. Yazılımın Amacı ve Değer Önerisi

MüzikSEO, bir müzik eserinin dijital dünyadaki yolculuğunu üç aşamada yöneten uçtan uca bir platformdur:

1. **ÖLÇ** — Şarkının Spotify, Deezer, YouTube gibi platformlardaki görünürlüğünü (SEO) ücretsiz olarak ölçer, puanlar ve zaman içindeki değişimini takip eder.
2. **DAĞIT** — Şarkıyı doğru playlist küratörlerine, radyolara, medyaya, plak şirketlerine ve reklam kanallarına ulaştırır.
3. **KANITLA** — Yapılan her işin (playlist'e ekleme, radyoda çalma, reklam yayını) gerçekten yapıldığını bağımsız olarak doğrular.

### Platformun değişmez temel kuralı

> **Sonuç satılmaz. Hizmet satılır.**
> Playlist'e eklenme, radyoda çalınma gibi sonuçlar **asla garanti edilmez veya satılmaz.** Para karşılığı satılan tek şey, bir müzik profesyonelinin şarkıyı **dinleyip yazılı ve nitelikli geri bildirim vermesidir.** Eğer bir sonuç çıkarsa (şarkı listeye eklenirse), bu bağımsız olarak doğrulanır.

Bu kural sektörün "para al, kaybol" alışkanlığının tam tersidir ve platformun tüm güven mimarisinin temelidir.

---

## 2. Çözülen Problem

Müzik sektöründe iki büyük yapısal sorun vardır:

**Sorun 1 — Sanatçı parasını kanıtsız harcıyor.** Tanıtım, playlist ve radyo hizmetleri çoğunlukla vaatten ibarettir. Ödeme yapılır, sonuç görülmez, kanıt sunulmaz. Sanatçı ne aldığını bilmez.

**Sorun 2 — Görünürlük ölçülemiyor.** Sanatçı, şarkısının platformlardaki SEO durumunu göremez. Metadata eksik mi, hangi platformda görünmüyor, anahtar kelimelerde çıkıyor mu — hiçbiri bilinmez.

MüzikSEO bu iki sorunu da teknik olarak çözer: **ücretsiz ve sürekli ölçüm** + **kanıta zorlanan dağıtım.**

---

## 3. Genel Mimari — Üç Katman

Yazılım fiziksel olarak üç bağımsız ama entegre parçadan oluşur:

| Katman | Dizin | Görev | Teknoloji |
|--------|-------|-------|-----------|
| SEO Denetim Motoru | `musical_seo/` | Görünürlük ölçümü, karne, zaman serisi | Python (CLI + kütüphane) |
| Pazar & Gelir Motoru | `marketplace/` | Küratör pazarı, reklam, ödeme, kanıt | Python / FastAPI (REST) |
| Web Arayüzü | `web/` | Kullanıcı panelleri ve sayfaları | Next.js (TR/EN) |

Veri depolama tek bir SQLite dosyasında toplanır (sıfır sunucu maliyeti, kolay yedekleme, taşınabilirlik). SEO zaman serisi ayrı bir SQLite dosyasında (`data/snapshots.db`) tutulur.

---

## 4. KATMAN 1 — SEO Denetim Motoru (`musical_seo/`)

Sıfır maliyetle çalışan bir müzik SEO denetçisi. Kullanıcı bir şarkı adı veya platform linki verir; sistem birden çok bedava veri kaynağını tarayıp bir **"SEO Karnesi"** (HTML rapor) üretir ve gecelik anlık görüntülerle zaman serisi biriktirir.

### 4.1 Veri kaynakları (`musical_seo/sources/`)

Hepsi ücretsizdir; opsiyonel anahtarlar da bedava kotalıdır.

| Kaynak | Anahtar | Sağladığı veri |
|--------|---------|----------------|
| Deezer API | Gerekmez | Metadata, ISRC, sıralama, playlist |
| iTunes Search | Gerekmez | Apple metadata |
| Google/YouTube autocomplete | Gerekmez | Anahtar kelime görünürlüğü |
| Spotify Web API | Opsiyonel (bedava dev hesap) | Popülerlik, ISRC, metadata |
| YouTube Data API | Opsiyonel (bedava 10k birim/gün) | İzlenme, etiketler |
| Last.fm | Opsiyonel (bedava) | Dinlenme istatistikleri |
| MusicBrainz | Gerekmez | Uluslararası kayıt verisi |

### 4.2 Skorlama motoru (`audit.py`, `models.py`)

Şarkı dört kategoride puanlanır ve ağırlıklı toplamla tek bir skor üretilir:

| Kategori | Ağırlık | Ölçtüğü şey |
|----------|---------|-------------|
| Metadata | %30 | Etiket doğruluğu, ISRC varlığı, sanatçı/eser bilgisi |
| Presence (Varlık) | %25 | Kaç platformda görünüyor |
| Consistency (Tutarlılık) | %20 | Platformlar arası bilgi uyumu |
| Keywords (Anahtar kelime) | %25 | Arama/autocomplete görünürlüğü |

Tespit edilen her eksiklik ciddiyetine göre puandan düşülür:
- **Kritik (critical):** −40 puan
- **Uyarı (warn):** −20 puan
- **Bilgi (info):** −5 puan

Sonuç, kategori kırılımı ve tüm bulguları içeren bir HTML karne olarak `reports/` altına yazılır (`report.py`).

### 4.3 Yan analiz modülleri

- **`keywords.py`** — Google/YouTube otomatik tamamlamadan anahtar kelime görünürlüğü çıkarır.
- **`playlists.py`** — Benzer-sanatçı analiziyle şarkıya uygun playlist adaylarını bulur (pitch aday listesi).
- **`pitch.py`** — Her aday playlist için kişiselleştirilmiş tanıtım mesajı üretir.
- **`audio.py`** — Şarkının ses profilini ve ruh halini (mood) çıkarır; playlist uyumu için kullanılır.
- **`contacts.py`** — Playlist açıklamalarından iletişim bilgisi çıkarır; bulunamazsa "platforma davet et" akışına yönlendirir.
- **`spotify_scout.py`** — Curator/playlist keşfi.
- **`db.py`** — Zaman serisi veritabanı (snapshot kaydetme, geçmiş sorgulama).
- **`envutil.py`** — `.env` yükleme yardımcısı.

### 4.4 Komut satırı arayüzü (`cli.py`)

```
python cli.py audit "Duman - Senden Daha Guzel"      # Denetim + HTML karne
python cli.py audit <spotify-link> --json            # JSON çıktı
python cli.py snapshot --list tracks.txt             # Gecelik toplu denetim → zaman serisi
python cli.py history "Duman - Senden Daha Guzel"     # 30 günlük skor trendi
```

### 4.5 Gecelik otomasyon

`.github/workflows/snapshot.yml` — GitHub Actions her gece 03:00 UTC'de `tracks.txt` listesini denetler, `data/snapshots.db`'yi otomatik günceller. Tamamen ücretsizdir. Böylece her sanatçının skor değişimi zaman içinde birikir ve "büyüyen erken yakalanır".

---

## 5. KATMAN 2 — Pazar & Gelir Motoru (`marketplace/`)

Platformun kalbi. FastAPI ile yazılmış bir REST API. İki taraflı bir pazar kurar: **sanatçılar** (talep) ve **müzik profesyonelleri** (arz).

**Profesyonel (küratör) türleri:** playlist, radyo, medya, plak şirketi (label), menajer, booker, DJ, mentor, sync (lisans).

### 5.1 Hesap ve kimlik (`accounts.py`, `api.py`)

- Kayıt / giriş / çıkış, token tabanlı kimlik doğrulama.
- İki rol: **artist** ve **curator**.
- Kredi cüzdanı, işlem geçmişi, küratör kazançları.
- Referans/davet kodu: ilk gönderimde iki tarafa da bonus.

**Ana endpoint'ler:** `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /me` (kullanıcı + işlemler + kazançlar).

### 5.2 Çekirdek pazar döngüsü (`service.py`)

Platformun temel iş akışı:

```
Kredi al  →  Küratör seç  →  Gönder (1 kredi harcanır)
                                     │
                    Küratör dinler + yazılı geri bildirim verir
                                     │
              ┌──────────────────────┴──────────────────────┐
              │                                              │
   Nitelikli geri bildirim →                    72 saatte cevap yoksa →
   küratör ~$1 kazanır                          kredi OTOMATİK iade edilir
```

**İş kuralları:**
- **Playlist'e ekleme hiçbir zaman satılmaz/garanti edilmez.** Sadece dinleme + yazılı geri bildirim garanti edilir.
- **SLA (hizmet süresi):** Standart 72 saat. Süre dolar ve cevap gelmezse kredi otomatik iade edilir.
- **Garanti gönderim:** SLA kaçarsa 2 kat kredi iadesi (ek ücretli).
- **Öncelikli gönderim:** 48 saat SLA + gelen kutusunda üst sıra (+1 kredi).
- **Fırsat seviyeleri:** Kabulde küratör fırsat türü belirtir — primary/secondary + tür (playlist_ekleme, radyo_çalma, sosyal_paylaşım vb.).

**Gönderim endpoint'leri (giriş gerekli):**
- `POST /me/submissions` — sanatçı gönderim yapar.
- `GET /me/submissions` — sanatçı kampanya geçmişi (durum + geri bildirim + SLA).
- `GET /me/inbox` — küratör gelen kutusu.
- `POST /me/submissions/{id}/respond` — küratör kabul/red + zorunlu geri bildirim.
- `GET /me/earnings` — küratör kazançları.

**Güvenlik notu:** Kredi harcamadan gönderim yapan, herkese açık listeleme ve sahipsiz yanıt veren eski public yollar **kaldırıldı** (güvenlik açığıydı). Tüm gönderim/yanıt artık kimlik doğrulamalı yollardan geçer.

### 5.3 Küratör doğrulama (`service.py`, `db.py`)

- **Başvuru:** `POST /curators/apply` — playlist türü link ister, diğer profesyoneller linksiz başvurur.
- **Sahiplik doğrulama:** Küratör `POST /me/curator/verify/start` ile bir kod alır, bunu playlist açıklamasına ekler, `POST /me/curator/verify/check` ile doğrulama yapılır. Böylece listenin gerçekten kendisine ait olduğu kanıtlanır.
- **Yerleşim kanıtı:** `POST /submissions/{id}/verify-placement` — şarkının playlist'e gerçekten eklenip eklenmediği Deezer'dan bağımsız doğrulanır.

**Public katalog:** `GET /curators` (onaylı liste), `GET /curators/{id}`. Bu çıktılarda küratörün **e-postası, iletişim kaynağı ve doğrulama kodu asla sızdırılmaz** — sadece kamuya açık alanlar döner. Fiyat, küratörün erişimine (reach) göre otomatik hesaplanır ve katalogda görünür.

### 5.4 Yerleşik SLA cron'u

Uygulama ayakta olduğu sürece **15 dakikada bir** otomatik bakım döngüsü çalışır: SLA dolan gönderimleri kapatır, kredileri iade eder, yerleşim garantilerini işler, planlı gönderimleri gönderir ve Artist Pro aylık kredi tahsisini yapar. İnsan müdahalesi gerekmez. Ek olarak sunucu crontab'ına `POST /maintenance/expire` çağrısı da eklenebilir.

---

## 6. Gelir Modülleri (Nasıl Para Kazanır)

### 6.1 Kredi paketleri ve fiyatlandırma (`pricing.py`, `api_features.py`)

- **Kredi paketleri:** `GET /packages`. Sanatçı gönderim başına kredi harcar.
- **Satın alma isteği:** `POST /me/packages/request`, admin onayı `POST /admin/purchase-requests/{id}/grant`.
- **Reach-bazlı küratör fiyatı:** Küratörün takipçi/erişim büyüklüğüne göre otomatik kademeli fiyat.
- **Pilot ödeme:** Ödeme manuel alınır (iyzico/Papara), kredi `POST /admin/credits/grant` ile yüklenir (gizli admin anahtarıyla korunur).

### 6.2 Artist Pro (`premium.py`)

Aylık abonelik. Sağladıkları:
- Aylık otomatik kredi tahsisi.
- **Otopilot** (`POST /me/autopilot`) — sistem otomatik gönderim yapar.
- **Yayın takvimi** (`POST/GET /me/schedule`) — planlı gönderimler.
- **Payout** (`POST/GET /me/payouts`) — küratör kazanç çekimi.
- Aktivasyon: `POST /admin/pro/activate`.

### 6.3 Büyüme ve viral bileşenler (`growth.py`, `api_features.py`)

- **Referans sistemi:** `GET /me/referral` — davet, iki tarafa bonus.
- **Küratör sponsorluk:** `POST /admin/curators/sponsor` — küratör katalogda üst sıra için öder (arz tarafı gelir bacağı; sponsorlu küratörler listede öne çıkar).
- **Bildirimler:** `GET /me/notifications`, `POST /me/notifications/read`.
- **Public karne paylaşımı:** `POST /me/karne/share`, `GET /public/karne/{token}` — sanatçı karnesini paylaşır (organik yayılım).
- **Karne Ligi:** `GET /public/leaderboard`, `POST /me/leaderboard-opt-in` — liderlik tablosu.
- **Sertifika:** `GET /me/submissions/{id}/certificate`.
- **Paylaşım kartı:** `GET /me/submissions/{id}/share-card`.
- **Etki raporu:** `GET /me/submissions/{id}/impact`.
- **EPK (Elektronik Basın Kiti):** `GET /me/epk`.
- **Dashboard & hazırlık skoru:** `GET /me/dashboard`, `GET /me/readiness`.

### 6.4 Akıllı link + Affiliate (`smartlink.py`, `affiliate.py`, `api_smartlink.py`)

- **Smartlink:** `POST /me/links` — tüm platformları tek linkte toplar. Public link `GET /public/link/{slug}`, tıklama `POST /public/link/{slug}/click`.
- **Fan toplama:** `POST /public/link/{slug}/fan` — pre-save/e-posta toplar; `GET /me/links/{id}/fans`, dışa aktarma `POST /me/links/{id}/fans/export`.
- **Affiliate:** `GET /affiliates`, tıklama takibi `POST /affiliates/{key}/click`.

### 6.5 Sync/Lisans pazarı (`syncmarket.py`, `api_sync.py`)

Şarkının film, dizi, reklam için lisanslanması. İlan (`POST /me/sync/listings`) → public katalog (`GET /public/sync`) → talep (`POST /public/sync/{id}/request`) → yanıt → ödeme.

### 6.6 Label / A&R B2B (`labels.py`, `api_labels.py`)

Plak şirketlerine kurumsal erişim. Başvuru (`POST /public/labels/apply`) → admin onay (`POST /admin/labels/{id}/approve`) → rapor (`GET /labels/report`).

### 6.7 Radyo airplay takibi (`airplay.py`, `api_airplay.py`)

Radyo istasyonlarını izler. İstasyon ekleme (`POST /admin/airplay/stations`), polling (`POST /admin/airplay/poll`), sanatçı aboneliği (`POST /me/airplay/subscribe`), çalınma tespiti (`GET /me/airplay/hits`).

### 6.8 Tanıtım kartı (`promo.py`, `api_promo.py`)

Otomatik animasyonlu tanıtım/kanıt kartı (SVG). `POST /me/promo`, `GET /me/promo/{token}.svg`.

### 6.9 Geri bildirim sentezi (`feedback_digest.py`, `api_feedback.py`)

Tüm küratör yanıtlarını tek raporda özetler. `POST /me/feedback-digest`, `GET /me/feedback-digest`.

### 6.10 Şarkı kütüphanesi (`tracks.py`, `api_tracks.py`)

Sanatçının şarkı kütüphanesi. `POST /me/tracks`, `GET /me/tracks`, `DELETE /me/tracks/{id}`.

### 6.11 Lead / iletişim zenginleştirme (`import_scout.py`, `enrich_contacts.py`, `hermes_enrich.py`)

İletişim bilgisi bulunamayan küratörler otomatik olarak "lead" kaydedilir. Hermes adlı web-araştırma botu (uzak sunucuda) bu lead'lerin halka açık gönderim iletişimini web'den araştırıp tamamlar.

---

## 7. Radyo Reklam Ekosistemi (En Gelişmiş Katman)

Platformun en yüksek gelir potansiyelli parçası. İşletmeler ve sanatçılar yerel radyolarda kendi kendine reklam kampanyası kurar. Dört alt sistemden oluşur.

### 7.1 Reklam envanteri ve tekil sipariş (`radio_ads.py`)

**Aktörler:** Radyo türü küratör (envanter açar), alıcı (işletme/sanatçı, sipariş verir), admin (ödeme onayı), MüzikSEO (**%18 komisyon**).

**Envanter (`radio_ad_listings` tablosu):** istasyon adı, spot süresi (15/30/60 saniye), yayın kuşağı (sabah/gündüz/drive/akşam/gece), haftalık tekrar sayısı, haftalık fiyat, şehir. Sadece `radyo` türü küratör açabilir.

**Sipariş yaşam döngüsü:**
```
pending → (küratör kabul/red) → accepted → (admin ödeme) → paid → (küratör yayın kaydı) → airing
```
- Fiyat ve komisyon **sipariş anında donar** — sonradan fiyat değişse eski sipariş etkilenmez.
- Kabulde standart Türkçe sözleşme metni üretilir.
- `mark_paid` yalnızca kabul edilmiş siparişe uygulanabilir, idempotenttir.
- Yayın kaydı (`record_air`) her çağrıda teyitli yayın sayacını (`verified_plays`) artırır; **ödeme tamamlanmadan yayın kaydı alınamaz.**

**Endpoint'ler:** ilan (`POST/GET /me/radio-ads/listings`, duraklat/aktif et), public katalog (`GET /public/radio-ads`), sipariş (`POST /public/radio-ads/{id}/order`), yanıt (`POST /me/radio-ads/orders/{id}/respond`), yayın (`POST /me/radio-ads/orders/{id}/air`), admin ödeme (`POST /admin/radio-ads/orders/{id}/paid`).

### 7.2 5 Adımlı Self-Servis Kampanya Sihirbazı (`campaigns.py`, `api_campaigns.py`)

Alıcı, tek formda birden fazla radyoya **aynı anda** reklam verir. Bu "fan-out" katmanı `radio_ads` üzerine kuruludur — gerçek siparişler yine tekil sipariş sistemine yazılır.

**Adım 1 — İçerik:** Ürün/marka bilgisi girilir. Yapay zeka reklam metni + seslendirme + jingle üretilir (bkz. bölüm 7.3).

**Adım 2 — Hedef:** Şehir(ler) ve yayın kuşağı/kuşakları seçilir. Boş bırakılırsa tüm katalog.

**Adım 3 — Bütçe & Paket:** `POST /public/campaigns/suggest` üç hazır paket önerir:
- **Açılış Paketi** — en ucuz 3 ilan, 1 hafta.
- **Hafta Sonu Kampanyası** — yalnız drive+akşam kuşağı, 1 hafta.
- **1 Aylık Bilinirlik** — tüm havuz, 4 hafta.

Her paket bütçeye **en ucuzdan doldurulur**; bütçe aşımının ilk noktasında durulur.

**Adım 4 — Onay & Fan-out:** `POST /public/campaigns` çağrılır:
1. Girdi doğrulanır (alıcı türü, e-posta, ürün, spot metni; hafta 1–12; pozitif bütçe).
2. Şehir+kuşak filtresiyle uygun ilanlar seçilir, bütçeye sığdırılır.
3. **Hiç ilan sığmazsa hiçbir kayıt bırakılmadan hata verilir** (ya hep ya hiç).
4. Bir kupon kodu üretilir (`RADYO-XXXX`), spot mesajına eklenir.
5. Seçili her ilana gerçek sipariş verilir.
6. **Tek birleşik sözleşme** üretilir (tüm istasyonlar tek belgede: taraflar, spot, süre, kupon, toplam bedel + komisyon, istasyon başına döküm).
7. Kampanya ve bağlı siparişler tek işlemde (transaction) kaydedilir.
8. Her radyo küratörüne bildirim gönderilir (uygulama içi + varsa e-posta); bildirim hatası akışı bozmaz.

**Adım 5 — Ödeme:** Admin `POST /admin/campaigns/{id}/paid` ile bağlı tüm siparişleri toplu "ödendi" işaretler; kampanya "active" olur.

**Alıcı takibi:** `GET /public/campaigns/{id}?email=` — kampanya + sipariş kırılımı. **E-posta eşleşme kapısı**: yanlış e-posta "bulunamadı" döner (varlık maskesi, güvenlik). Rapor `GET /public/campaigns/{id}/report`: planlanan toplam spot vs teyitli yayın, istasyon bazında döküm, kupon kodu.

### 7.3 Yapay zeka spot üretimi (`spot_ai.py`, `api_spot.py`)

**Reklam metni:** `POST /public/spot/script`. Anthropic-uyumlu bir dil modeli çağrılır. **Şu an z.ai (GLM-5.2) modeli kullanılıyor** — doğal, akıcı, harekete geçirici Türkçe spot metni yazar ve metne otomatik bir kupon kodu yer tutucusu (`{KUPON}`) yerleştirir. Sağlayıcı ortam değişkenleriyle seçilir (`LLM_API_URL`, `LLM_MODEL`, `LLM_API_KEY`); tanımlı değilse sistem **deterministik şablon metne** düşer — hiçbir durumda çökmez. Hedef kelime sayısı, spot süresine göre hesaplanır (~saniye × 2.5).

**Seslendirme:** `POST /public/spot/voice`. ElevenLabs ile çok dilli profesyonel ses üretimi; MP3 sunucuda saklanır, `GET /spot-file/{id}` ile servis edilir. Anahtar zorunludur. Ses listesi `GET /public/spot/voices` (anahtar yoksa 3 örnek ses döner, arayüz bozulmaz).

**Jingle:** `POST /public/spot/jingle`. Suno resmi API sunmadığından bir talep kuyruğu açılır; operatör şarkıyı harici üretir, admin `POST /admin/spot/jingle-requests/{id}/fulfill` ile dosyayı talebe bağlar.

### 7.4 Ses parmak izi ile yayın doğrulama (`fingerprint.py`, `api_fingerprint.py`)

Reklam gerçekten yayınlandı mı? Küratör beyanının yanında **bağımsız kanıt** sunar:
- Admin, spotun ses parmak izini kaydeder: `POST /admin/fingerprint/spots/{order_id}/register`.
- Yayın akışı taranır: `POST /admin/fingerprint/scan`.
- Tespitler birikir: `GET /admin/fingerprint/detections`.
- Alıcı bağımsız kanıtı görür: `GET /public/campaigns-proof/{order_id}`.

---

## 8. KATMAN 3 — Web Arayüzü (`web/`)

Next.js ile geliştirilmiş, Türkçe/İngilizce çok dilli (`locale.tsx`, `middleware.ts`) modern panel.

**Sayfalar:** ana panel, giriş, şarkı gönderme, kampanyalar, **karne**, küratör paneli, **lig** (liderlik), akıllı linkler, plak şirketi paneli, playlist keşfi, Pro aboneliği, **radyo**, raporlar, **reklam sihirbazı** (`/reklam/kampanya`), sync pazarı, **yayın takvimi**, tanıtım kartı, yönetici paneli ve public kısa linkler (`/k`, `/l`).

Ana panelde pitch üretimi **canlı akışla** (SSE) gösterilir: şarkı çözümlenir → playlist havuzu taranır → ses profili analiz edilir → mood eşleşmesi → sıralama → sonuç. Kullanıcı süreci gerçek zamanlı görsel efektlerle izler.

---

## 9. Veri Modeli (Ana Tablolar)

Tümü tek SQLite dosyasında:

- **users** — hesaplar (rol, kredi, token).
- **curators** — küratör kayıtları (tür, playlist, doğrulama durumu, kalite skoru).
- **submissions** — gönderimler (durum, geri bildirim, SLA, fırsat).
- **transactions / earnings** — kredi işlemleri ve küratör kazançları.
- **radio_ad_listings / radio_ad_orders** — radyo reklam envanteri ve siparişleri.
- **ad_campaigns / ad_campaign_orders** — fan-out kampanyaları ve sipariş bağlantıları.
- **spot_assets / jingle_requests** — üretilen metin/ses/jingle varlıkları.
- **links / fans / affiliates** — akıllı link, fan ve affiliate verisi.
- **sync_listings / label_leads / airplay_*** — sync, label ve airplay verileri.

Ayrıca `data/snapshots.db` — SEO zaman serisi (gecelik skorlar).

---

## 10. Güven ve Kanıt Mimarisi

Platformun tüm değeri güven üzerine kuruludur ve yazılım bunu teknik olarak zorunlu kılar:

1. **Sonuç değil hizmet satılır** — playlist ekleme / radyo çalma asla garanti edilmez.
2. **Zaman garantisi** — SLA dolunca otomatik kredi iadesi, insan müdahalesi gerekmez.
3. **Bağımsız doğrulama** — yerleşim kanıtı (Deezer), yayın kanıtı (ses parmak izi), sahiplik doğrulaması (playlist açıklama kodu).
4. **Zorunlu geri bildirim** — küratör reddederse dahi yazılı sebep vermek zorundadır.
5. **Şeffaf fiyat** — küratör erişimine göre otomatik fiyat, katalogda görünür.
6. **Fiyat donması** — sipariş anındaki fiyat sonradan değişmez.

---

## 11. Teknoloji ve Maliyet Disiplini

- **Backend:** Python + FastAPI.
- **Veritabanı:** SQLite (sıfır sunucu maliyeti, kolay yedek, taşınabilir).
- **Frontend:** Next.js (TR/EN çok dilli).
- **SEO verisi:** Tamamen ücretsiz kaynaklar; opsiyonel anahtarlar bedava kotalı.
- **Yapay zeka:** z.ai GLM-5.2 (spot metni) + ElevenLabs (ses). Anahtar yoksa şablon fallback ile sistem asla durmaz.
- **Otomasyon:** Gecelik SEO snapshot GitHub Actions ile ücretsiz; SLA kontrolü uygulama içinde 15 dakikada bir otomatik.

**Maliyet felsefesi:** Sistem, gelir gelmeden önce **neredeyse sıfır sabit maliyetle** ayakta durabilecek şekilde tasarlandı. Ücretli servisler (yapay zeka, seslendirme) yalnızca gelir üreten işlemlerde devreye girer.

---

## 12. Güvenlik İlkeleri

- API anahtarları ve sırlar **koda gömülmez**; ortam değişkenlerinde (`.env`) tutulur, versiyon kontrolüne dahil edilmez.
- Reklam envanterini yalnız doğrulanmış radyo hesapları açabilir.
- Sipariş fiyatı sipariş anında donar.
- Kampanya görüntüleme e-posta ile maskelenir (kullanıcı yalnız kendi kampanyasını görür).
- Yönetici işlemleri ayrı bir gizli anahtarla (`MARKETPLACE_ADMIN_KEY`) korunur.
- Public küratör verisinde e-posta / iletişim kaynağı / doğrulama kodu sızdırılmaz.
- Dosya işlemlerinde dizin gezinme (path traversal) koruması.
- Güvenlik açığı olan eski public gönderim yolları kaldırıldı.

---

## 13. Mevcut Durum

- Çekirdek pazar döngüsü, SEO motoru ve radyo reklam ekosistemi **çalışır durumda.**
- Yapay zeka spot üretimi z.ai (GLM-5.2) ile **canlı test edilip doğrulandı** (gerçek Türkçe reklam metni üretiliyor).
- Kapsamlı otomatik test seti mevcut: **199 test geçiyor.**
- Ödeme akışı pilot aşamada manuel (iyzico/Papara ile alınıp kredi yüklenir); altyapı tam otomasyona hazır.

---

## 14. Sistemin Genel Mantığı (Bütünsel Bakış)

MüzikSEO, bir sanatçının bir şarkısını alıp onu **ölçülebilir, dağıtılabilir ve kanıtlanabilir** bir sürece sokar:

1. Sanatçı şarkısını sisteme verir; **SEO motoru** neyin eksik olduğunu ücretsiz gösterir.
2. Sistem şarkıya uygun **küratör ve playlist adaylarını** bulur, tanıtım mesajlarını hazırlar.
3. Sanatçı kredi harcayarak gönderim yapar; profesyonel **dinlemek ve yazılı geri bildirim vermek zorundadır** — yoksa parası iade edilir.
4. İşletmeler ve sanatçılar aynı platformda **yapay zeka destekli radyo reklamı** kurar; sistem metni yazar, sesi üretir, radyoları seçer, sözleşmeyi hazırlar.
5. Yapılan her iş **bağımsız kanıtla** (yerleşim doğrulama, ses parmak izi, airplay takibi) belgelenir.
6. Platform bu zincirin her halkasından adil bir gelir alır (kredi, abonelik, %18 reklam komisyonu, sync/label, sponsorluk).

Sonuç: Sektörün en büyük güven açığını kapatan, düşük maliyetle ölçeklenen, uçtan uca bir müzik görünürlük ve dağıtım platformu.
