"""Recon: abre a pagina, preenche dados dummy, clica 'Continuar para voto'
e lista os botoes/avisos reais. NAO clica em votar — nenhum voto e lancado."""
from camoufox.sync_api import Camoufox

URL = "https://speaker.thebestspeaker.com.br/vote/lauro-eduardo-rufini-pinheiro-bthrtz"

with Camoufox(headless="virtual") as browser:
    page = browser.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)

    print("TITULO:", page.title())
    print("BOTOES INICIAIS:", page.get_by_role("button").all_inner_texts())

    page.get_by_role("button", name="Votar agora").click()
    page.wait_for_timeout(3000)
    print("BOTOES APOS 'Votar agora':", page.get_by_role("button").all_inner_texts())

    email = page.locator('input[type="email"]').first
    email.click()
    email.press_sequentially("recon.teste@gmail.com", delay=60)
    fone = page.locator('input[type="tel"]').first
    fone.click()
    fone.press_sequentially("11988887777", delay=70)
    page.wait_for_timeout(1000)
    print("VALOR FONE APOS MASCARA:", fone.input_value())

    page.get_by_role("button", name="Continuar para voto").click()
    page.wait_for_timeout(7000)

    print("URL ATUAL:", page.url)
    print("BOTOES DEPOIS:", page.get_by_role("button").all_inner_texts())
    body = page.inner_text("body")
    print("TEXTO (primeiros 1200 chars):")
    print(body[:1200])
    page.screenshot(path="recon.png", full_page=True)
    print("screenshot: recon.png")
