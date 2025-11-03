from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import asyncio
from image_scraper import ImageScraper
from models import ImageData, init_db, SessionLocal
from sqlalchemy.orm import Session
import uvicorn
import logging
from config import global_config as config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
init_db()

app = FastAPI(title="Image Scraper API",
             description="API for scraping and processing images from Bing")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ScrapeRequest(BaseModel):
    keyword: str
    profile: str
    max_save: int = 2

async def get_or_create_keyword(db: Session, keyword: str) -> ImageData:
    """Get existing keyword or create a new one"""
    db_keyword = db.query(ImageData).filter(ImageData.keyword == keyword.lower()).first()
    if not db_keyword:
        db_keyword = ImageData(keyword=keyword.lower())
        db.add(db_keyword)
        db.commit()
        db.refresh(db_keyword)
    return db_keyword

@app.post("/scrape-images/")
async def scrape_images(
    request: ScrapeRequest, 
    db: Session = Depends(get_db)
):
    """
    Scrape and save images based on the provided keyword.
    
    Args:
        keyword: The search term to find images
        profile: Profile name used for saving images
        max_save: Maximum number of images to save (default: 2)
        
    Returns:
        dict: Status and list of saved image URLs
    """
    try:
        logger.info(f"Received request to scrape images for keyword: {request.keyword}")
        
        # Get or create keyword in database
        db_keyword = await get_or_create_keyword(db, request.keyword)
        
        # Initialize the scraper
        scraper = ImageScraper(
            profile=request.profile,
            keyword=request.keyword,
            max_save=request.max_save
        )
        
        # If no scraped URLs in DB, fetch new ones
        if not db_keyword.scraped_urls and not db_keyword.processed_urls:
            logger.info("No existing URLs found, scraping new images...")
            new_urls = scraper.bing_image_scraper()
            db_keyword.scraped_urls = new_urls
            db.commit()
        
        # Get URLs to process (prefer unprocessed, then random from processed)
        urls_to_process, remaining_urls = db_keyword.get_urls_to_process(request.max_save)
        
        if not urls_to_process:
            return {
                "status": "success",
                "message": "No more images to process",
                "saved_urls": [],
                "remaining_urls": []
            }
        
        # Process the selected URLs
        saved_urls = []
        for url in urls_to_process:
            saved_url, _ = await scraper.save_and_process_image(url)
            if saved_url and saved_url != url:  # Only add if save was successful
                saved_urls.append(saved_url)
        
        # Update database
        db_keyword.mark_as_processed(urls_to_process)
        db_keyword.scraped_urls = remaining_urls
        db.commit()
        
        return {
            "status": "success",
            "keyword": request.keyword,
            "saved_count": len(saved_urls),
            "saved_urls": saved_urls,
            "remaining_urls": remaining_urls
        }
        
    except Exception as e:
        logger.error(f"Error in scrape_images: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.app.IMAGE_PORT,
        reload=True
    )
