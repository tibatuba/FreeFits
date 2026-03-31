from pathlib import Path
import hmac
import secrets

from flask import Flask, session, request, abort
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConfigurationError
from werkzeug.security import generate_password_hash  # ensure available
from config import get_config


def create_app():
    # Load .env from project root (so it works when gunicorn starts from any CWD)
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")

    app = Flask(__name__)

    # Load config
    cfg = get_config()
    app.secret_key = cfg.SECRET_KEY

    # Initialize MongoDB client if URI provided
    app.mongo_client = None
    app.mongo_db = None
    
    # Try to get MongoDB URI from config, or use default local connection
    mongo_uri = cfg.MONGO_URI
    if not mongo_uri or mongo_uri.strip() == "":
        # Try default local MongoDB connection
        mongo_uri = "mongodb://localhost:27017/"
        print(f"MongoDB URI not configured. Trying default local connection: {mongo_uri}")
    else:
        print(f"Using configured MongoDB URI: {mongo_uri[:20]}...")
    
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        # Use the freefits database
        db = client["freefits"]
        
        # Test connection
        client.admin.command('ping')
        
        app.mongo_client = client
        app.mongo_db = db

        # Ensure indexes for users
        users = db["users"]
        users.create_index("username", unique=True)
        users.create_index("email", unique=True)
        
        # Ensure indexes for listings
        listings = db["listings"]
        listings.create_index("user_id")
        listings.create_index("category")
        listings.create_index("created_at")
        listings.create_index([("title", "text"), ("description", "text")])  # Text search index
        # Geospatial index for location-based searches
        try:
            listings.create_index([("location_coords", "2dsphere")])
        except Exception as e:
            # Index might already exist, or coordinates might not be present yet
            print(f"Note: Geospatial index creation: {e}")

        # Ensure indexes for flags (moderation)
        flags = db["flags"]
        flags.create_index("listing_id")
        flags.create_index("status")
        flags.create_index("created_at")
        
        print("MongoDB connected successfully!")
    except Exception as e:
        print(f"MongoDB connection error: {e}")
        print("Please ensure MongoDB is running and accessible.")
        print("To configure MongoDB, set MONGO_URI in your .env file.")
        print("Example: MONGO_URI=mongodb://localhost:27017/")
        app.mongo_client = None
        app.mongo_db = None

    # Import and register blueprints
    from app.routes import main
    app.register_blueprint(main)

    # Inject Google Places API key for frontend location autocomplete (Canada-only)
    @app.context_processor
    def inject_google_places_key():
        return {"google_places_api_key": (cfg.GOOGLE_PLACES_API_KEY or "")}

    # Inject is_admin and email_verified for templates
    @app.context_processor
    def inject_is_admin():
        is_admin = False
        email_verified = True  # default for existing users without the field
        try:
            username = session.get("username")
            if username and app.mongo_db is not None:
                user = app.mongo_db["users"].find_one({"username": username})
                if user:
                    is_admin = user.get("role") == "admin"
                    email_verified = user.get("email_verified", True)
        except Exception:
            pass
        return {"is_admin": is_admin, "email_verified": email_verified}

    @app.context_processor
    def inject_csrf_token():
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return {"csrf_token": lambda: session.get("_csrf_token", "")}

    @app.before_request
    def validate_csrf_token():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        if request.endpoint == "static":
            return None

        session_token = session.get("_csrf_token", "")
        request_token = request.form.get("csrf_token", "") or request.headers.get("X-CSRF-Token", "")
        if not session_token or not request_token or not hmac.compare_digest(session_token, request_token):
            abort(400, description="CSRF token missing or invalid.")
        return None

    # Prevent browser from caching HTML so deploys show up immediately
    @app.after_request
    def add_no_cache_headers(response):
        if response.content_type and "text/html" in response.content_type:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    return app

# Create the app instance for flask run command
app = create_app()
