
.phony: export diff

# https://github.com/python-poetry/poetry/issues/3472
# https://github.com/python-poetry/poetry/issues/3160
# when resolved, we should be able to run with hashes
tests/requirements.txt: poetry.lock
	poetry export --format=requirements.txt --dev --without-hashes --output=$@

clean:
	rm -rf dist virl2_client.egg-info .built .pytest_cache .coverage coverage.xml
	find . -depth -type f -name '*.pyc' -exec rm {} \; || true
	find . -depth -type d -name '__pycache__' -exec rmdir {} \; || true
	cd docs && make clean

poetry:
	poetry update

export: tests/requirements.txt
	@echo "exported dependencies"

diff:
	diff -ruN -X.gitignore -x.github -x.git -xdist -x.pytest_cache ./ ../simple/virl2_client/ | pygmentize | less -r
