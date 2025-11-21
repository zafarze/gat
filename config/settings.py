# config/settings.py
# ПОЛНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ (BEST PRACTICES 2025)

from pathlib import Path
import os
import sys
from dotenv import load_dotenv

# =============================================================================
# 1. БАЗОВЫЕ НАСТРОЙКИ И ОКРУЖЕНИЕ
# =============================================================================

# Загружаем переменные из .env
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')

# Защита от запуска без ключа (Critical Check)
if not SECRET_KEY:
    error_msg = "CRITICAL ERROR: SECRET_KEY not found in .env file!"
    print(error_msg, file=sys.stderr)
    # В продакшене лучше упасть, чем работать с дырой в безопасности
    # raise ValueError(error_msg) 

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

# =============================================================================
# 2. ПРИЛОЖЕНИЯ (INSTALLED APPS)
# =============================================================================

INSTALLED_APPS = [
    # --- UI & Admin Themes (Должны быть первыми) ---
    'jazzmin',              # Красивая админка
    
    # --- Django Core ---
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # --- Third-party Apps (Сторонние библиотеки) ---
    'widget_tweaks',        # Улучшение рендеринга полей форм
    'crispy_forms',         # Формы DRY
    'crispy_tailwind',      # Tailwind для форм
    'django_htmx',          # Динамика без JS
    'import_export',        # Импорт/Экспорт Excel/CSV
    
    # --- Local Apps (Твои приложения) ---
    'core.apps.CoreConfig', # Рекомендуется указывать через Config класс
    'accounts.apps.AccountsConfig',
]

# =============================================================================
# 3. MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Whitenoise: Раздача статики (важно для Docker/Prod)
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # HTMX Middleware (важно для корректной работы htmx атрибутов)
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'config.urls'

# =============================================================================
# 4. ШАБЛОНЫ (TEMPLATES)
# =============================================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Твои кастомные процессоры
                'core.context_processors.archive_years_processor',
                'core.context_processors.global_settings_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# =============================================================================
# 5. БАЗА ДАННЫХ (DATABASE)
# =============================================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'postgres'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# =============================================================================
# 6. АУТЕНТИФИКАЦИЯ И ПАРОЛИ
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTHENTICATION_BACKENDS = [
    'core.backends.EmailOrUsernameBackend', # Твой кастомный вход
    'django.contrib.auth.backends.ModelBackend',
]

LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/'

# =============================================================================
# 7. ЛОКАЛИЗАЦИЯ (I18N & L10N)
# =============================================================================

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Asia/Dushanbe'
USE_I18N = True
USE_TZ = True # Важно: Django 5 использует zoneinfo по умолчанию

# =============================================================================
# 8. СТАТИКА И МЕДИА
# =============================================================================

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# =============================================================================
# 9. НАСТРОЙКИ БИБЛИОТЕК И ИНСТРУМЕНТОВ
# =============================================================================

# --- Django Auto Field ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Crispy Forms & Tailwind ---
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# --- Import-Export & Uploads ---
# Лимиты на загрузку (10MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

IMPORT_EXPORT_USE_TRANSACTIONS = True
IMPORT_EXPORT_SKIP_ADMIN_LOG = False
IMPORT_EXPORT_IMPORT_PERMISSION = True
IMPORT_EXPORT_EXPORT_PERMISSION = True

# --- Cache & Redis ---
if DEBUG:
    # Локальный кэш для разработки (быстрый, не требует Redis)
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }
else:
    # Redis для продакшена
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"}
        }
    }

# --- Jazzmin (Админ-панель) ---
JAZZMIN_SETTINGS = {
    "site_title": "GAT Testing System",
    "site_header": "GAT Testing System",
    "site_brand": "GAT Admin",
    "site_logo": "images/logo.png", # Убедись, что файл есть в static/images/
    "login_logo": "images/logo.png",
    "welcome_sign": "Добро пожаловать в GAT Testing System",
    "copyright": "GAT Testing System Ltd",
    "show_ui_builder": True,
    "changeform_format": "horizontal_tabs",
    "navigation_expanded": True,
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        # Добавь свои модели сюда по мере необходимости
        "core.AcademicYear": "fas fa-calendar-alt",
        "core.School": "fas fa-school",
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar": "navbar-indigo navbar-dark",
    "brand_colour": "navbar-indigo",
    "sidebar": "sidebar-dark-indigo",
    "theme": "default",
}

# =============================================================================
# 10. ЛОГИРОВАНИЕ (LOGGING) - MODERN STYLE
# =============================================================================

# Создаем папку логов через pathlib (надежно)
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'cleanup_file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'cleanup.log',
            'formatter': 'verbose',
        },
        'questions_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'questions.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'cleanup_logger': {
            'handlers': ['cleanup_file'],
            'level': 'WARNING',
            'propagate': True,
        },
        'questions_logger': {
            'handlers': ['questions_file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# =============================================================================
# 11. БЕЗОПАСНОСТЬ (PRODUCTION SECURITY)
# =============================================================================

if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 год
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    X_FRAME_OPTIONS = 'SAMEORIGIN' # Разрешить iframes с того же домена