# Contributing

Thank you for taking an interest in this research artifact. Small, focused pull requests are easiest to review.

## Local setup

1. Create and activate a Python 3.11+ virtual environment.
2. Run `python -m pip install -r requirements.txt`.
3. Run `python -m unittest discover -s tests -v` before making changes.
4. Start the sandbox with `python simulation/app.py` and verify browser-facing changes at `http://127.0.0.1:5000`.

## Pull requests

- Explain the research or software behavior being changed.
- Add or update a smoke test when behavior changes.
- Do not commit generated CSV/JSON runs unless they are intentionally curated into `data/` and documented.
- Keep research claims traceable to the thesis, included data, or a clearly cited source.
- Preserve the separation between the MIT-licensed software and CC BY 4.0 thesis/content.

By contributing code, you agree that your contribution may be distributed under the MIT License. Content contributions should state their provenance and applicable license.
