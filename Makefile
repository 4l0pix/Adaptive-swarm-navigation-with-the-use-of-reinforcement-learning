PYTHON ?= python3

.PHONY: install run test check

install:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) simulation/app.py

test:
	$(PYTHON) -m unittest discover -s tests -v

check:
	$(PYTHON) -m compileall -q simulation tests
	$(PYTHON) -m unittest discover -s tests -v
