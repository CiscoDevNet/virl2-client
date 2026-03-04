
.PHONY: export diff test coverage coverage-html

tests/requirements.txt: poetry.lock
	poetry export --format=requirements.txt --with dev --output=$@

clean:
	rm -rf dist virl2_client.egg-info .built .pytest_cache .coverage coverage.xml coverage.json htmlcov
	find . -depth -type f -name '*.pyc' -exec rm {} \; || true
	find . -depth -type d -name '__pycache__' -exec rmdir {} \; || true
	cd docs && make clean

poetry:
	poetry update

export: tests/requirements.txt
	@echo "exported dependencies"

diff:
	diff -ruN -X.gitignore -x.github -x.git -xdist -x.pytest_cache ./ ../simple/virl2_client/ | pygmentize | less -r

test:
	pytest -n auto

coverage:
	pytest -n auto --cov=virl2_client --cov-report=term-missing --cov-report=xml --cov-report=json

coverage-html:
	pytest -n auto --cov=virl2_client --cov-report=html --cov-report=term-missing
