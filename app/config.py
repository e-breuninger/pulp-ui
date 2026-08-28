from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Field names double as env var names. No env_prefix: it would concatenate
    # onto names already starting with "pulp_" (e.g. PULP_PULP_BASE_URL).
    pulp_base_url: str
    pulp_username: str
    pulp_password: str
    pulp_api_version: str = "v3"

    # Deployment-specific branding. Templates found here shadow the bundled ones
    # (drop in a footer.html to replace the footer), and a static/ subdirectory
    # is served at /custom-static for whatever assets those templates reference.
    custom_dir: Path | None = Field(default=None, validation_alias="PULP_UI_CUSTOM_DIR")

    # Logo and favicon. Any URL works; point it at /custom-static/... to use a
    # file from custom_dir. Falls back to the bundled Pulp logo.
    logo_url: str | None = Field(default=None, validation_alias="PULP_UI_LOGO_URL")

    # Stylesheet loaded after the bundled one, so it overrides. Defaults to
    # custom_dir/static/custom.css when that file exists.
    extra_css_url: str | None = Field(
        default=None, validation_alias="PULP_UI_EXTRA_CSS_URL"
    )

    @property
    def base_url(self) -> str:
        return self.pulp_base_url.rstrip("/")


settings = Settings()
