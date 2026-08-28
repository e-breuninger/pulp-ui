"""app.config builds its Settings at import time, so the required Pulp env vars
have to exist before any test module imports app.main. conftest.py is imported
first, which makes this the only reliable place for them.
"""

import os

os.environ.setdefault("PULP_USERNAME", "x")
os.environ.setdefault("PULP_PASSWORD", "y")
os.environ.setdefault("PULP_BASE_URL", "http://pulp.example")

# Branding a developer set for their own deployment must not leak in and change
# what the suite renders.
os.environ.pop("PULP_UI_CUSTOM_DIR", None)
os.environ.pop("PULP_UI_LOGO_URL", None)
