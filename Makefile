.phony: all build lint format typecheck check publish publish-test \
		clean demo showcase test memory-test performance-test
		

all: build


build: clean
	@uv pip install -e .

lint:
	@uv run ruff check --fix src/

format:
	@uv run ruff format src/

typecheck:
	@uv run mypy src/

check:
	@uv run twine check dist/*

publish-test:
	@uv run twine upload -r testpypi dist/*

publish:
	@uv run twine upload dist/*

clean:
	@rm -rf build src/pymui/pymui.*.so
	@find . -type d -name __pycache__ -exec rm -rf {} \; -prune
	@find . -type d -path ".*_cache"  -exec rm -rf {} \; -prune

demo:
	@uv run python examples/demo.py

showcase:
	@uv run python examples/showcase.py

test:
	@uv run pytest

test-window:
	@PYMUI_WINDOW_TESTS=1 uv run pytest

memory-test:
	@echo "Running memory leak detection..."
	@uv run python scripts/memory_leak_test.py --verbose

performance-test:
	@echo "Running performance benchmarks..."
	@uv run python scripts/benchmark.py
