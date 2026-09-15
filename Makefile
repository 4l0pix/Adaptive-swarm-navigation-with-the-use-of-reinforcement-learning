PYTHON ?= python3

.PHONY: install run test check

install:
	$(PYTHON) -m pip install -e '.[web]'

run:
	$(PYTHON) simulation/app.py

test:
	$(PYTHON) -m unittest discover -s tests -v

check:
	$(PYTHON) -m compileall -q src simulation tests examples
	$(PYTHON) -m unittest discover -s tests -v
