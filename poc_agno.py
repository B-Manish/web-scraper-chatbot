"""
Agno Agent with Website Knowledge Base (Using Qdrant - Simple Setup)

This script creates an Agno agent that can answer questions using content
from websites. It uses OpenAI for the LLM and Qdrant for vector storage.

Setup:
1. Set your OPENAI_API_KEY environment variable or update the code below
2. Start Qdrant: docker run -p 6333:6333 qdrant/qdrant
3. Install dependencies: uv sync (or pip install -r requirements.txt)
4. Run this script to load the knowledge base and test queries

Qdrant is much simpler than PostgreSQL - just one Docker command!
"""

import os
import asyncio
from dotenv import load_dotenv
from agno.agent import Agent
from agno.knowledge import Knowledge
from agno.knowledge.reader.website_reader import WebsiteReader
from agno.vectordb.qdrant import Qdrant

# Load environment variables from .env file
load_dotenv()

# Get OpenAI API key from environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set. Please set it in your .env file or environment.")
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Configure Qdrant vector database (much simpler than PostgreSQL!)
# Just run: docker run -p 6333:6333 qdrant/qdrant
# No database setup, users, or extensions needed!
COLLECTION_NAME = "website-content"
vector_db = Qdrant(
    collection=COLLECTION_NAME,
    url="http://localhost:6333",  # Default Qdrant port
)

# URLs to crawl and index
URLS = [
    "https://github.com/SSahas",
    # Add more URLs here as needed
]

# Create website reader
# Configure crawling parameters
website_reader = WebsiteReader(
    max_links=2,  # Number of links to follow from the seed URLs
    max_depth=3,  # Maximum depth to crawl
)

# Create knowledge base
knowledge_base = Knowledge(
    name="Website Knowledge Base",
    vector_db=vector_db,
)

# Create the agent with OpenAI and knowledge base
agent = Agent(
    name="Website Knowledge Agent",
    model="openai:gpt-4.1",  # Format: "openai:gpt-4o", "openai:gpt-4", "openai:gpt-3.5-turbo", etc.
    knowledge=knowledge_base,
    search_knowledge=True,  # Enable knowledge search
    description="An agent that can answer questions using website knowledge base",
    debug_mode=True,
    debug_level=2,
)

# Main execution
async def main():
    print("=" * 60)
    print("Agno Agent with Website Knowledge Base (Qdrant)")
    print("=" * 60)
    
    # Load the knowledge base by reading URLs
    # Set recreate=True to reload from scratch (useful for updates)
    # Set recreate=False to use existing data (faster)
    print("\nLoading knowledge base from URLs...")
    try:
        # Read content from each URL using the website reader
        for url in URLS:
            print(f"  Reading: {url}")
            documents = await website_reader.async_read(url)
            # Convert Document objects to Content formatTell me about your knowledge base and add to knowledge base
            for doc in documents:
                await agent.knowledge.add_content_async(
                    name=doc.name,
                    text_content=doc.content,
                    metadata=doc.meta_data if hasattr(doc, 'meta_data') else None,
                    url=url,
                )
        
        print("✓ Knowledge base loaded successfully!")
    except Exception as e:
        print(f"✗ Error loading knowledge base: {e}")
        print("\nMake sure:")
        print("1. Qdrant is running: docker run -p 6333:6333 qdrant/qdrant")
        print("2. Qdrant is accessible at http://localhost:6333")
        print("3. Required dependencies are installed: uv sync")
        print("4. You have internet access to fetch the URLs")
        raise
    
    print("\n" + "=" * 60)
    print("You can now ask questions!")
    print("=" * 60)
    print("\nExample queries:")
    print('  await agent.aprint_response("What is Agno?")')
    print('  await agent.aprint_response("How does Agno work?")')
    print('  await agent.aprint_response("What are the main features?")')
    print("\n" + "-" * 60)
    
    # Example query
    print("\nRunning example query...\n")
    await agent.aprint_response("Tell me about Sahas's github profile?", markdown=True)

if __name__ == "__main__":
    asyncio.run(main())

