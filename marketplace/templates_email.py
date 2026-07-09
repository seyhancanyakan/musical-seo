"""Retention/lead e-postalari icin kucuk HTML sablon yardimcilari.

Email-safe kisitlar: harici CSS yok (bircok mail istemcisi <style> ya da
harici sayfa yuklemesini engeller/bozar), tum stil INLINE, duzen basit
tek-sutun tablo (email istemcileri arasinda en tutarli render). Sozy Echo
marka rengi (#2d6bff) + net bir CTA butonu ile 'neo-brutal-ish' ama sade bir
gorunum hedeflenir.

Guvenlik: kullanici kaynakli TUM degerler (isim, alert detayi, sarki adi)
html.escape ile kacisiya alinir — HTML injection/bozuk markup imkansiz hale
gelir. Her fonksiyon (subject, html) ikilisi doner; gonderim marketplace.
mailer.send_email'e devredilir (bu modul network'e hic dokunmaz).
"""
from __future__ import annotations

import html
import os

_BRAND_BLUE = "#2d6bff"
_DEFAULT_SITE_URL = "https://sozyecho.live"


def _site_url() -> str:
    return os.environ.get("SEO_SITE_URL", _DEFAULT_SITE_URL).rstrip("/")


def _greeting(name: str) -> str:
    safe_name = html.escape((name or "").strip())
    return f"Merhaba {safe_name}," if safe_name else "Merhaba,"


def _wrap(title: str, body_html: str, cta_label: str, cta_href: str | None = None) -> str:
    """Ortak e-posta iskeleti: marka basligi + govde + CTA butonu + footer."""
    href = html.escape(cta_href or _site_url(), quote=True)
    safe_title = html.escape(title or "")
    safe_cta = html.escape(cta_label or "")
    return f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f4f5f7;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">
            <tr>
              <td style="background:{_BRAND_BLUE};padding:20px 32px;">
                <span style="color:#ffffff;font-size:20px;font-weight:bold;">Sozy Echo</span>
              </td>
            </tr>
            <tr>
              <td style="padding:32px;color:#1a1a1a;font-size:15px;line-height:1.55;">
                <h1 style="margin:0 0 16px;font-size:20px;color:#111111;">{safe_title}</h1>
                {body_html}
                <table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:24px;">
                  <tr>
                    <td style="border-radius:8px;background:{_BRAND_BLUE};">
                      <a href="{href}" style="display:inline-block;padding:12px 24px;color:#ffffff;text-decoration:none;font-weight:bold;font-size:14px;border-radius:8px;">{safe_cta}</a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 32px;color:#8a8f98;font-size:12px;border-top:1px solid #f0f0f0;">
                Sozy Echo &mdash; muzik SEO platformu.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def welcome_email(name: str) -> tuple[str, str]:
    """Ilk e-posta yakalamasinda (huni girisi) karsilama maili."""
    subject = "Sozy Echo'e hos geldin!"
    body = f"""
        <p style="margin:0 0 16px;">{_greeting(name)}</p>
        <p style="margin:0 0 16px;">Sozy Echo'e katildigin icin tesekkurler!
        Sarkinin SEO potansiyelini gormek ve takibe almak icin ucretsiz
        raporunu inceleyebilirsin.</p>
    """
    return subject, _wrap("Hos geldin", body, "Ucretsiz raporunu gor")


def cover_alert_email(name: str, detail: str) -> tuple[str, str]:
    """Takip edilen sarkida yeni izinsiz cover adayi bulundugunda."""
    subject = "Sarkinin izinsiz cover'i bulundu"
    safe_detail = html.escape(detail or "")
    body = f"""
        <p style="margin:0 0 16px;">{_greeting(name)}</p>
        <p style="margin:0 0 16px;">{safe_detail}</p>
    """
    return subject, _wrap("Cover uyarisi", body, "Adaylari incele")


def fraud_alert_email(name: str, detail: str) -> tuple[str, str]:
    """Takip edilen bir playlist icin riskli/sahte adli analiz raporu ciktiginda."""
    subject = "Takip ettigin playlist'te suphali aktivite"
    safe_detail = html.escape(detail or "")
    body = f"""
        <p style="margin:0 0 16px;">{_greeting(name)}</p>
        <p style="margin:0 0 16px;">{safe_detail}</p>
    """
    return subject, _wrap("Fraud uyarisi", body, "Raporu incele")


def score_alert_email(name: str, track: str, old: float, new: float) -> tuple[str, str]:
    """Takip edilen bir sarkinin SEO skoru anlamli miktarda degistiginde."""
    safe_track = html.escape(track or "")
    subject = f"SEO skorun degisti: {track or ''}"
    direction = "yukseldi" if new >= old else "dustu"
    body = f"""
        <p style="margin:0 0 16px;">{_greeting(name)}</p>
        <p style="margin:0 0 16px;"><strong>{safe_track}</strong> icin SEO
        skorun {old:.0f} &rarr; {new:.0f} olarak {direction}.</p>
    """
    return subject, _wrap("Skor degisimi", body, "Skoru incele")
