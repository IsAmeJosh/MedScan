import mimetypes
mimetypes.add_type("text/css", ".css", True)  # Windows sometimes reports .css as text/plain
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "medscan-class-project-key"
DEBUG = True
ALLOWED_HOSTS = ["*"]
ROOT_URLCONF = "medscan_site.urls"
INSTALLED_APPS = ["django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles"]
MIDDLEWARE = [
    "gui.G_Middleware.KeepSessionAsIs",  # background requests must not renew the session
    "gui.G_Middleware.TransactionPerRequest",  # one database connection per web request
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
        "builtins": ["gui.G_Icons", "gui.G_Filters"],  # {% icon "name" %}, the |mobile filter, and so on
    },
}]
DATABASES = {}
NOTIFICATION_POLL_SECONDS = 10  # how often the page checks for new notifications
IDLE_LOGOUT_MINUTES = 15  # a logged-in user with no activity for this long is logged out
SESSION_COOKIE_AGE = IDLE_LOGOUT_MINUTES * 60
SESSION_SAVE_EVERY_REQUEST = True  # every page the user opens starts the timer again
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "gui" / "static"]
