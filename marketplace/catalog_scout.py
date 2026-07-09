"""Top sanatci seed motoru: programatik SEO kuyruguna (bkz. seo_pages.build_queue)
en bilinen sanatcilari YUKSEK oncelikle ekler. Boylece gunluk arka plan uretimi
(bkz. marketplace.api._seo_build_cron) once bu sanatcilarla baslar, sonra
kuyruga eklenen diger sanatcilarla devam eder — "once top sanatcilar, sonra
sistem hergun yavas yavas buyusun" akisi.

Sanatci disinda iki seed motoru daha: `seed_songs_from_starter` (STARTER_TOP_
ARTISTS'in Deezer'daki top parcalarini kuyruga ekler) ve
`seed_playlists_from_search` (populer tur/mood sorgulariyla Spotify'da
playlist arar). Ikisi de guardli — Deezer/Spotify erisilemezse (ag hatasi,
kimlik bilgisi yok, kota asimi) sessizce atlar/bos doner, ASLA cokmez;
seed_from_list ile ayni idempotent kuyruk sozlesmesini kullanirlar.

Yasal/etik: sanatci seed'i (seed_starter) AG ERISIMI YAPMAZ — sadece bu
dosyadaki bundled listeyi (STARTER_TOP_ARTISTS) veya cagiranin verdigi ismi
kuyruga yazar. Sarki/playlist seed'leri ise Deezer'in genel/anahtarsiz arama
uc noktalarini ve Spotify'in Client Credentials ile herkese acik arama uc
noktasini kullanir — 3. parti scraping/yetkisiz veri kazima YOK, sadece
resmi API'ler. seo_pages.enqueue_* zaten idempotent oldugu icin ayni kaydi
tekrar seed etmek yeni 'pending' satir acmaz; boylece kaldigi yerden devam
edilebilir (script her calistiginda sifirdan baslamaz).

Hata sozlesmesi: is kurali ihlalleri ValueError (aksanli Turkce) — API
katmani bunu 400'e cevirir.
"""
from __future__ import annotations

import requests

from marketplace import seo_pages, spotify_client

_DEEZER_TIMEOUT = 15
_DEEZER_SEARCH_ARTIST_URL = "https://api.deezer.com/search/artist"
_DEEZER_ARTIST_TOP_URL = "https://api.deezer.com/artist/{id}/top"

_SPOTIFY_TIMEOUT = 15
_SPOTIFY_SEARCH_URL = "https://api.spotify.com/v1/search"

# Populer tur/mood sorgulari — seed_playlists_from_search icin varsayilan
# arama listesi (kullanici turlerin cesitliligini genisletmek icin farkli
# bir liste verebilir).
DEFAULT_PLAYLIST_SEARCH_QUERIES: list[str] = [
    "pop hits", "chill vibes", "workout motivation", "türkçe pop",
    "hip hop 2024", "sleep ambient", "party dance", "acoustic chill",
    "rock classics", "latin hits",
]

# Oncelik hic bir zaman bu tabanin altina inmez (0 veya negatif oncelik
# build_next_batch siralamasinda anlamsizlasir/normal kuyrukla karisir).
MIN_PRIORITY = 1


def seed_from_list(names: list[str], base_priority: int = 100) -> dict:
    """Verilen isim listesini SIRALI azalan oncelikle kuyruga ekler: ilk isim
    en yuksek onceligi (base_priority) alir, sonraki her isim bir eksigini
    alir (index kadar), boylece build_next_batch (priority DESC siralama)
    listedeki sirayi korur. Oncelik MIN_PRIORITY'nin altina inmez (taban).
    Bos/gecersiz isimler atlanir. Idempotent — enqueue_artist zaten bekleyen
    kaydi yutar, tekrar seed etmek yeni satir acmaz."""
    if not names:
        raise ValueError("Sanatci listesi bos olamaz")

    queued = 0
    skipped = 0
    for index, name in enumerate(names):
        if not name or not name.strip():
            skipped += 1
            continue
        priority = max(MIN_PRIORITY, base_priority - index)
        try:
            seo_pages.enqueue_artist(name, priority=priority)
            queued += 1
        except ValueError:
            skipped += 1
    return {"queued": queued, "skipped": skipped}


# Kabaca populerlige gore siralanmis, global + Turkce karma baslangic listesi.
# Bu SADECE bir tohum (seed) — ilk yayin oncelik sirasini belirler, sonrasinda
# kuyruga baska sanatcilar da (farkli kaynaklardan) normal oncelikle eklenebilir.
STARTER_TOP_ARTISTS: list[str] = [
    # --- Global superstar (en yuksek oncelik) ---
    "Taylor Swift", "Drake", "The Weeknd", "Bad Bunny", "Ed Sheeran",
    "Ariana Grande", "Billie Eilish", "Beyonce", "Rihanna", "Justin Bieber",
    "Kanye West", "Eminem", "Adele", "Dua Lipa", "Bruno Mars",
    "Post Malone", "Travis Scott", "Kendrick Lamar", "SZA", "Doja Cat",
    "Olivia Rodrigo", "Harry Styles", "Lady Gaga", "Katy Perry", "Shakira",
    "Coldplay", "Imagine Dragons", "Maroon 5", "Sam Smith", "Lizzo",
    "Cardi B", "Nicki Minaj", "Megan Thee Stallion", "J Balvin", "Karol G",
    "Rosalia", "Peso Pluma", "Feid", "Anitta", "Charlie Puth",
    "Shawn Mendes", "Camila Cabello", "Selena Gomez", "Miley Cyrus",
    "Demi Lovato", "Halsey", "Lana Del Rey", "Sia", "Pink",
    "Alicia Keys", "John Legend", "Chris Brown", "Usher", "Lil Wayne",
    "Jay-Z", "Nas", "50 Cent", "Snoop Dogg", "Dr. Dre",
    "Future", "21 Savage", "Lil Baby", "Playboi Carti", "Metro Boomin",
    "Tyler The Creator", "Frank Ocean", "Childish Gambino", "J. Cole",
    "Anderson .Paak", "H.E.R.", "Summer Walker", "Jhene Aiko",
    "Bryson Tiller", "Khalid", "Zayn", "Niall Horan", "One Direction",
    "Backstreet Boys", "NSYNC", "Spice Girls", "Britney Spears",
    "Christina Aguilera", "Madonna", "Michael Jackson", "Whitney Houston",
    "Mariah Carey", "Celine Dion", "Elton John", "Queen", "The Beatles",
    "Rolling Stones", "Led Zeppelin", "Pink Floyd", "AC/DC", "Metallica",
    "Guns N Roses", "Nirvana", "Red Hot Chili Peppers", "Foo Fighters",
    "Linkin Park", "Green Day", "Blink-182", "Twenty One Pilots",
    "Panic! at the Disco", "Fall Out Boy", "My Chemical Romance",
    "Arctic Monkeys", "The 1975", "Radiohead", "U2", "Oasis", "Muse",
    "Florence and the Machine", "Lorde", "Bebe Rexha", "Meghan Trainor",
    "Kesha", "Avril Lavigne", "P!nk", "Sabrina Carpenter", "Chappell Roan",
    "Ice Spice", "Gunna", "Lil Durk", "NBA YoungBoy", "Central Cee",
    "Dave", "Stormzy", "Burna Boy", "Wizkid", "Davido", "Rema",
    "Tems", "Ayra Starr", "Zara Larsson",
    "Tove Lo", "Robyn", "ABBA", "Avicii", "Calvin Harris", "David Guetta",
    "Martin Garrix", "Marshmello", "Kygo", "Alan Walker", "Zedd",
    "Diplo", "Skrillex", "The Chainsmokers", "Swedish House Mafia",
    "Daft Punk", "Justice", "Disclosure", "Flume", "ODESZA",
    # --- Latin ---
    "Ozuna", "Maluma", "Daddy Yankee", "Nicky Jam", "Wisin y Yandel",
    "Rauw Alejandro", "Anuel AA", "Sech", "Myke Towers", "Farruko",
    "Manuel Turizo", "Sebastian Yatra", "Carlos Vives", "Juanes",
    "Marc Anthony", "Romeo Santos", "Prince Royce", "Luis Fonsi",
    "Enrique Iglesias", "Ricky Martin", "Gloria Estefan", "Christian Nodal",
    "Grupo Firme", "Fuerza Regida", "Junior H", "Natanael Cano",
    # --- K-pop ---
    "BTS", "Blackpink", "Twice", "Stray Kids", "Seventeen", "NewJeans",
    "IU", "EXO", "Aespa", "Itzy", "NCT", "TXT", "Ateez", "Le Sserafim",
    "IVE", "Red Velvet", "Big Bang", "Psy", "G-Dragon", "Jungkook",
    # --- Turkce pop/rock/arabesk/rap ---
    "Tarkan", "Sezen Aksu", "Ajda Pekkan", "Baris Manco", "MFO",
    "Sertab Erener", "Mustafa Sandal", "Kenan Dogulu", "Hadise",
    "Aleyna Tilki", "Edis", "Simge", "Gulsen", "Ebru Gundes", "Sila",
    "Yildiz Tilbe", "Muslum Gurses", "Ferdi Tayfur", "Zeki Muren",
    "Orhan Gencebay", "Ibrahim Tatlises", "Duman", "maNga", "Athena",
    "Mor ve Otesi", "Teoman", "Gripin", "Yalin", "Mabel Matiz", "Ceza",
    "Sagopa Kajmer", "Ezhel", "Norm Ender", "Motive", "Melike Sahin",
    "Zeynep Bastik", "Reynmen", "Sevval Sam", "Model", "Emre Aydin",
    "Buray", "Kalben", "Sebnem Ferah", "Cem Adrian", "Nil Karaibrahimgil",
    "Yildiz Ismen", "Rafet El Roman", "Emrah", "Ismail YK", "Gokhan Turkmen",
    "Ceylan Ertem", "Merve Ozbey", "Irem Derici", "Aleyna Ozbey",
    "Berkay", "Murat Boz", "Hande Yener", "Demet Akalin", "Bengu",
    "Soner Sarikabadayi", "Levent Yuksel", "Nihat Dogan",
    "Volkan Konak", "Kubat", "Grup Vitamin", "Metin Senturk",
    "Ayyuka", "UZI", "Batu Akdeniz", "Semicenk", "Ben Fero",
    "Aycan", "Melek Mosso", "Derya Ulug",
    "Simge Sagin", "Gaye Su Akyol",
]


def seed_starter(base_priority: int = 1000) -> dict:
    """Bundled top-sanatci listesini (STARTER_TOP_ARTISTS) EN YUKSEK oncelikle
    kuyruga ekler — gunluk build cron'u (bkz. api._seo_build_cron) once
    bunlarla baslasin diye. Operator bunu bir kere calistirir, sonrasi
    otomatik/kademeli devam eder."""
    return seed_from_list(STARTER_TOP_ARTISTS, base_priority)


# --- 'song' seed: STARTER_TOP_ARTISTS'in Deezer top parcalari ----------------

def _deezer_top_tracks(artist_name: str, limit: int) -> list[str]:
    """Deezer'da sanatciyi arar (anahtarsiz genel arama uc noktasi), ilk
    sonucun ID'sini alir, /artist/{id}/top uc noktasindan en fazla `limit`
    parcayi "Sanatci - Sarki" formatinda metin listesi olarak doner (bkz.
    seo_pages.enqueue_song / _split_song_query ile ayni format). Ag hatasinda,
    sanatci bulunamazsa veya top parca listesi bossa [] doner — exception
    firlatmaz."""
    try:
        resp = requests.get(
            _DEEZER_SEARCH_ARTIST_URL, params={"q": artist_name, "limit": 1},
            timeout=_DEEZER_TIMEOUT,
        )
        resp.raise_for_status()
        artist_results = (resp.json() or {}).get("data") or []
    except (requests.RequestException, ValueError):
        return []
    if not artist_results:
        return []
    artist_id = artist_results[0].get("id") if isinstance(artist_results[0], dict) else None
    if artist_id is None:
        return []

    try:
        resp = requests.get(
            _DEEZER_ARTIST_TOP_URL.format(id=artist_id), params={"limit": limit},
            timeout=_DEEZER_TIMEOUT,
        )
        resp.raise_for_status()
        top_tracks = (resp.json() or {}).get("data") or []
    except (requests.RequestException, ValueError):
        return []

    queries: list[str] = []
    for track in top_tracks[:limit]:
        if not isinstance(track, dict):
            continue
        title = track.get("title")
        track_artist = (track.get("artist") or {}).get("name") or artist_name
        if title:
            queries.append(f"{track_artist} - {title}")
    return queries


def seed_songs_from_starter(per_artist: int = 3, base_priority: int = 500) -> dict:
    """STARTER_TOP_ARTISTS'teki her sanatci icin Deezer'dan en fazla
    `per_artist` top parca bulur ve enqueue_song ile azalan oncelikle kuyruga
    ekler (STARTER_TOP_ARTISTS sirasindaki ilk sanatcinin ilk parcasi en
    yuksek onceligi alir; MIN_PRIORITY tabanin altina inmez).

    Her sanatci bagimsiz guardli: biri (Deezer'da bulunamadi, ag hatasi, top
    parca listesi bos) basarisiz olursa digerleri etkilenmez, sessizce
    atlanir — asla cokme. Idempotent (enqueue_song zaten bekleyen ayni
    sorguyu yutar). Doner: {'queued': N}."""
    if per_artist <= 0:
        raise ValueError("per_artist pozitif olmali")

    queued = 0
    index = 0
    for artist_name in STARTER_TOP_ARTISTS:
        try:
            queries = _deezer_top_tracks(artist_name, per_artist)
        except Exception:
            continue
        for query in queries:
            priority = max(MIN_PRIORITY, base_priority - index)
            try:
                seo_pages.enqueue_song(query, priority=priority)
                queued += 1
            except ValueError:
                pass
            index += 1
    return {"queued": queued}


# --- 'playlist' seed: populer tur/mood sorgulariyla Spotify arama -------------

def _spotify_search_playlist_urls(query: str, limit: int) -> list[str]:
    """Spotify Arama API'siyle (Client Credentials — bkz. spotify_client)
    playlist arar, sonuclari acilabilir Spotify playlist URL'leri olarak
    doner. spotify_client.available() False ise (kimlik bilgisi yok), token
    alinamazsa, ag hatasi olursa veya kota asilirsa [] doner — exception
    firlatmaz."""
    if not spotify_client.available():
        return []
    token = spotify_client.get_token()
    if not token:
        return []
    try:
        resp = requests.get(
            _SPOTIFY_SEARCH_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={"q": query, "type": "playlist", "limit": limit},
            timeout=_SPOTIFY_TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    if not isinstance(data, dict):
        return []
    items = ((data.get("playlists") or {}).get("items")) or []
    urls: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        external = (item.get("external_urls") or {}).get("spotify")
        if external:
            urls.append(external)
        elif item.get("id"):
            urls.append(f"https://open.spotify.com/playlist/{item['id']}")
    return urls


def seed_playlists_from_search(
    queries: list[str] | None = None, limit_per: int = 5, base_priority: int = 400,
) -> dict:
    """Populer tur/mood sorgulariyla (varsayilan DEFAULT_PLAYLIST_SEARCH_QUERIES)
    Spotify'da kullanici playlist'i arar ve bulunanlari enqueue_playlist ile
    azalan oncelikle kuyruga ekler. Spotify musait degilse (kimlik bilgisi
    yok / erisilemedi) AG ISTEGI BILE ATMADAN {'queued': 0} doner — exception
    firlatmaz. Her sorgu bagimsiz guardli: biri basarisiz olursa digerleri
    etkilenmez. Idempotent (enqueue_playlist zaten bekleyen ayni URL'yi
    yutar). Doner: {'queued': N}.

    NOT: `queries=None` varsayilan listeyi kullanir; `queries=[]` (acikca
    bos liste) is kurali ihlali sayilir ve ValueError firlatir — ikisi
    kasitli olarak farkli ele alinir (bos liste sessizce varsayilana
    dusseydi cagiranin hatasi fark edilmezdi)."""
    search_queries = DEFAULT_PLAYLIST_SEARCH_QUERIES if queries is None else queries
    if not search_queries:
        raise ValueError("Sorgu listesi bos olamaz")
    if not spotify_client.available():
        return {"queued": 0}

    queued = 0
    index = 0
    for query in search_queries:
        try:
            urls = _spotify_search_playlist_urls(query, limit_per)
        except Exception:
            continue
        for url in urls:
            priority = max(MIN_PRIORITY, base_priority - index)
            try:
                seo_pages.enqueue_playlist(url, priority=priority)
                queued += 1
            except ValueError:
                pass
            index += 1
    return {"queued": queued}
