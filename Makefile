clean:
	rm -rf dist virl2_client.egg-info .built
	find . -type f -name '*.pyc' -exec rm {} \; || true
	find . -type d -name '__pycache__' -exec rmdir {} \; || true
	cd docs && make clean
