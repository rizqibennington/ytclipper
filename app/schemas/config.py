from pydantic import BaseModel, ConfigDict


class ConfigResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    output_dir: str | None = None
    output_mode: str | None = None
    crop_mode: str | None = None
    use_subtitle: bool | None = None
    whisper_model: str | None = None
    subtitle_language: str | None = None
    subtitle_position: str | None = None
    preview_seconds: int | None = None
    deps_verbose: bool | None = None
    has_gemini_key: bool | None = None
    use_gemini_suggestions: bool | None = None


class ConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    output_mode: str | None = None
    output_dir: str | None = None
    crop_mode: str | None = None
    crop_preview: bool | None = None
    use_subtitle: bool | None = None
    whisper_model: str | None = None
    subtitle_language: str | None = None
    subtitle_position: str | None = None
    preview_seconds: int | None = None
    deps_verbose: bool | None = None
    use_gemini_suggestions: bool | None = None
    gemini_api_key: str | None = None
