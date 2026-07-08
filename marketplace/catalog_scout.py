"""Top sanatci seed motoru: programatik SEO kuyruguna (bkz. seo_pages.build_queue)
en bilinen sanatcilari YUKSEK oncelikle ekler. Boylece gunluk arka plan uretimi
(bkz. marketplace.api._seo_build_cron) once bu sanatcilarla baslar, sonra
kuyruga eklenen diger sanatcilarla devam eder — "once top sanatcilar, sonra
sistem hergun yavas yavas buyusun" akisi.

Yasal/etik: bu modul AG ERISIMI YAPMAZ. Sadece bu dosyadaki bundled listeyi
(STARTER_TOP_ARTISTS) veya cagiranin verdigi ismi kuyruga yazar — 3. parti
veri kazima YOK. seo_pages.enqueue_artist zaten idempotent oldugu icin ayni
ismi tekrar seed etmek yeni 'pending' satir acmaz; boylece kaldigi yerden
devam edilebilir (script her calistiginda sifirdan baslamaz).

Hata sozlesmesi: is kurali ihlalleri ValueError (aksanli Turkce) — API
katmani bunu 400'e cevirir.
"""
from __future__ import annotations

from marketplace import seo_pages

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
