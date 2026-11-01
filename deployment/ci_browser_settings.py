from .ci_sqlite_settings import *  # noqa: F403

DATABASES['default']['TEST']={'NAME':BASE_DIR/'outputs/ci_browser.sqlite3'}
