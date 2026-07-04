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
pip install -r requirements.txt
copy .env.example .env   # anahtarlar opsiyonel
```

## Kullanim

```
# Denetim + HTML karne (reports/ altina)
python cli.py audit "Duman - Senden Daha Guzel"
python cli.py audit https://open.spotify.com/track/XXXX --out rapor.html

# JSON cikti
python cli.py audit "Sezen Aksu - Firuze" --json

# Gecelik snapshot (tracks.txt listesi -> data/snapshots.db)
python cli.py snapshot --list tracks.txt

# Zaman serisi
python cli.py history "Duman - Senden Daha Guzel"
```

## Gecelik otomasyon (bedava)

`.github/workflows/snapshot.yml` — GitHub Actions her gece 03:00 UTC'de
`tracks.txt` listesini denetler, `data/snapshots.db`'yi repoya commit'ler.
Spotify/YouTube anahtarlarini repo Secrets'a ekle (opsiyonel).

## Skorlama

Kategoriler: metadata %30, presence %25, consistency %20, keywords %25.
critical -40, warn -20, info -5.

## Test

```
pytest
```
