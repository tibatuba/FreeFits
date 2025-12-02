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
    if cfg.MONGO_URI:
        try:
            client = MongoClient(cfg.MONGO_URI)
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
            app.mongo_client = None
            app.mongo_db = None

    # Import and register blueprints
    from app.routes import main
    app.register_blueprint(main)
    
    return app

# Create the app instance for flask run command
app = create_app()
