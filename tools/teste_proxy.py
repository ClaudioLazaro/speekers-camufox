"""Teste do caminho de proxy: IP direto vs IP via Tor (socks5 127.0.0.1:9050)."""
import time
from camoufox.sync_api import Camoufox

URL_IP = "https://api.ipify.org"

def pega_ip(proxy=None):
    kwargs = {"headless": "virtual"}
    if proxy:
        kwargs["proxy"] = proxy
        kwargs["geoip"] = True  # ajusta timezone/locale ao IP do proxy
    with Camoufox(**kwargs) as b:
        page = b.new_page()
        page.goto(URL_IP, timeout=60000)
        return page.inner_text("body").strip()

print("IP direto:", pega_ip())
time.sleep(2)
print("IP via Tor:", pega_ip({"server": "socks5://127.0.0.1:9050"}))
