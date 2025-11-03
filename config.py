import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database Configuration
class DatabaseConfig:
    USER: str = os.getenv("DB_USER", "auto_publisher_user")
    PASSWORD: str = os.getenv("DB_PASSWORD", "3116311353")
    HOST: str = os.getenv("DB_HOST", "147.79.117.38")
    PORT: str = os.getenv("DB_PORT", "38028")
    NAME: str = os.getenv("DB_NAME", "auto_publisher_db")
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.NAME}"

# Application Settings
class AppConfig:
    IMAGES_SAVE_DIR: Path = Path(os.getenv("IMAGES_SAVE_DIR", "/var/www/images"))
    WATERMARK_IMAGE_PATH: Path = Path(os.getenv("WATERMARK_IMAGE_PATH", "./watermark/watermark.png"))
    IMAGE_PORT: int = int(os.getenv("IMAGE_PORT", "8021"))

# Logging Configuration
class LoggingConfig:
    LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    FILE: str = os.getenv("LOG_FILE", "app.log")

# Main Config Class
class Config:
    db = DatabaseConfig()
    app = AppConfig()
    log = LoggingConfig()
    
    @classmethod
    def get(cls, key: str, default: Optional[str] = None) -> str:
        """Get any configuration value by dot notation (e.g., 'db.USER' or 'app.IMAGE_PORT')"""
        try:
            parts = key.split('.')
            value = cls
            for part in parts:
                value = getattr(value, part)
            return value if value is not None else default
        except (AttributeError, TypeError):
            return default

# Create a single config instance to be imported
global_config = Config()

# Example usage:
# from config import global_config as config
# db_url = config.db.DATABASE_URL
# image_port = config.app.IMAGE_PORT
# log_level = config.log.LEVEL
