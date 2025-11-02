from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration from environment variables
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'image-scraper')

# Construct the database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Enable connection health checks
    pool_size=5,         # Number of connections to keep open
    max_overflow=10,     # Number of connections to create beyond pool_size when needed
    echo=False           # Set to True for SQL query logging
)

# Create a scoped session factory
SessionLocal = scoped_session(
    sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
)

# Base class for models
Base = declarative_base()

def get_db():
    """Dependency for getting DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize the database by creating all tables"""
    import models  # Import models to ensure they're registered with SQLAlchemy
    Base.metadata.create_all(bind=engine)
    print(f"Database '{DB_NAME}' initialized successfully at {DB_HOST}:{DB_PORT}")

# For testing the connection
if __name__ == "__main__":
    try:
        # Test the connection
        with engine.connect() as conn:
            print(f"Successfully connected to database: {DB_NAME}")
        init_db()
    except Exception as e:
        print(f"Error connecting to database: {e}")
