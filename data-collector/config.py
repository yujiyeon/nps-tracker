from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg2://nps_user:localdevpassword@localhost:5432/nps_tracker"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    # DART Open API 키 (https://opendart.fss.or.kr 발급)
    dart_api_key: str = Field(default="")

    # KRX 데이터 포털 로그인 (https://data.krx.co.kr 무료 가입, pykrx 1.1+ 필수)
    krx_id: str = Field(default="")
    krx_pw: str = Field(default="")

    log_level: str = Field(default="INFO")


settings = Settings()
