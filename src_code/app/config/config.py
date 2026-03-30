import re
from pathlib import Path
from dotenv import load_dotenv, set_key
from pydantic_settings import BaseSettings


ENV_FILE = ".env"
# Define paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # Adjust if needed
VERSION_FILE = BASE_DIR / "VERSION.txt"


def get_latest_version():
    if VERSION_FILE.exists():
        with open(VERSION_FILE, "r") as file:
            content = file.read()
        # Find all semantic versions like 1.00.04
        matches = re.findall(r"APAAR API (\d+\.\d+\.\d+)", content)

        if matches:
            # Sort versions using tuple comparison
            versions = sorted(
                matches, key=lambda v: tuple(map(int, v.split("."))), reverse=True
            )
            return versions[0]

    return "Unknown"


# Update .env or print
latest_version = get_latest_version()

# If a valid version is found, update the .env file
if latest_version != "Unknown":
    set_key(str(ENV_FILE), "APP_VERSION", latest_version)

# 🔹 Load .env AGAIN to reflect updates made by `set_key()`
load_dotenv(dotenv_path=str(ENV_FILE), override=True)


# Pydantic settings class
class Settings(BaseSettings):
    # Application Variables
    APP_NAME: str
    APP_VERSION: str
    APP_ENV: str
    APP_KEY: str
    APP_DEBUG: bool
    APP_TIMEZONE: str
    APP_URL: str
    WORKER_APP_URL: str
    ALLOW_ORIGINS: str
    ALLOWED_HOSTS: str

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    API_ENCRYPTED: bool
    API_ENCRYPTION_KEY: str

    # Mongo DB Connection
    MONGO_URI: str
    MONGO_DB_NAME: str

    # Logging
    LOGGING: str
    LOG_LABEL: str
    LOG_FILE_PREFIX: str
    LOG_FILE_PATH: str
    LOG_RETENTION_DAYS: str
    ELK_LOGGING: str

    # AWS S3/minio Configuration
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    S3_BUCKET_NAME: str
    FILE_UPLOAD_PATH: str
    ZIP_PASSWORD: str
    PRESIGNED_URL_EXPIRY: str

    # RabbitMQ Service Configuration
    LOG_RMQ_API_URL: str
    LOG_RMQ_AUTH: str
    LOG_RMQ_EXCHANGE_NAME: str
    LOG_RMQ_EXCHANGE_TYPE: str
    LOG_RMQ_ROUTING_KEY: str
    LOG_RMQ_QUEUE_NAME: str
    DIRECT_EXCHANGE_TYPE: str
    FANOUT_EXCHANGE_TYPE: str

    # Encryption Key and Nonce for AES-GCM - LOCAL
    AES_SECRET_KEY: str
    ENCRYPTION_REQUIRED_CLIENT_IDS: str

    # JWT Auth Configurations
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int

    # API request Rate Limit
    RATE_LIMIT: int
    WINDOW_SIZE: int

    # Redis connection
    REDIS_URL: str
    ALLOWED_HOSTS: str

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    MONGO_CA_CERT: str = ""
    MONGO_CLIENT_CERT: str = ""
    FRONTEND_ORIGINS: str = ""
    # MQTT Config
    MQTT_BROKER: str
    MQTT_PORT: int = 1883
    MQTT_USERNAME: str | None = None
    MQTT_PASSWORD: str | None = None

    # Tata API
    TATA_API_URL: str
    TATA_API_KEY: str
    TATA_INITIATOR_ID: str
    TATA_COOKIE: str

    class Config:
        env_file = str(ENV_FILE)
        extra = "allow"


# Instantiate settings
settings = Settings()
