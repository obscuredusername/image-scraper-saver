from PIL import Image, ImageFile, ImageEnhance
import io
import aiohttp
import os
import re
import random
import tempfile
import logging
import traceback
import json
from bs4 import BeautifulSoup

class ImageScraper:
    def __init__(self, profile: str = None, keyword: str = None, max_results: int = 10, max_save: int = 10):
        """
        Initialize the ImageScraper with common parameters.
        
        Args:
            profile: Profile name used for saving images (e.g., website name)
            keyword: Default search keyword
            max_results: Maximum number of results to return from search (default: 10)
            max_save: Maximum number of images to save (default: 10)
        """
        self.profile = profile
        self.keyword = keyword
        self.max_results = max_results
        self.max_save = max_save
        self._saved_count = 0  # Counter for saved images
        
        # Initialize session with headers
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.bing.com/",
            "DNT": "1",
            "Connection": "keep-alive"
        })
    def bing_image_scraper(self, query: str = None, max_results: int = None):
        """
        Scrape full-size Bing image URLs.
        
        Args:
            query: Search keyword (uses self.keyword if None)
            max_results: Number of images to fetch (uses self.max_results if None)
        
        Returns:
            List of image URLs
        """
        query = query or self.keyword
        max_results = max_results or self.max_results
        
        if not query:
            raise ValueError("No search query provided and no default keyword set")
            
        print(f"\n=== Starting bing_image_scraper with query: {query} ===")
        
        url = "https://www.bing.com/images/search"
        params = {
            "q": query,
            "form": "HDRSC2",
            "first": "1",
            "tsc": "ImageBasicHover",
            "qft": "+filterui:imagesize-large"  # request large images
        }
        
        print(f"Making request to: {url}")
        print(f"Params: {params}")
        print(f"Using headers from session")

        try:
            # Make the request using the session
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            print(f"\n=== Response Status: {response.status_code} ===")
            print(f"Final URL: {response.url}")
            
            # Parse the response
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Debug: Print page title
            title = soup.find('title')
            print(f"Page title: {title.text if title else 'No title found'}")
            
            # Find all image containers
            image_containers = soup.find_all("a", class_="iusc")
            print(f"Found {len(image_containers)} image containers")
            
            results = []
            for i, div in enumerate(image_containers):
                try:
                    m = div.get("m")
                    if not m:
                        print(f"No 'm' attribute in container {i}")
                        continue
                        
                    m_json = json.loads(m)
                    img_url = m_json.get("murl")
                    
                    if img_url and img_url.startswith("http"):
                        print(f"Found image URL: {img_url}")
                        results.append(img_url)
                        if len(results) >= max_results:
                            break
                except json.JSONDecodeError as e:
                    print(f"JSON decode error in container {i}: {e}")
                    print(f"Problematic 'm' content: {m[:200]}...")
                except Exception as e:
                    print(f"Error processing container {i}: {str(e)}")
            
            print(f"\n=== Found {len(results)} valid image URLs ===")
            return results
            
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response headers: {e.response.headers}")
                print(f"Response content: {e.response.text[:500]}...")
            return []
        except Exception as e:
            print(f"Unexpected error in bing_image_scraper: {str(e)}")
            traceback.print_exc()
            return []
    async def save_and_process_image(self, image_url: str, remaining_urls: list = None, profile: str = None, keyword: str = None, max_save: int = None) -> tuple:
            """
            Save image to disk in WebP format with 65% quality, add watermark if configured,
            and return a tuple of (saved_url, remaining_urls).
            
            Args:
                image_url: URL of the image to download
                remaining_urls: List of URLs that haven't been processed yet
                profile: Profile name used for the save path and URL generation (uses self.profile if None)
                keyword: Keyword used for generating the filename (uses self.keyword if None)
                max_save: Maximum number of images to save (uses self.max_save if None)
                
            Returns:
                tuple: (saved_url, remaining_urls) where:
                    - saved_url: Public URL of the saved image or original URL if save failed
                    - remaining_urls: List of URLs that weren't processed yet
            """
            logger = logging.getLogger(__name__)
            
            # Use instance variables if parameters are not provided
            profile = profile or self.profile
            keyword = keyword or self.keyword or 'image'  # Default to 'image' if no keyword provided
            max_save = max_save if max_save is not None else self.max_save
            remaining_urls = remaining_urls or []
            
            # Check if we've reached the maximum number of images to save
            if hasattr(self, '_saved_count') and max_save is not None and self._saved_count >= max_save:
                logger.info(f"[save_and_process_image] Reached maximum save limit of {max_save} images")
                return image_url, remaining_urls
                
            if not profile:
                raise ValueError("No profile provided and no default profile set in constructor")
            
            logger.info(f"[save_and_process_image] Starting image processing")
            logger.info(f"[save_and_process_image] Original URL: {image_url}")
            logger.info(f"[save_and_process_image] Keyword: {keyword}")
            logger.info(f"[save_and_process_image] Profile: {profile}")
            
            # Store the original URL to return if saving fails
            original_url = image_url
            logger.info(f"[save_and_process_image] Original URL stored: {original_url}")

            # Get save directory from environment or use a default, and format with profile
            save_dir = os.getenv("IMAGES_SAVE_DIR", "/var/www/{profile}/images").format(profile=profile)
            logger.info(f"[save_and_process_image] Using save directory: {save_dir}")

            # Generate a safe filename
            base_name = re.sub(r'[^a-zA-Z0-9]', '', str(keyword).replace(' ', ''))[:20]
            filename = f"{base_name}.webp"
            counter = 1
            filepath = ""

            # Check if file exists and find next available filename
            while True:
                filepath = os.path.join(save_dir, filename)
                if not os.path.exists(filepath):
                    break
                filename = f"{base_name}{counter}.webp"
                counter += 1

            logger.info(f"[save_and_process_image] Generated filename: {filename}")
            
            try:
                # Create directory if it doesn't exist
                os.makedirs(save_dir, exist_ok=True, mode=0o777)
                filepath = os.path.join(save_dir, filename)
                
                # Check if we have write permissions
                if not os.access(os.path.dirname(filepath), os.W_OK):
                    logger.warning(f"No write permissions in directory: {os.path.dirname(filepath)}")
                    return original_url
                
                # If the URL is a local file path, just return it
                if image_url.startswith('file://'):
                    local_path = image_url.replace('file://', '')
                    logger.info(f"[save_and_process_image] Using existing local image: {local_path}")
                    return local_path  # Return the local path
                
                # Set timeout for the request
                timeout = aiohttp.ClientTimeout(total=60)  # 60 seconds timeout
                
                logger.info(f"[save_and_process_image] Attempting to download image from: {image_url}")
                
                # Download the image
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(image_url) as response:
                        logger.info(f"[save_and_process_image] Image download status: {response.status}")
                        
                        if response.status != 200:
                            error_msg = f"Failed to download image: {image_url} (Status: {response.status}). Using original URL."
                            logger.error(f"[save_and_process_image] {error_msg}")
                            return original_url
                        
                        # Read the image data
                        img_data = await response.read()
                        logger.info(f"[save_and_process_image] Successfully read {len(img_data)} bytes of image data")
                        
                        try:
                            # Convert to WebP with 65% 
                            with Image.open(io.BytesIO(img_data)) as img:
                                logger.info(f"[save_and_process_image] Opened image with mode: {img.mode}, size: {img.size}")
                                
                                # Convert to RGB if necessary (for PNG with transparency)
                                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                                    logger.info("[save_and_process_image] Converting image from transparent to RGB")
                                    background = Image.new('RGB', img.size, (255, 255, 255))
                                    background.paste(img, mask=img.split()[-1])  # Paste using alpha channel as mask
                                    img = background
                                
                                # Save the original image first
                                with tempfile.NamedTemporaryFile(suffix='.webp', delete=False) as temp_file:
                                    temp_path = temp_file.name
                                    img.save(temp_path, format='WEBP', quality=65, method=6)
                                
                                # Get the path to the watermark image - first check environment variable, then default location
                                watermark_path = os.getenv("WATERMARK_IMAGE_PATH")
                                if not watermark_path or not os.path.exists(watermark_path):
                                    # Fall back to the default watermark location
                                    watermark_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'watermark', 'spreadword.webp')
                                
                                logger.info(f"[save_and_process_image] Checking watermark at: {watermark_path}")
                                
                                if os.path.exists(watermark_path):
                                    try:
                                        # Verify the watermark file is readable
                                        with Image.open(watermark_path) as test_img:
                                            logger.info(f"[save_and_process_image] Watermark image is valid. Mode: {test_img.mode}, Size: {test_img.size}")
                                        
                                        # Create a temporary file for the watermarked image
                                        with tempfile.NamedTemporaryFile(suffix='.webp', delete=False) as watermarked_temp_file:
                                            watermarked_path = watermarked_temp_file.name
                                        
                                        logger.info(f"[save_and_process_image] Applying watermark from: {watermark_path}")
                                        logger.info(f"[save_and_process_image] Source image: {temp_path}, Output: {watermarked_path}")
                                        
                                        # Apply watermark
                                        self._add_watermark(temp_path, watermark_path, watermarked_path)
                                        
                                        # Verify the watermarked image was created
                                        if os.path.exists(watermarked_path) and os.path.getsize(watermarked_path) > 0:
                                            temp_path = watermarked_path  # Use the watermarked image
                                            logger.info(f"[save_and_process_image] Successfully applied watermark. New temp path: {temp_path}")
                                        else:
                                            raise Exception("Watermarked file was not created or is empty")
                                            
                                    except Exception as e:
                                        logger.error(f"[save_and_process_image] Error applying watermark: {str(e)}", exc_info=True)
                                        # Clean up any partial files
                                        if 'watermarked_path' in locals() and os.path.exists(watermarked_path):
                                            try:
                                                os.unlink(watermarked_path)
                                            except:
                                                pass
                                        # Continue with unwatermarked image if watermarking fails
                                else:
                                    logger.warning(f"[save_and_process_image] Watermark file not found at: {watermark_path}")
                                    logger.info(f"[save_and_process_image] Current working directory: {os.getcwd()}")
                                    logger.info(f"[save_and_process_image] Directory contents: {os.listdir(os.path.dirname(watermark_path))}")
                                
                                # Move the final (watermarked or original) image to the target location
                                try:
                                    shutil.move(temp_path, filepath)
                                    logger.info(f"[save_and_process_image] Successfully saved image to {filepath}")
                                except Exception as e:
                                    logger.error(f"[save_and_process_image] Error moving file to {filepath}: {str(e)}")
                                    return original_url
                            
                            # Set proper permissions
                            os.chmod(filepath, 0o644)
                            
                            # Clean up any temporary files that might be left
                            if os.path.exists(temp_path):
                                try:
                                    os.unlink(temp_path)
                                except:
                                    pass
                            
                            # Return the full public URL with domain
                            public_url = f"https://{profile}/images/{filename}"  # Adjust this based on your URL structure
                            
                            # Increment the saved image counter
                            if not hasattr(self, '_saved_count'):
                                self._saved_count = 0
                            self._saved_count += 1
                            
                            logger.info(f"[save_and_process_image] Successfully saved image to {filepath}")
                            logger.info(f"[save_and_process_image] Public URL: {public_url}")
                            logger.info(f"[save_and_process_image] Saved {self._saved_count}/{self.max_save} images so far")
                            return public_url, remaining_urls
                        except Exception as e:
                            error_msg = f"Error processing image {image_url}: {str(e)}. Using original URL."
                            logger.error(f"[save_and_process_image] {error_msg}", exc_info=True)
                            return original_url, remaining_urls
        
            except Exception as e:
                error_msg = f"Error saving image {image_url}: {str(e)}. Using original URL."
                logger.error(f"[save_and_process_image] {error_msg}", exc_info=True)
                return original_url, remaining_urls
                
            except PermissionError as e:
                error_msg = f"Permission denied when saving image to directory: {os.path.dirname(filepath) if filepath else 'unknown'}. Error: {str(e)}"
                logger.error(f"[save_and_process_image] {error_msg}")
                logger.info("[save_and_process_image] Using original URL due to permission error")

                if os.geteuid() == 0:  # If running as root
                    try:
                        os.chmod(save_dir, 0o777)
                        logger.info(f"[save_and_process_image] Attempted to fix permissions on {save_dir}")
                    except Exception as perm_error:
                        logger.error(f"[save_and_process_image] Failed to fix permissions: {str(perm_error)}")
                return original_url, remaining_urls
                
            except Exception as e:
                error_msg = f"Unexpected error processing image {image_url}: {str(e)}"
                logger.error(f"[save_and_process_image] {error_msg}", exc_info=True)
                logger.info("[save_and_process_image] Using original URL due to unexpected error")
                return original_url, remaining_urls