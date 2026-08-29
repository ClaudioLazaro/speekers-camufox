.PHONY: setup run once

# instala dependencias python + o Firefox do Camoufox (primeiro uso)
setup:
	uv sync
	uv run camoufox fetch

# regime continuo: 6 navegadores, sem limite, ate Ctrl+C
run:
	uv run python votar.py --votos 0 --paralelo 6

# 1 voto de teste
once:
	uv run python votar.py --once
