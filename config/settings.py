# config/settings.py (ПОЛНАЯ ОБНОВЛЕННАЯ ВЕРСИЯ)

from pathlib import Path
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# Получаем список разрешенных хостов из .env файла
ALLOWED_HOSTS_STRING = os.environ.get('ALLOWED_HOSTS')
if ALLOWED_HOSTS_STRING:
    ALLOWED_HOSTS = ALLOWED_HOSTS_STRING.split(',')
else:
    ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    # Jazzmin должен быть выше admin для корректной работы
    'jazzmin',
    
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Сторонние приложения
    'crispy_forms',
    'crispy_tailwind',
    'django_htmx',
    
    # Твои приложения
    'core',
    'accounts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Whitenoise для раздачи статики в продакшене
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Middleware для HTMX
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Указываем Django, где искать общую папку с шаблонами
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
# Папка, где лежат твои статические файлы в разработке
STATICFILES_DIRS = [BASE_DIR / 'static']
# Папка, куда collectstatic будет собирать все файлы для продакшена
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Хранилище для Whitenoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Настройки Аутентификации
AUTHENTICATION_BACKENDS = ['core.backends.EmailBackend']
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/'
X_FRAME_OPTIONS = 'SAMEORIGIN'

# Настройки для Медиа-файлов (загружаемых пользователями)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Настройки Кэша
if DEBUG:
    # Простой кэш в памяти для режима разработки
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }
else:
    # Redis кэш для продакшена
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"}
        }
    }

# Настройки для Crispy Forms и Tailwind
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"