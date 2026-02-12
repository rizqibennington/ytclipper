from app.core.settings import Settings, get_settings


def settings_dep() -> Settings:
    return get_settings()

