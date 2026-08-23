"""Geriye donuk uyumluluk kabugu.

Gercek CLI artik paketin icinde: musical_seo/cli.py
Bu dosya `python cli.py audit ...` kullanimini calisir tutar; kurulumdan
sonra `musical-seo audit ...` komutu da ayni main()'i cagirir.
"""
from musical_seo.cli import main

if __name__ == "__main__":
    main()
