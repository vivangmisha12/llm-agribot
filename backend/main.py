"""
AgriBot Backend - Complete OpenRouter Implementation
A multilingual agricultural assistant powered by Claude 4.5 Sonnet via OpenRouter
"""

# ============================================================================
# STEP 1: Load environment variables FIRST (before any other imports)
# ============================================================================
import os
from pathlib import Path
from dotenv import load_dotenv

# Force load .env file
env_file = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_file, override=True)

# Verify environment variables loaded
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SITE_URL = os.getenv("SITE_URL", "http://localhost:5173")
SITE_NAME = os.getenv("SITE_NAME", "AgriBot")

print("=" * 70)
print("LOADING AGRIBOT BACKEND")
print("=" * 70)
print(f"✓ API Key Loaded: {bool(OPENROUTER_API_KEY)}")
if OPENROUTER_API_KEY:
    print(f"✓ API Key: {OPENROUTER_API_KEY[:15]}...{OPENROUTER_API_KEY[-5:]}")
else:
    print("✗ WARNING: OPENROUTER_API_KEY not found in .env file!")
print(f"✓ Site URL: {SITE_URL}")
print(f"✓ Site Name: {SITE_NAME}")
print("=" * 70)

# ============================================================================
# STEP 2: Import other dependencies
# ============================================================================
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langdetect import detect, LangDetectException
from deep_translator import GoogleTranslator
import logging
import requests
import json
from typing import List, Dict, Optional

# ============================================================================
# STEP 3: Configure Logging
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# STEP 4: Initialize FastAPI App
# ============================================================================
app = FastAPI(
    title="AgriBot API",
    description="Multilingual Agricultural Assistant powered by Claude 4.5 Sonnet",
    version="2.0.0"
)

# CORS Configuration
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# STEP 5: Request/Response Models
# ============================================================================
class ChatRequest(BaseModel):
    query: str
    image_url: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    error: bool = False
    error_type: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    api_available: bool
    message: str

# ============================================================================
# STEP 6: Global State
# ============================================================================
conversation_history: List[Dict[str, str]] = []

# ============================================================================
# STEP 7: Utility Functions
# ============================================================================
def detect_language(text: str) -> str:
    """Detect language with fallback to English"""
    try:
        lang = detect(text)
        logger.info(f"Detected language: {lang}")
        return lang
    except LangDetectException as e:
        logger.warning(f"Language detection failed: {e}. Defaulting to English.")
        return "en"
    except Exception as e:
        logger.error(f"Unexpected error in language detection: {e}")
        return "en"

def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """Translate text with error handling"""
    if source_lang == target_lang:
        return text
    
    try:
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        translated = translator.translate(text)
        logger.info(f"Translated from {source_lang} to {target_lang}")
        return translated
    except Exception as e:
        logger.error(f"Translation failed ({source_lang} -> {target_lang}): {e}")
        return text

def get_openrouter_response(user_message: str, image_url: Optional[str] = None) -> tuple[str, bool, Optional[str]]:
    """
    Get response from OpenRouter API (Claude 4.5 Sonnet)
    
    Args:
        user_message: The user's message in English
        image_url: Optional URL to an image for analysis
        
    Returns:
        tuple: (response_text, is_error, error_type)
    """
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY not configured!")
        return (
            "I apologize, but the AI service is currently unavailable. "
            "Please contact the administrator to configure the API key.",
            True,
            "configuration_error"
        )
    
    # Build messages array
    messages = []
    
    # System message
    system_message = {
        "role": "system",
        "content": (
            "You are AgriBot, a friendly and knowledgeable agricultural assistant. "
            "You help farmers and agricultural enthusiasts with questions about crops, "
            "farming techniques, pest control, soil health, irrigation, weather, "
            "agricultural equipment, and general agriculture topics. "
            "\n\n"
            "IMPORTANT FORMATTING RULES:\n"
            "- Always structure your responses using markdown formatting\n"
            "- Use headers (##, ###) to organize main sections\n"
            "- Use bullet points (-) for lists of items\n"
            "- Use numbered lists (1., 2., 3.) for sequential steps or procedures\n"
            "- Use **bold** for emphasis on important terms\n"
            "- Break content into clear sections with headers\n"
            "- Keep information practical and actionable\n"
            "- Make responses easy to scan and read\n"
            "\n"
            "Example structure:\n"
            "## Main Topic\n"
            "Brief introduction\n\n"
            "### Subtopic 1\n"
            "- Point one\n"
            "- Point two\n\n"
            "### Subtopic 2\n"
            "1. First step\n"
            "2. Second step\n"
        )
    }
    
    # Add conversation history (last 5 exchanges for context)
    for exchange in conversation_history[-5:]:
        messages.append({"role": "user", "content": exchange["user"]})
        messages.append({"role": "assistant", "content": exchange["bot"]})
    
    # Build current message
    if image_url:
        # Message with image
        content = [
            {"type": "text", "text": user_message},
            {"type": "image_url", "image_url": {"url": image_url}}
        ]
    else:
        # Text-only message
        content = user_message
    
    messages.append({"role": "user", "content": content})
    
    # Prepare API request
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": SITE_URL,
        "X-Title": SITE_NAME,
    }
    
    payload = {
        "model": "anthropic/claude-sonnet-4.5",
        "messages": [system_message] + messages,
        "max_tokens": 1000,  # Increased for detailed structured responses
        "temperature": 0.3,
    }
    
    logger.info(f"Sending request to OpenRouter API...")
    
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=30
        )
        
        logger.info(f"OpenRouter API response status: {response.status_code}")
        
        # Success
        if response.status_code == 200:
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                reply_text = result["choices"][0]["message"]["content"].strip()
                
                # Log token usage if available
                if "usage" in result:
                    logger.info(f"Token usage - Total: {result['usage'].get('total_tokens', 0)}")
                
                logger.info("✓ Successfully received response from OpenRouter")
                return reply_text, False, None
            else:
                logger.error(f"Unexpected response format: {result}")
                return (
                    "I received an unexpected response format. Please try again.",
                    True,
                    "unexpected_format"
                )
        
        # Handle error status codes
        elif response.status_code == 400:
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", "Bad request")
            logger.error(f"Bad request (400): {error_message}")
            
            if "credit" in error_message.lower() or "balance" in error_message.lower():
                return (
                    "I apologize, but the AI service credits have been exhausted. "
                    "Please contact the administrator to add more credits to OpenRouter.",
                    True,
                    "insufficient_credits"
                )
            else:
                return (
                    "I encountered an issue processing your request. "
                    "Please try rephrasing your question.",
                    True,
                    "bad_request"
                )
        
        elif response.status_code == 401:
            logger.error("Authentication failed (401)")
            return (
                "Authentication failed. The API key may be invalid. "
                "Please contact the administrator.",
                True,
                "authentication_error"
            )
        
        elif response.status_code == 402:
            logger.error("Payment required (402)")
            return (
                "The AI service requires payment. Please add credits to your OpenRouter account.",
                True,
                "payment_required"
            )
        
        elif response.status_code == 429:
            logger.error("Rate limit exceeded (429)")
            return (
                "Too many requests. Please wait a moment and try again.",
                True,
                "rate_limit"
            )
        
        elif response.status_code >= 500:
            logger.error(f"Server error ({response.status_code})")
            return (
                "The AI service is temporarily unavailable. Please try again in a few moments.",
                True,
                "server_error"
            )
        
        else:
            logger.error(f"Unexpected status code: {response.status_code}")
            return (
                f"An unexpected error occurred (Status: {response.status_code}). Please try again.",
                True,
                "unknown_error"
            )
    
    except requests.exceptions.Timeout:
        logger.error("Request timeout")
        return (
            "The request took too long to process. Please try again.",
            True,
            "timeout"
        )
    
    except requests.exceptions.ConnectionError:
        logger.error("Connection error")
        return (
            "Unable to connect to the AI service. Please check your internet connection.",
            True,
            "connection_error"
        )
    
    except Exception as e:
        logger.error(f"Unexpected error: {type(e).__name__}: {e}")
        return (
            "An unexpected error occurred. Please try again later.",
            True,
            "unexpected_error"
        )

# ============================================================================
# STEP 8: API Routes
# ============================================================================
@app.on_event("startup")
async def startup_event():
    """Log startup information"""
    logger.info("=" * 70)
    logger.info("🌾 AGRIBOT BACKEND STARTED")
    logger.info("=" * 70)
    logger.info(f"API Provider: OpenRouter")
    logger.info(f"Model: anthropic/claude-sonnet-4.5")
    logger.info(f"API Key Configured: {bool(OPENROUTER_API_KEY)}")
    if OPENROUTER_API_KEY:
        logger.info(f"API Key: {OPENROUTER_API_KEY[:15]}...{OPENROUTER_API_KEY[-5:]}")
    logger.info(f"Site URL: {SITE_URL}")
    logger.info(f"Site Name: {SITE_NAME}")
    logger.info("=" * 70)

@app.get("/", response_model=HealthResponse)
def home():
    """Health check endpoint"""
    api_available = bool(OPENROUTER_API_KEY)
    
    return HealthResponse(
        status="healthy" if api_available else "degraded",
        api_available=api_available,
        message="AgriBot (Claude Sonnet 4.5 via OpenRouter) is " + 
                ("running successfully!" if api_available else "running with limited functionality.")
    )

@app.get("/health")
def health_check():
    """Detailed health check"""
    return {
        "status": "ok",
        "api_provider": "OpenRouter",
        "model": "anthropic/claude-sonnet-4.5",
        "api_configured": bool(OPENROUTER_API_KEY),
        "conversation_history_size": len(conversation_history),
        "site_url": SITE_URL,
        "site_name": SITE_NAME
    }

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Main chat endpoint with multilingual support and optional image analysis
    """
    user_text = req.query.strip()
    
    # Validation
    if not user_text:
        raise HTTPException(status_code=400, detail="Empty message received")
    
    if len(user_text) > 2000:
        raise HTTPException(
            status_code=400, 
            detail="Message too long. Please keep messages under 2000 characters."
        )
    
    logger.info(f"📨 Received: '{user_text[:50]}{'...' if len(user_text) > 50 else ''}'")
    if req.image_url:
        logger.info(f"🖼️  Image URL: {req.image_url[:50]}...")
    
    # Detect language
    user_lang = detect_language(user_text)
    
    # Translate to English if needed
    translated_text = user_text
    if user_lang != "en":
        translated_text = translate_text(user_text, user_lang, "en")
    
    # Get AI response
    reply_text, is_error, error_type = get_openrouter_response(translated_text, req.image_url)
    
    # Save to history (only if not an error)
    if not is_error:
        conversation_history.append({
            "user": translated_text,
            "bot": reply_text
        })
        
        # Limit history size
        if len(conversation_history) > 100:
            conversation_history.pop(0)
    
    # Translate response back to user's language
    if user_lang != "en" and not is_error:
        reply_text = translate_text(reply_text, "en", user_lang)
    
    logger.info(f"✓ Response sent (error={is_error})")
    
    return ChatResponse(
        reply=reply_text,
        error=is_error,
        error_type=error_type
    )

@app.post("/api/clear-history")
def clear_history():
    """Clear conversation history"""
    global conversation_history
    conversation_history = []
    logger.info("🗑️  Conversation history cleared")
    return {"message": "Conversation history cleared successfully", "count": 0}

@app.get("/api/history")
def get_history():
    """Get conversation history"""
    return {
        "history": conversation_history,
        "count": len(conversation_history)
    }

# ============================================================================
# STEP 9: Error Handlers
# ============================================================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    logger.error(f"HTTP {exc.status_code}: {exc.detail}")
    return {"detail": exc.detail, "status_code": exc.status_code}

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Catch-all exception handler"""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {exc}", exc_info=True)
    return {
        "detail": "An internal server error occurred. Please try again later.",
        "status_code": 500
    }

# ============================================================================
# STEP 10: Run Server
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting AgriBot Backend Server...")
    print("📡 Access at: http://127.0.0.1:8000")
    print("📚 API Docs at: http://127.0.0.1:8000/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)