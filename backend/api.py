"""
FastAPI Backend for Agno Chatbot

This API server wraps the Agno agent and provides endpoints for the React frontend.
"""

import os
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from agno.agent import Agent
from agno.knowledge import Knowledge
from agno.knowledge.reader.website_reader import WebsiteReader
from agno.vectordb.qdrant import Qdrant
from qdrant_client import QdrantClient
from typing import List, Optional
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re
import concurrent.futures

# Load environment variables
load_dotenv()

# Get OpenAI API key from environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set. Please set it in your .env file or environment.")
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Initialize FastAPI app
app = FastAPI(title="Agno Chatbot API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance (initialized on startup)
agent = None
website_reader = None
knowledge_loaded = False
COLLECTION_NAME = "website-content"
QDRANT_URL = "http://localhost:6333"
loaded_urls = []  # Track loaded URLs

# Request/Response models
class Message(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []  # Conversation history

class ChatResponse(BaseModel):
    response: str
    success: bool

class InitializeRequest(BaseModel):
    url: str

class InitializeResponse(BaseModel):
    success: bool
    message: str
    loaded_urls: List[str] = []

class HealthResponse(BaseModel):
    status: str
    message: str
    knowledge_loaded: bool

class LoadedUrlsResponse(BaseModel):
    urls: List[str]
    total: int

class RemoveUrlRequest(BaseModel):
    url: str

class RemoveUrlResponse(BaseModel):
    success: bool
    message: str
    remaining_urls: List[str] = []

class KnowledgeChunk(BaseModel):
    id: str
    name: Optional[str] = None
    content: str
    url: Optional[str] = None
    metadata: Optional[dict] = None

class KnowledgeBaseResponse(BaseModel):
    total_chunks: int
    chunks: List[KnowledgeChunk]

# Browser-based scraper function (using sync Playwright in thread pool for Windows compatibility)
def _scrape_with_browser_sync(url: str, max_links: int = 2, max_depth: int = 3) -> List[dict]:
    """
    Synchronous version of browser scraper - runs in thread pool.
    Scrape website content using Playwright browser to handle JavaScript-rendered sites.
    Returns a list of document dictionaries with name, content, and metadata.
    """
    documents = []
    visited_urls = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        def scrape_page(page_url: str, depth: int = 0):
            if depth > max_depth or page_url in visited_urls:
                return
            
            visited_urls.add(page_url)
            
            try:
                page = browser.new_page()
                
                # Set a reasonable timeout
                page.set_default_timeout(30000)  # 30 seconds
                
                # Navigate to the page and wait for network to be idle
                page.goto(page_url, wait_until="networkidle", timeout=30000)
                
                # Wait a bit more for JavaScript to fully render
                page.wait_for_timeout(2000)
                
                # Get the rendered HTML content
                html_content = page.content()
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style", "noscript"]):
                    script.decompose()
                
                # Get text content
                text_content = soup.get_text(separator=' ', strip=True)
                
                # Clean up whitespace
                text_content = re.sub(r'\s+', ' ', text_content).strip()
                
                if text_content and len(text_content) > 50:  # Only add if substantial content
                    # Get page title
                    title = soup.find('title')
                    page_title = title.get_text(strip=True) if title else page_url
                    
                    documents.append({
                        'name': page_title,
                        'content': text_content,
                        'url': page_url,
                        'meta_data': {
                            'url': page_url,
                            'title': page_title,
                            'depth': depth
                        }
                    })
                
                # Find links to follow (if depth allows)
                if depth < max_depth and len(documents) < max_links * 2:
                    links = soup.find_all('a', href=True)
                    
                    for link in links[:max_links]:
                        href = link.get('href', '')
                        if href.startswith('http'):
                            absolute_url = href
                        elif href.startswith('/'):
                            parsed = urlparse(page_url)
                            absolute_url = f"{parsed.scheme}://{parsed.netloc}{href}"
                        else:
                            continue
                        
                        # Only follow links from the same domain
                        if urlparse(absolute_url).netloc == urlparse(page_url).netloc:
                            scrape_page(absolute_url, depth + 1)
                
                page.close()
                
            except Exception as e:
                print(f"Error scraping {page_url}: {e}")
        
        # Start scraping from the root URL
        scrape_page(url, depth=0)
        browser.close()
    
    return documents

async def scrape_with_browser(url: str, max_links: int = 2, max_depth: int = 3) -> List[dict]:
    """
    Async wrapper for browser scraper - runs sync version in thread pool.
    This avoids Windows asyncio subprocess issues.
    """
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        documents = await loop.run_in_executor(
            executor,
            _scrape_with_browser_sync,
            url,
            max_links,
            max_depth
        )
    return documents

# Initialize agent on startup (without knowledge base - will be loaded when URL is provided)
@app.on_event("startup")
async def startup_event():
    global agent, website_reader
    
    print("Initializing Agno Agent...")
    
    # Note: Browser will be initialized lazily when needed (on first scrape)
    # This avoids Windows asyncio subprocess issues during startup
    
    # Configure Qdrant vector database
    vector_db = Qdrant(
        collection=COLLECTION_NAME,
        url=QDRANT_URL,
    )
    
    # Create website reader (fallback for non-JS sites)
    website_reader = WebsiteReader(
        max_links=2,
        max_depth=3,
    )
    
    # Create knowledge base (empty initially)
    knowledge_base = Knowledge(
        name="Website Knowledge Base",
        vector_db=vector_db,
    )
    
    # Create the agent
    agent = Agent(
        name="Website Knowledge Agent",
        model="openai:gpt-4.1",  # Using gpt-4o instead of gpt-4.1
        knowledge=knowledge_base,
        search_knowledge=True,
        description="An agent that can answer questions using website knowledge base",
        debug_mode=True,  # Disable debug in production
        debug_level=2,
    )
    
    print("✓ Agent initialized and ready! (Waiting for URL to load knowledge base)")

# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    # Browser is managed per-scrape, no cleanup needed
    pass

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        message="Agno Chatbot API is running",
        knowledge_loaded=knowledge_loaded
    )

# Initialize knowledge base from URL
@app.post("/initialize", response_model=InitializeResponse)
async def initialize_knowledge(request: InitializeRequest):
    global agent, website_reader, knowledge_loaded, loaded_urls
    
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    if not request.url or not request.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    
    url = request.url.strip()
    
    # Validate URL format
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    
    try:
        print(f"Loading knowledge base from URL: {url}")
        
        documents = []
        use_browser = False
        
        # Try browser-based scraping first for better JavaScript support
        print("Attempting browser-based scraper for JavaScript rendering...")
        try:
            browser_docs = await scrape_with_browser(url, max_links=2, max_depth=3)
            if browser_docs:
                documents = browser_docs
                use_browser = True
                print(f"✓ Browser scraper extracted {len(documents)} document(s)")
            else:
                print("⚠️  Browser scraper returned no documents, falling back to regular reader")
        except Exception as e:
            print(f"⚠️  Browser scraping failed: {e}")
            print("Falling back to regular website reader...")
            print("Note: To use browser scraping, ensure Playwright browsers are installed: playwright install chromium")
        
        # Fallback to regular website reader if browser scraping failed or not available
        if not documents:
            print("Using regular website reader...")
            try:
                regular_docs = await website_reader.async_read(url)
                if regular_docs:
                    # Convert Document objects to dict format
                    for doc in regular_docs:
                        documents.append({
                            'name': doc.name if hasattr(doc, 'name') else url,
                            'content': doc.content if hasattr(doc, 'content') else str(doc),
                            'url': url,
                            'meta_data': doc.meta_data if hasattr(doc, 'meta_data') and doc.meta_data else {}
                        })
                    print(f"✓ Regular reader extracted {len(documents)} document(s)")
            except Exception as e:
                print(f"⚠️  Regular reader also failed: {e}")
        
        if not documents:
            raise HTTPException(
                status_code=400, 
                detail="No content could be extracted from the URL. The site may require authentication or be inaccessible."
            )
        
        # Check for JavaScript-rendered site issues (only if using regular reader)
        warning_message = ""
        if not use_browser:
            js_indicators = ["enable javascript", "you need to enable javascript", "javascript is disabled"]
            for doc in documents:
                content_lower = doc.get('content', '').lower()
                if any(indicator in content_lower for indicator in js_indicators):
                    warning_message = " Warning: This appears to be a JavaScript-rendered website. Browser-based scraping is recommended for better results."
                    break
        
        # Add documents to knowledge base
        for doc in documents:
            # Build metadata with URL included
            doc_metadata = doc.get('meta_data', {}).copy()
            doc_metadata['url'] = doc.get('url', url)
            doc_metadata['scraped_with'] = 'browser' if use_browser else 'regular'
            
            # Use add_content_async without url parameter to avoid file reading issues
            await agent.knowledge.add_content_async(
                name=doc.get('name') or url,
                text_content=doc.get('content', ''),
                metadata=doc_metadata if doc_metadata else None,
            )
        
        knowledge_loaded = True
        
        # Track loaded URL (avoid duplicates)
        if url not in loaded_urls:
            loaded_urls.append(url)
        
        print(f"✓ Knowledge base loaded successfully from {url}!")
        if warning_message:
            print(f"⚠️{warning_message}")
        
        return InitializeResponse(
            success=True,
            message=f"Knowledge base loaded successfully from {url}. {len(documents)} document(s) indexed using {'browser' if use_browser else 'regular'} scraper.{warning_message}",
            loaded_urls=loaded_urls.copy()
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error loading knowledge base: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error loading knowledge base: {str(e)}"
        )

# Chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    global agent, knowledge_loaded
    
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    # Note: knowledge_loaded is optional - agent can chat without knowledge base
    
    try:
        # Build conversation context from history
        context_parts = []
        
        # Add conversation history to provide context
        if request.history:
            context_parts.append("Previous conversation:")
            for msg in request.history:
                role_label = "User" if msg.role == "user" else "Assistant"
                context_parts.append(f"{role_label}: {msg.content}")
            context_parts.append("")  # Empty line before current message
            context_parts.append("Current question:")
        
        # Add the current message
        full_message = "\n".join(context_parts) + request.message if context_parts else request.message
        
        # Get response from agent with full context
        response = await agent.arun(full_message)
        
        # Extract the response text
        if hasattr(response, 'content'):
            response_text = response.content
        elif isinstance(response, str):
            response_text = response
        else:
            response_text = str(response)
        
        return ChatResponse(
            response=response_text,
            success=True
        )
    except Exception as e:
        print(f"Error processing chat request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )

# Get loaded URLs
@app.get("/loaded-urls", response_model=LoadedUrlsResponse)
async def get_loaded_urls():
    """Get list of all loaded URLs"""
    return LoadedUrlsResponse(
        urls=loaded_urls.copy(),
        total=len(loaded_urls)
    )

# Remove specific URL from knowledge base
@app.post("/remove-url", response_model=RemoveUrlResponse)
async def remove_url(request: RemoveUrlRequest):
    """Remove content from a specific URL from the knowledge base"""
    global loaded_urls, knowledge_loaded
    
    if not request.url or not request.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    
    url = request.url.strip()
    
    if url not in loaded_urls:
        raise HTTPException(status_code=404, detail=f"URL {url} not found in loaded URLs")
    
    try:
        # Connect to Qdrant
        client = QdrantClient(url=QDRANT_URL)
        
        # Delete points that match this URL in metadata
        # We need to scroll through and delete matching points
        deleted_count = 0
        offset = None
        
        while True:
            scroll_result = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            points = scroll_result[0]
            if not points:
                break
            
            # Find points with matching URL
            point_ids_to_delete = []
            for point in points:
                payload = point.payload or {}
                # Check both direct url field and metadata url
                point_url = payload.get("url") or (payload.get("meta_data", {}).get("url") if isinstance(payload.get("meta_data"), dict) else None)
                if point_url == url:
                    point_ids_to_delete.append(point.id)
            
            # Delete matching points
            if point_ids_to_delete:
                client.delete(
                    collection_name=COLLECTION_NAME,
                    points_selector=point_ids_to_delete
                )
                deleted_count += len(point_ids_to_delete)
            
            offset = scroll_result[1]  # next_page_offset
            if offset is None:
                break
        
        # Remove from loaded_urls list
        loaded_urls.remove(url)
        
        # Update knowledge_loaded flag
        if len(loaded_urls) == 0:
            knowledge_loaded = False
        
        return RemoveUrlResponse(
            success=True,
            message=f"Removed {deleted_count} document(s) from {url}",
            remaining_urls=loaded_urls.copy()
        )
    except Exception as e:
        print(f"Error removing URL: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error removing URL: {str(e)}"
        )

# Clear all knowledge base
@app.post("/clear-knowledge-base", response_model=dict)
async def clear_knowledge_base():
    """Clear all knowledge base content"""
    global loaded_urls, knowledge_loaded
    
    try:
        # Connect to Qdrant
        client = QdrantClient(url=QDRANT_URL)
        
        # Get all point IDs and delete them
        all_point_ids = []
        offset = None
        
        while True:
            scroll_result = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                offset=offset,
                with_payload=False,
                with_vectors=False
            )
            
            points = scroll_result[0]
            if not points:
                break
            
            all_point_ids.extend([point.id for point in points])
            offset = scroll_result[1]  # next_page_offset
            if offset is None:
                break
        
        # Delete all points
        if all_point_ids:
            from qdrant_client.models import PointIdsList
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=PointIdsList(points=all_point_ids)
            )
        
        # Clear loaded URLs list
        loaded_urls.clear()
        knowledge_loaded = False
        
        return {
            "success": True,
            "message": f"Knowledge base cleared successfully. Removed {len(all_point_ids)} document(s)."
        }
    except Exception as e:
        print(f"Error clearing knowledge base: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing knowledge base: {str(e)}"
        )

# Get knowledge base chunks
@app.get("/knowledge-base", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(limit: int = 100, offset: int = 0):
    """
    Retrieve knowledge base chunks from Qdrant.
    limit: Maximum number of chunks to return (default: 100)
    offset: Number of chunks to skip (default: 0)
    """
    if not knowledge_loaded:
        raise HTTPException(status_code=400, detail="Knowledge base not loaded. Please initialize with a URL first.")
    
    try:
        # Connect to Qdrant
        client = QdrantClient(url=QDRANT_URL)
        
        # Get collection info to check if it exists
        try:
            collection_info = client.get_collection(COLLECTION_NAME)
            total_points = collection_info.points_count
        except Exception:
            return KnowledgeBaseResponse(total_chunks=0, chunks=[])
        
        # Scroll through points to get chunks
        scroll_result = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        
        chunks = []
        for point in scroll_result[0]:  # scroll_result is a tuple (points, next_page_offset)
            payload = point.payload or {}
            
            chunk = KnowledgeChunk(
                id=str(point.id),
                name=payload.get("name"),
                content=payload.get("text_content", payload.get("content", "")),
                url=payload.get("url"),
                metadata=payload.get("meta_data") if "meta_data" in payload else payload
            )
            chunks.append(chunk)
        
        return KnowledgeBaseResponse(
            total_chunks=total_points,
            chunks=chunks
        )
    except Exception as e:
        print(f"Error retrieving knowledge base: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving knowledge base: {str(e)}"
        )

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Agno Chatbot API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "initialize": "/initialize",
            "chat": "/chat",
            "knowledge-base": "/knowledge-base",
            "loaded-urls": "/loaded-urls",
            "remove-url": "/remove-url",
            "clear-knowledge-base": "/clear-knowledge-base"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

