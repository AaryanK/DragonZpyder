# DragonZpyder

DragonZpyder is the personal client for Operly's governed execution runtime.

The modern package intentionally does not import or execute the historical desktop-assistant program. P1 establishes a clean package/configuration boundary, placeholder-only example configuration, current-tree secret scanning, and CI. Task submission and authenticated Operly integration are implemented in later slices.

## Local validation

```bash
python -m pip install --no-deps .
python -m compileall -q src tests scripts
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/check_no_secrets.py
```

Configuration is environment-based. Copy `.env.example` to a local ignored `.env` and set the Operly endpoint. Do not commit tokens, OAuth files, pickle credentials, private keys, or provider secrets.
