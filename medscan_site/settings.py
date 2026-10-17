"""Django settings for MedScan: installed apps, middleware, sessions, templates and the idle logout."""
import mimetypes
# Windows sometimes reports .css files as text/plain, which browsers refuse as a stylesheet.
mimetypes.add_type("text/css", ".css", True)
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "medscan-class-project-key"
DEBUG = True
ALLOWED_HOSTS = ["*"]
ROOT_URLCONF = "medscan_site.urls"
INSTALLED_APPS = ["django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles"]
MIDDLEWARE = [
    "gui.G_Middleware.KeepSessionAsIs",  # Background requests (the notification check) must not renew the session.
    "gui.G_Middleware.TransactionPerRequest",  # One database transaction, and so one connection, per web request.
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "gui" / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.request",
            "django.contrib.messages.context_processors.messages",
            "gui.G_Context.shell",
        ],
        # Template helpers every page can use: {% icon "name" %}, the |mobile filter, and so on.
        "builtins": ["gui.G_Icons", "gui.G_Filters"],
    },
}]
DATABASES = {}
NOTIFICATION_POLL_SECONDS = 10  # How often (in seconds) the page checks for new notifications.
IDLE_LOGOUT_MINUTES = 15  # A logged-in person with no activity for this many minutes is logged out.
SESSION_COOKIE_AGE = IDLE_LOGOUT_MINUTES * 60
SESSION_SAVE_EVERY_REQUEST = True  # Every page the person opens starts the idle timer again.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "gui" / "static"]
