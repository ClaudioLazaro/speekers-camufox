# Voto Torcedor Automático — TheBestSpeaker

Automação do **voto torcedor** (que o próprio site declara ilimitado) usando
Firefox real via [Camoufox](https://github.com/daijro/camoufox), com confirmação
pela resposta HTTP da API (só conta voto quando o servidor devolve 201).

O voto único e o cadastro inicial (nome/CPF/nascimento) **não** são automatizados:
cada pessoa da lista precisa votar uma vez manualmente no site antes.

## Requisitos

- Linux com [uv](https://docs.astral.sh/uv/) instalado
- Xvfb (display virtual para os navegadores):
  - Arch: `sudo pacman -S xorg-server-xvfb`
  - Debian/Ubuntu: `sudo apt install xvfb`

## Setup (primeira vez)

```bash
git clone <repo> && cd thebestspeaker
make setup                 # uv sync + download do Firefox do Camoufox (~660MB)
cp config.example.json config.json
# edite config.json: url do palestrante e a lista "votantes" (email + telefone reais, ja cadastrados no site)
```

O GeoIP (para uso com proxies) baixa sozinho na primeira execução.

## Uso

```bash
make run                                    # 6 navegadores, sem limite, ate Ctrl+C
make once                                   # 1 voto de teste

uv run python votar.py --votos 50           # 50 votos, 1 navegador
uv run python votar.py --votos 0 --paralelo 6 --intervalo 15 40
uv run python votar.py --votos 100 --paralelo 12
```

Parâmetros:

| flag | efeito |
|---|---|
| `--votos N` | total de votos; `0` = sem limite até Ctrl+C |
| `--paralelo` | 1 navegador por votante do config |
| `--paralelo N` | N navegadores (votantes reusados em rodízio) |
| `--intervalo MIN MAX` | segundos entre votos por navegador |
| `--intervalo-global MIN MAX` | segundos entre tentativas somando TODOS os navegadores |
| `--once` | 1 voto (teste) |

Cada navegador é um Firefox completo (~400-800MB RAM). O script avisa antes
de iniciar se `N x 750MB` não couber na RAM disponível.

## Como funciona

Fluxo por voto: `Votar agora` → preenche email/telefone → `Continuar para voto`
→ modal → `Confirmar seu voto` → confirmação via `POST /vote/torcida` (HTTP 201).
A propaganda exibida depois é cosmética e não é esperada.

Estratégia anti-bloqueio (descoberta empiricamente — o 403/429 do site é por
**sessão do navegador**, não por IP):

- **Throttle → sessão nova**: ao tomar 403/429, o worker fecha o Firefox e abre
  um novo (cookies zerados) após 45-90s, em vez de morrer ou dormir longos períodos
- **Rotação preventiva**: cada navegador se reinicia a cada 15-25 votos
- **Ritmo global**: distância mínima entre tentativas somando todos os navegadores
  (`intervalo_global_segundos`, padrão 20-35s ≈ 2 votos/min de teto)
- **Cooldown global curto**: quando um worker é throttlado, os demais seguram ~90s
- O processo nunca morre por throttling — só com Ctrl+C

Logs: tudo vai para o terminal e para `votos.log` (gitignored). Erros salvam
screenshots `debug_*.png` (gitignored).

## Proxies (opcional)

Lista `"proxies"` no config, distribuída em rodízio entre os navegadores:

```json
"proxies": ["socks5://127.0.0.1:9050", "http://usuario:senha@host:porta"]
```

Com proxy ativo, o Camoufox ajusta timezone/locale ao IP (`geoip=True`).
Proxies residenciais têm score de reCAPTCHA muito melhor que Tor/datacenter.

## Ferramentas de diagnóstico (tools/)

- `tools/recon.py` — mapeia os botões/fluxo da página (útil se o site mudar)
- `tools/debug2.py` — despeja a estrutura DOM do modal de confirmação
- `tools/teste_proxy.py` — compara IP direto vs IP via proxy

## Avisos

- Use apenas dados reais de pessoas que já se cadastraram no site. O script
  não preenche CPF nem faz cadastro, não gera emails falsos e não tenta
  burlar CAPTCHA — se o site exibir desafio, o fluxo para.
- `config.json` contém dados pessoais e está no `.gitignore` de propósito.
