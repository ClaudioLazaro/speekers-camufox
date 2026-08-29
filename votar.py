"""
Voto torcedor automatico - TheBestSpeaker
-----------------------------------------
O proprio site declara que o "voto torcedor" e ilimitado. Este script
automatiza APENAS esse voto, usando dados reais de pessoas ja cadastradas
no site (lista "votantes" no config.json), em Firefox real (Camoufox),
executando o reCAPTCHA do site normalmente como um visitante humano.

Limites propositais:
  - nao gera nem usa emails/telefones/CPF falsos;
  - nao faz o cadastro inicial nem o voto unico (isso e manual, uma vez
    por pessoa, direto no site);
  - nao tenta burlar CAPTCHA nem OTP;
  - para sozinho se o site apresentar desafio ou 3 erros seguidos.

Uso:
  source .venv/bin/activate
  python votar.py --votos 20                 # 20 votos, 1 navegador
  python votar.py --votos 20 --paralelo      # 1 navegador por votante do config
  python votar.py --votos 20 --paralelo 12   # 12 navegadores (reusa votantes em rodizio)
  python votar.py --votos 0                  # sem limite, ate Ctrl+C
  python votar.py --votos 0 --paralelo 12    # 12 navegadores ate Ctrl+C
  python votar.py --once                     # 1 voto, para teste

Opcional: --intervalo MIN MAX   (segundos entre votos; padrao: config.json)

Cada navegador paralelo e um Firefox completo (~400-800MB RAM).
"""

import argparse
import json
import multiprocessing as mp
import random
import sys
import time
from pathlib import Path

BASE = Path(__file__).parent
CONFIG_PATH = BASE / "config.json"
LOG_PATH = BASE / "votos.log"

API_HOST = "services-prd.profissionaissa.com"

# fluxo descoberto no teste real:
# "Votar agora" -> form -> "Continuar para voto" -> modal -> "Confirmar seu voto" -> propaganda -> concluido
ROTULOS_CONFIRMA = ["Confirmar seu voto", "Confirmar voto", "Confirmar"]
# NOTA: "Continuar" NAO pode entrar aqui — casaria com "Continuar para voto"
ROTULOS_FECHAR = ["Fechar", "Pular", "Pular propaganda", "Fechar propaganda"]


def log(msg: str, wid: int = 0) -> None:
    tag = f"[W{wid}] " if wid else ""
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {tag}{msg}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def carregar_config() -> dict:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    votantes = cfg.get("votantes") or []
    validos = [v for v in votantes
               if "@" in v.get("email", "") and "exemplo.com" not in v["email"]
               and len(str(v.get("telefone", ""))) >= 10]
    if not validos:
        sys.exit("Preencha config.json com ao menos um votante real (email + telefone cadastrados no site).")
    cfg["votantes"] = validos
    cfg["proxies"] = cfg.get("proxies") or []
    return cfg


def parse_proxy(url: str) -> dict:
    """'http://user:pass@host:port' ou 'socks5://host:port' -> dict do Playwright."""
    from urllib.parse import urlparse
    u = urlparse(url)
    proxy = {"server": f"{u.scheme}://{u.hostname}:{u.port}"}
    if u.username:
        proxy["username"] = u.username
        proxy["password"] = u.password or ""
    return proxy


def mascara_proxy(url: str) -> str:
    """Esconde usuario/senha no log."""
    from urllib.parse import urlparse
    u = urlparse(url)
    return f"{u.scheme}://{u.hostname}:{u.port}"


def achar_botao(page, rotulos, exact=False):
    """Procura por role button OU link (o 'Confirmar seu voto' e um <a id=votou>).
    exact=True exige o nome exato (evita 'Continuar' casar com 'Continuar para voto')."""
    for r in rotulos:
        for role in ("button", "link"):
            b = page.get_by_role(role, name=r, exact=exact)
            if b.count() > 0 and b.first.is_visible():
                return b.first
        if r == "Confirmar seu voto":
            css = page.locator("a#votou")
            if css.count() > 0 and css.first.is_visible():
                return css.first
    return None


def achar_fechar(page):
    """Botao de fechar/pular: nome exato ou X com aria-label."""
    b = achar_botao(page, ROTULOS_FECHAR, exact=True)
    if b:
        return b
    for sel in ('button[aria-label="Fechar"]', 'button[aria-label="fechar"]',
                'button[aria-label="Close"]', 'button[aria-label="Pular"]'):
        loc = page.locator(sel)
        if loc.count() > 0 and loc.first.is_visible():
            return loc.first
    return None


def identificar_votante(page, cfg: dict, votante: dict, wid: int) -> bool:
    """Abre o formulario, preenche email/telefone e avanca ate o modal."""
    page.goto(cfg["url"], wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(random.randint(1200, 2500))

    page.get_by_role("button", name="Votar agora").click()

    # espera o form abrir; se nao abrir, reclica (clique perdido acontece)
    email = page.locator('input[type="email"]').first
    for _ in range(3):
        try:
            email.wait_for(state="visible", timeout=8000)
            break
        except Exception:
            log("form nao abriu; reclicando 'Votar agora'", wid)
            page.get_by_role("button", name="Votar agora").click()
    else:
        log("ERRO: formulario de voto nao abriu apos 3 tentativas.", wid)
        return False
    page.wait_for_timeout(random.randint(400, 900))

    email.click()
    email.press_sequentially(votante["email"], delay=random.randint(40, 90))
    page.wait_for_timeout(random.randint(300, 600))

    fone = page.locator('input[type="tel"]').first
    fone.click()
    fone.press_sequentially(str(votante["telefone"]), delay=random.randint(45, 100))
    page.wait_for_timeout(random.randint(400, 800))

    page.get_by_role("button", name="Continuar para voto").click()
    log(f"clicou em 'Continuar para voto' ({votante['email']})", wid)

    # escuta a resposta REAL da API em vez de so olhar a tela
    try:
        resp = page.wait_for_event(
            "response",
            predicate=lambda r: API_HOST in r.url and "/vote/voter" in r.url
                                and r.request.method == "POST",
            timeout=30000,
        )
    except Exception:
        log("ERRO: API do site nao respondeu em 30s (throttling ou maquina sobrecarregada).", wid)
        page.screenshot(path=str(BASE / f"debug_painel_w{wid}.png"), full_page=True)
        return False

    log(f"API respondeu HTTP {resp.status} ({resp.url.split(API_HOST)[-1][:60]})", wid)
    if resp.status in (403, 429):
        log(f"throttling do site (HTTP {resp.status}) — vai dar backoff.", wid)
        return None
    if resp.status >= 400:
        try:
            corpo = resp.text()[:200]
        except Exception:
            corpo = "<sem corpo>"
        log(f"ERRO da API: HTTP {resp.status} — {corpo}", wid)
        return False

    if achar_botao(page, ["Cadastrar e votar"]):
        log(f"ERRO: site pediu cadastro para {votante['email']} (nome/CPF/nascimento).", wid)
        log("Esse email ainda nao e votante. Vote uma vez MANUALMENTE com ele e rode de novo.", wid)
        return False

    # com a API OK, o modal abre em instantes; poll curto so para achar o botao
    for _ in range(15):
        if achar_botao(page, ROTULOS_CONFIRMA):
            log("modal do voto torcedor aberto", wid)
            return True
        page.wait_for_timeout(1000)

    log("ERRO: API OK mas modal nao abriu em 15s.", wid)
    page.screenshot(path=str(BASE / f"debug_painel_w{wid}.png"), full_page=True)
    return False


def votar_torcida(page, wid: int) -> bool:
    """Um voto torcedor: confirma no modal, atravessa a propaganda, fecha."""
    botao = achar_botao(page, ROTULOS_CONFIRMA)
    if not botao:
        reabrir = achar_botao(page, ["Votar de novo", "VOTAR DE NOVO"]) or \
                  achar_botao(page, ["Continuar para voto"])
        if not reabrir:
            log("nem modal, nem 'Votar de novo', nem 'Continuar para voto' na tela.", wid)
            return False
        reabrir.click()
        page.wait_for_timeout(3000)
        botao = achar_botao(page, ROTULOS_CONFIRMA)
        if not botao:
            log("modal de confirmacao nao abriu.", wid)
            page.screenshot(path=str(BASE / f"debug_reabrir_w{wid}.png"), full_page=True)
            return False

    # confirma pela RESPOSTA DA API, nao pela tela: o voto e registrado no clique,
    # a propaganda que vem depois e so cosmetica
    try:
        with page.expect_response(
            lambda r: API_HOST in r.url and "torcida" in r.url and r.request.method == "POST",
            timeout=30000,
        ) as resp_info:
            botao.click()
        resp = resp_info.value
    except Exception:
        log("ERRO: POST /vote/torcida nao respondeu em 30s.", wid)
        page.screenshot(path=str(BASE / f"debug_voto_w{wid}.png"), full_page=True)
        return False

    log(f"POST /vote/torcida -> HTTP {resp.status}", wid)
    if resp.status in (403, 429):
        log(f"throttling do site (HTTP {resp.status}) — vai dar backoff.", wid)
        return None
    if resp.status >= 400:
        try:
            corpo = resp.text()[:200]
        except Exception:
            corpo = "<sem corpo>"
        log(f"ERRO ao registrar voto: HTTP {resp.status} — {corpo}", wid)
        return False

    log("voto registrado pelo servidor.", wid)

    # fecha a propaganda/modal se houver botao (best-effort, sem travar o ciclo)
    page.wait_for_timeout(2500)
    fechar = achar_fechar(page)
    if fechar:
        fechar.click()
        page.wait_for_timeout(1000)
    return True


def worker(wid: int, cfg: dict, votante: dict, proxy_url, quota: int, intervalo: list,
           largada: int, ok_shared, tent_shared, lock, blocked_until, ultima_tentativa,
           intervalo_global: list) -> None:
    """Um navegador votando como `votante`. quota=0 significa sem limite.

    Estrategia anti-bloqueio (descoberta empirica): o 403/429 do site e por
    SESSAO do navegador, nao por IP — restartar o processo liberava na hora.
    Entao: ao tomar throttle, o worker fecha o Firefox e abre um novo (sessao
    limpa) apos espera curta; e a cada 15-25 votos reinicia preventivamente."""
    from camoufox.sync_api import Camoufox

    if largada:
        log(f"largada escalonada: aguardando {largada}s", wid)
        time.sleep(largada)

    via = f" via {mascara_proxy(proxy_url)}" if proxy_url else ""
    log(f"votando como {votante['email']}{via} (cota: {'infinita' if quota == 0 else quota})", wid)

    kwargs = {"headless": "virtual"}
    if proxy_url:
        kwargs["proxy"] = parse_proxy(proxy_url)
        kwargs["geoip"] = True

    cm = page = None

    def abrir_sessao():
        nonlocal cm, page
        fechar_sessao()
        cm = Camoufox(**kwargs)
        browser = cm.__enter__()
        page = browser.new_page()

    def fechar_sessao():
        nonlocal cm, page
        if cm:
            try:
                cm.__exit__(None, None, None)
            except Exception:
                pass
        cm = page = None

    feitos = falhas = throttles = votos_na_sessao = 0
    limite_sessao = random.randint(15, 25)
    try:
        abrir_sessao()
        while quota == 0 or feitos < quota:
            # cooldown global curto: quando um worker e throttlado, os demais
            # seguram um pouco enquanto ele troca de sessao
            with lock:
                resto = blocked_until.value - time.time()
            if resto > 0:
                espera = min(resto, 90) + random.uniform(2, 10)
                log(f"cooldown global ativo; dormindo {int(espera)}s", wid)
                time.sleep(espera)

            # ritmo global: distancia minima entre tentativas de TODOS os workers
            with lock:
                gap = random.uniform(*intervalo_global)
                dormir = max(0.0, gap - (time.time() - ultima_tentativa.value))
            if dormir > 0:
                time.sleep(dormir)
            with lock:
                ultima_tentativa.value = time.time()
                tent_shared.value += 1

            try:
                r1 = identificar_votante(page, cfg, votante, wid)
                sucesso = votar_torcida(page, wid) if r1 else r1  # None = throttle
            except Exception as e:
                log(f"excecao: {type(e).__name__}: {e}", wid)
                sucesso = False

            if sucesso is None:
                # throttle: sessao queimada -> navegador NOVO apos espera curta
                falhas = 0
                throttles += 1
                espera = random.randint(45, 90)
                with lock:
                    blocked_until.value = max(blocked_until.value, time.time() + espera)
                log(f"throttle {throttles} seguido(s); trocando de sessao em {espera}s", wid)
                fechar_sessao()
                time.sleep(espera)
                abrir_sessao()
                votos_na_sessao = 0
                limite_sessao = random.randint(15, 25)
                continue

            throttles = 0
            if sucesso:
                feitos += 1
                votos_na_sessao += 1
                falhas = 0
                with lock:
                    ok_shared.value += 1
                log(f"voto {feitos}{'' if quota == 0 else f'/{quota}'} confirmado", wid)

                # rotacao preventiva: navegador novo antes de o guard marcar a sessao
                if votos_na_sessao >= limite_sessao:
                    log(f"rotacao preventiva: {votos_na_sessao} votos nesta sessao; navegador novo", wid)
                    fechar_sessao()
                    time.sleep(random.randint(10, 25))
                    abrir_sessao()
                    votos_na_sessao = 0
                    limite_sessao = random.randint(15, 25)
            else:
                falhas += 1
                log(f"voto FALHOU ({falhas} seguidas)", wid)
                if falhas >= 3:
                    log("3 falhas seguidas — reiniciando sessao e seguindo.", wid)
                    fechar_sessao()
                    time.sleep(random.randint(30, 60))
                    abrir_sessao()
                    falhas = 0
                    votos_na_sessao = 0

            if quota == 0 or feitos < quota:
                espera = random.randint(*intervalo)
                log(f"aguardando {espera}s", wid)
                time.sleep(espera)
    except Exception as e:
        log(f"excecao fatal no worker: {type(e).__name__}: {e}", wid)
    finally:
        fechar_sessao()
        log(f"worker encerrado com {feitos} voto(s) confirmado(s).", wid)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--votos", type=int, default=None,
                        help="total de votos; 0 = sem limite, ate Ctrl+C (padrao: config)")
    parser.add_argument("--paralelo", nargs="?", const=0, type=int, default=None, metavar="N",
                        help="sem valor: 1 navegador por votante; com N: N navegadores (rodizio)")
    parser.add_argument("--once", action="store_true", help="roda um unico voto (teste)")
    parser.add_argument("--intervalo", type=int, nargs=2, metavar=("MIN", "MAX"), default=None,
                        help="segundos entre votos por navegador (sobrescreve config)")
    parser.add_argument("--intervalo-global", type=int, nargs=2, metavar=("MIN", "MAX"), default=None,
                        help="segundos entre tentativas SOMANDO todos os navegadores")
    args = parser.parse_args()

    cfg = carregar_config()
    votantes = cfg["votantes"]
    total = 1 if args.once else (args.votos if args.votos is not None else int(cfg.get("votos", 10)))
    intervalo = args.intervalo or cfg.get("intervalo_segundos", [8, 20])
    intervalo_global = args.intervalo_global or cfg.get("intervalo_global_segundos", [20, 35])

    # --paralelo ausente: 1 navegador | --paralelo puro: 1 por votante | --paralelo N: N
    if args.once or args.paralelo is None:
        n_workers = 1
    elif args.paralelo == 0:
        n_workers = len(votantes)
    else:
        n_workers = max(1, args.paralelo)

    # alerta de memoria: ~750MB por navegador contra RAM disponivel
    try:
        disp_mb = int(next(l.split()[1] for l in open("/proc/meminfo")
                           if l.startswith("MemAvailable"))) // 1024
        if n_workers * 750 > disp_mb:
            log(f"AVISO: {n_workers} navegadores pedem ~{n_workers * 750}MB e ha ~{disp_mb}MB "
                f"disponiveis. Risco de travar a maquina — considere menos paralelos.")
    except Exception:
        pass

    # divide o total entre os workers; 0 (infinito) fica 0 para todos
    if total == 0:
        quotas = [0] * n_workers
        desc = "sem limite (Ctrl+C para parar)"
    else:
        base, resto = divmod(total, n_workers)
        quotas = [base + (1 if i < resto else 0) for i in range(n_workers)]
        desc = str(total)

    log(f"iniciando: {desc} voto(s) | {'paralelo: ' + str(n_workers) + ' navegador(es)' if n_workers > 1 else '1 navegador'} "
        f"| {len(votantes)} votante(s) no config | {cfg['url']}")

    lock = mp.Lock()
    ok_shared = mp.Value("i", 0)
    tent_shared = mp.Value("i", 0)
    blocked_until = mp.Value("d", 0.0)   # epoch: cooldown global compartilhado
    ultima_tentativa = mp.Value("d", 0.0)  # epoch da ultima tentativa (ritmo global)
    procs = []
    for wid in range(1, n_workers + 1):
        votante = votantes[(wid - 1) % len(votantes)]
        proxy_url = cfg["proxies"][(wid - 1) % len(cfg["proxies"])] if cfg["proxies"] else None
        largada = 0 if wid == 1 else random.randint(5, 12) * (wid - 1)
        p = mp.Process(target=worker,
                       args=(wid, cfg, votante, proxy_url, quotas[wid - 1], intervalo, largada,
                             ok_shared, tent_shared, lock, blocked_until, ultima_tentativa,
                             intervalo_global))
        p.start()
        procs.append(p)

    try:
        for p in procs:
            p.join()
    except KeyboardInterrupt:
        log("Ctrl+C recebido — encerrando navegadores...")
        for p in procs:
            p.terminate()
        for p in procs:
            p.join(timeout=10)

    log(f"FIM: {ok_shared.value} confirmado(s) de {tent_shared.value} tentado(s). "
        f"Detalhes em votos.log")


if __name__ == "__main__":
    main()
