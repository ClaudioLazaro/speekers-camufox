.PHONY: setup run once container-build container-run container-once

# instala dependencias python + o Firefox do Camoufox (primeiro uso, modo nativo)
setup:
	uv sync
	uv run camoufox fetch

# regime continuo nativo: 6 navegadores, sem limite, ate Ctrl+C
run:
	uv run python votar.py --votos 0 --paralelo 6 --intervalo 15 40

# 1 voto de teste (nativo)
once:
	uv run python votar.py --once

# --- container (Rocky/RHEL 8, ARM64, glibc antiga; usa podman ou docker) ---

CONTAINER_RT ?= podman
IMAGE = speekers-camufox
PARALELOS ?= 6
INTERVALO ?= 15 40

container-build:
	$(CONTAINER_RT) build -t $(IMAGE) -f Containerfile .

container-run:
	touch votos.log
	$(CONTAINER_RT) run --rm -it \
	  -v ./config.json:/app/config.json:ro,Z \
	  -v ./votos.log:/app/votos.log:Z \
	  $(IMAGE) uv run python votar.py --votos 0 --paralelo $(PARALELOS) --intervalo $(INTERVALO)

container-once:
	$(CONTAINER_RT) run --rm -it \
	  -v ./config.json:/app/config.json:ro,Z \
	  $(IMAGE) uv run python votar.py --once
