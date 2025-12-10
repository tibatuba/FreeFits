from flask import Flask
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConfigurationError
from werkzeug.security import generate_password_hash  # ensure available
from config import get_config

def create_app():
    load_dotenv()
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
    
    return app

# Create the app instance for flask run command
app = create_app()
