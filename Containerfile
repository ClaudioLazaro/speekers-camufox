# Containerfile — roda o votar.py em qualquer host (glibc velha, ARM64, etc.)
# Build:  podman build -t speekers-camufox -f Containerfile .
# Run:    podman run --rm -it \
#           -v ./config.json:/app/config.json:ro,Z \
#           -v ./votos.log:/app/votos.log:Z \
#           speekers-camufox
# Args customizados: adicione ao final, ex:
#           ... speekers-camufox uv run python votar.py --once

FROM docker.io/library/ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# xvfb: display virtual | curl: instalar o uv
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates xvfb \
 && rm -rf /var/lib/apt/lists/*

# uv (gerenciador python + deps)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# deps python primeiro (cache de camadas), depois libs do Firefox e o Camoufox
COPY pyproject.toml uv.lock ./
RUN uv sync \
 && uv run playwright install-deps firefox \
 && (uv run camoufox fetch || (sleep 10 && uv run camoufox fetch)) \
 && test -n "$(find /root/.cache/camoufox/browsers -type f | head -1)" \
 && echo "Camoufox browser OK na imagem"

COPY votar.py ./

# config.json e votos.log entram por volume em runtime (dados pessoais NUNCA na imagem)
CMD ["uv", "run", "python", "votar.py", "--votos", "0", "--paralelo", "6", "--intervalo", "15", "40"]
