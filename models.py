from sqlalchemy import create_engine, Column, Integer, String, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import global_config as config

# Create SQLAlchemy engine and session
Base = declarative_base()

# Get database URL from config
DATABASE_URL = config.db.DATABASE_URL


class ImageData(Base):
    __tablename__ = 'image_data'
    
    id = Column(Integer, primary_key=True)
    keyword = Column(String(255), unique=True, nullable=False, index=True)
    scraped_urls = Column(JSON, default=list)  # List of scraped but unprocessed URLs
    processed_urls = Column(JSON, default=list)  # List of already processed/saved URLs
    
    def __repr__(self):
        return f"<ImageData(keyword='{self.keyword}', scraped={len(self.scraped_urls)}, processed={len(self.processed_urls)})>"
        
    def get_urls_to_process(self, count: int) -> tuple[list, list]:
        """
        Get URLs to process, with preference for unprocessed URLs first.
        Returns a tuple of (urls_to_process, updated_scraped_urls)
        """
        # First take from scraped_urls
        to_process = self.scraped_urls[:count]
        remaining = self.scraped_urls[count:]
        
        # If we need more, take from processed_urls
        remaining_count = count - len(to_process)
        if remaining_count > 0 and self.processed_urls:
            # Take random samples if we have enough, otherwise take all
            import random
            available = min(remaining_count, len(self.processed_urls))
            random_processed = random.sample(self.processed_urls, available)
            to_process.extend(random_processed)
            
        return to_process, remaining
    
    def mark_as_processed(self, urls: list[str]):
        """Mark URLs as processed (move from scraped to processed)"""
        # Remove from scraped_urls
        self.scraped_urls = [url for url in self.scraped_urls if url not in urls]
        # Add to processed_urls if not already there
        for url in urls:
            if url not in self.processed_urls:
                self.processed_urls.append(url)

# Create database engine and session
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db(db_url=None):
    """Initialize the database and create tables"""
    db_url = db_url or DATABASE_URL
    engine = create_engine(db_url, pool_pre_ping=True)
    
    # Create tables if they don't exist
    Base.metadata.create_all(engine)
    
    # Create a configured "Session" class
    SessionLocal.configure(bind=engine)
    
    return SessionLocal()

def get_or_create_image_data(session, keyword):
    """Get or create an ImageData record"""
    data = session.query(ImageData).filter_by(keyword=keyword).first()
    if not data:
        data = ImageData(keyword=keyword, scraped_urls=[], processed_urls=[])
        session.add(data)
        session.commit()
    return data

# Example usage:
# session = init_db()
# data = get_or_create_image_data(session, "cats")
# data.scraped_urls.append("http://example.com/cat1.jpg")
# data.processed_urls.append("http://example.com/processed/cat1.jpg")
# session.commit()
