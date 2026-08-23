# musical-seo

Sifir maliyetli muzik SEO denetim araci. Bir sarkinin dijital platformlardaki
gorunurlugunu denetler, "SEO karnesi" (HTML rapor) uretir ve gecelik snapshot ile
zaman serisi biriktirir.

## Veri kaynaklari (hepsi bedava)

| Kaynak | Anahtar | Ne verir |
|--------|---------|----------|
| Deezer API | Gerekmez | meta, ISRC, rank |
| iTunes Search | Gerekmez | Apple meta |
| Google/YouTube autocomplete | Gerekmez | keyword gorunurlugu |
| Spotify Web API | Opsiyonel (bedava dev hesap) | popularity, ISRC, meta |
| YouTube Data API | Opsiyonel (bedava 10k unit/gun) | views, tags |

## Kurulum

```
pip install musical-seo
```

Ses profili ve marketplace API'si opsiyonel ek paketlerde:

```
pip install "musical-seo[audio]"   # Deezer onizleme analizi (librosa)
pip install "musical-seo[api]"     # curator marketplace HTTP API'si
pip install "musical-seo[audio,api]"
```

Kaynaktan (gelistirme):

```
git clone https://github.com/seyhancanyakan/musical-seo.git
cd musical-seo
pip install -e ".[audio,api,dev]"
cp .env.example .env   # Windows: copy .env.example .env — anahtarlar opsiyonel
```

Kurulumdan sonra `musical-seo` komutu kullanilabilir; depo icinden
`python cli.py ...` de calismaya devam eder.

## Kullanim

```
# Denetim + HTML karne (reports/ altina)
musical-seo audit "Duman - Senden Daha Guzel"
python cli.py audit "Duman - Senden Daha Guzel"   # depo icinden ayni sey
python cli.py audit https://open.spotify.com/track/XXXX --out rapor.html

# JSON cikti
python cli.py audit "Sezen Aksu - Firuze" --json

# Gecelik snapshot (tracks.txt listesi -> data/snapshots.db)
python cli.py snapshot --list tracks.txt

# Zaman serisi
python cli.py history "Duman - Senden Daha Guzel"

# Playlist eslestirme (pitch aday listesi, Deezer benzer-sanatci analizi)
python cli.py playlists "Duman - Senden Daha Guzel" --limit 10

# Curator pitch mesajlari uret (+ --save ile takibe al, --out dosya.txt)
python cli.py pitch "Duman - Senden Daha Guzel" --limit 5 --save
python cli.py pitch --list                 # takip tablosu
python cli.py pitch --set 3 accepted      # durum guncelle (pitched|accepted|rejected)
```

## Gecelik otomasyon (bedava)

`.github/workflows/snapshot.yml` — GitHub Actions her gece 03:00 UTC'de
`tracks.txt` listesini denetler, `data/snapshots.db`'yi repoya commit'ler.
Spotify/YouTube anahtarlarini repo Secrets'a ekle (opsiyonel).

## Curator Marketplace (SubmitHub benzeri)

Kendi curator agi: basvuru + otomatik playlist dogrulama + gonderim kuyrugu
(72 saat SLA) + red'de zorunlu geri bildirim + otomatik yerlesim kaniti
(sarki playlist'e gercekten eklendi mi, Deezer'dan dogrulanir).

```
# API'yi baslat
uvicorn marketplace.api:app --port 8100

# Curator adaylari kesfet (davet listesi)
python cli.py curators "Duman" --limit 15
```

Endpoint'ler: POST /curators/apply, GET /curators, POST /submissions,
GET /submissions?curator_id=, POST /submissions/{id}/respond,
POST /submissions/{id}/verify-placement — dokumantasyon: http://localhost:8100/docs

## Skorlama

Kategoriler: metadata %30, presence %25, consistency %20, keywords %25.
critical -40, warn -20, info -5.

## Test

```
pytest
```

## Lisans

MIT — bkz. [LICENSE](LICENSE).
