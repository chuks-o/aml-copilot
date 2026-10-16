"""Test-wide environment.

Set before any test module is imported, because ``aml.api.app`` builds its app
(and reads settings) at import time. Tests never read the developer's .env.
"""

import os

os.environ.update(
    {
        "AML_ENV": "test",
        "POSTGRES_PASSWORD": "test-only",
        "RABBITMQ_DEFAULT_PASS": "test-only",
    }
)
