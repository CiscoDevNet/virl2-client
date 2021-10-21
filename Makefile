
.phony: export docs

# https://github.com/python-poetry/poetry/issues/3160
# when resolved, we should be able to run with hashes
tests/requirements.txt: poetry.lock
	poetry export --format=requirements.txt --dev --without-hashes --output=$@

clean:
	rm -rf dist virl2_client.egg-info .built
	find . -not -path ./.venv -depth -type f -name '*.pyc' -exec rm {} \; || true
	find . -not -path ./.venv -depth -type d -name '__pycache__' -exec rmdir {} \; || true
	cd docs && make clean

poetry:
	poetry update

export: tests/requirements.txt
	@echo "exported dependencies"

docs: docs/dist

docs/dist:
	@pushd docs && make buildapi
	@sphinx-build -b html -t internal docs/source docs/dist
