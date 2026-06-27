.PHONY: run lint typecheck test

run:
	PYTHONPATH=src uv run python run_pob_post_install.py

lint:
	PYTHONPATH=src uv run ruff check src/

typecheck:
	PYTHONPATH=src uv run python -m py_compile src/pob_post_install/main.py

test:
	PYTHONPATH=src uv run python -c "from pob_post_install.registry import load_packages; from pathlib import Path; files=list(sorted(Path('packages').glob('*.toml'))); total=sum(len(load_packages(p)) for p in files); assert total > 0, 'no packages'; print(f'OK ({total} packages across {len(files)} files)')"
