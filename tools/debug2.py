"""Debug: abre o modal de confirmacao e despeja a estrutura real dos elementos."""
import json
from pathlib import Path
from camoufox.sync_api import Camoufox

cfg = json.loads(Path("config.json").read_text())

with Camoufox(headless="virtual") as browser:
    page = browser.new_page()
    page.goto(cfg["url"], wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3500)
    page.get_by_role("button", name="Votar agora").click()
    page.wait_for_timeout(2500)
    page.locator('input[type="email"]').first.press_sequentially(cfg["email"], delay=70)
    page.locator('input[type="tel"]').first.press_sequentially(cfg["telefone"], delay=80)
    page.wait_for_timeout(800)
    page.get_by_role("button", name="Continuar para voto").click()
    print("clicou; aguardando modal...")

    for tentativa in range(6):
        page.wait_for_timeout(5000)
        n = page.locator("text=Confirmar seu voto").count()
        print(f"t+{(tentativa+1)*5}s: 'Confirmar seu voto' no DOM: {n}")
        if n:
            break

    print("\n--- elementos clicaveis ---")
    els = page.locator("button, [role='button'], a, input[type='submit']")
    for i in range(els.count()):
        e = els.nth(i)
        try:
            print(i, e.evaluate("el => el.tagName"), repr(e.inner_text()[:80]),
                  "visivel:", e.is_visible())
        except Exception as ex:
            print(i, "erro:", ex)

    print("\n--- dialogs ---")
    for sel in ["[role='dialog']", ".fixed", "[class*='modal']"]:
        loc = page.locator(sel)
        print(sel, "count:", loc.count())

    html = page.locator("text=Confirmar seu voto").first
    if html.count():
        print("\n--- HTML do elemento 'Confirmar seu voto' ---")
        print(html.evaluate("el => el.outerHTML")[:500])
        print("\n--- ancestral mais proximo ---")
        print(html.evaluate(
            "el => {let p=el; for(let i=0;i<4&&p.parentElement;i++) p=p.parentElement; return p.outerHTML.slice(0,1500)}"))

    page.screenshot(path="debug2.png", full_page=True)
    print("\nscreenshot: debug2.png")
