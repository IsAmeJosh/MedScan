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
        "builtins": ["gui.G_Icons"],  # lets every template use {% icon "name" %}
    },
}]
DATABASES = {}
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "gui" / "static"]
