from datetime import datetime
from bson import ObjectId

class Listing:
    def __init__(self, id, title, description, category, size, condition, location, user_id, created_at=None, images=None, is_available=True):
        self.id = id
        self.title = title
        self.description = description
        self.category = category
        self.size = size
        self.condition = condition
        self.location = location
        self.user_id = user_id
        self.created_at = created_at if isinstance(created_at, datetime) else (created_at or datetime.now())
        self.images = images or []
        self.is_available = is_available
    
    @classmethod
    def from_dict(cls, doc):
        """Create a Listing object from a MongoDB document"""
        return cls(
            id=str(doc.get('_id', '')),
            title=doc.get('title', ''),
            description=doc.get('description', ''),
            category=doc.get('category', ''),
            size=doc.get('size', ''),
            condition=doc.get('condition', ''),
            location=doc.get('location', ''),
            user_id=doc.get('user_id', ''),
            created_at=doc.get('created_at', datetime.now()),
            images=doc.get('images', []),
            is_available=doc.get('is_available', True)
        )
    
    def to_dict(self):
        """Convert Listing object to dictionary for MongoDB"""
        return {
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'size': self.size,
            'condition': self.condition,
            'location': self.location,
            'user_id': self.user_id,
            'created_at': self.created_at,
            'images': self.images,
            'is_available': self.is_available
        }

def get_listings_collection(db):
    """Get the listings collection from MongoDB"""
    if db is None:
        return None
    return db["listings"]

def get_latest_listings(db, limit=20):
    """Get the latest listings from MongoDB, sorted by creation date"""
    collection = get_listings_collection(db)
    if collection is None:
        return []
    
    cursor = collection.find({"is_available": True}).sort("created_at", -1).limit(limit)
    return [Listing.from_dict(doc) for doc in cursor]

def search_listings(db, query=None, category=None, location=None, max_distance=None):
    """Search listings in MongoDB based on query and filters"""
    collection = get_listings_collection(db)
    if collection is None:
        return []
    
    # Build MongoDB query
    mongo_query = {"is_available": True}
    
    # Filter by search query
    if query:
        mongo_query["$or"] = [
            {"title": {"$regex": query, "$options": "i"}},
            {"description": {"$regex": query, "$options": "i"}}
        ]
    
    # Filter by category
    if category:
        mongo_query["category"] = category
    
    # Filter by location (simplified for demo - will use proper geolocation later)
    if location:
        mongo_query["location"] = {"$regex": location, "$options": "i"}
    
    cursor = collection.find(mongo_query).sort("created_at", -1)
    return [Listing.from_dict(doc) for doc in cursor]

def get_listing_by_id(db, listing_id):
    """Get a listing by its ID from MongoDB"""
    collection = get_listings_collection(db)
    if collection is None:
        return None
    
    try:
        doc = collection.find_one({"_id": ObjectId(listing_id)})
        if doc:
            return Listing.from_dict(doc)
    except:
        pass
    
    return None

def get_listings_by_user(db, user_id):
    """Get all listings created by a specific user from MongoDB"""
    collection = get_listings_collection(db)
    if collection is None:
        return []
    
    cursor = collection.find({"user_id": user_id}).sort("created_at", -1)
    return [Listing.from_dict(doc) for doc in cursor]

def create_listing(db, title, description, category, size, condition, location, user_id, image_filename=None):
    """Create a new listing and save it to MongoDB"""
    collection = get_listings_collection(db)
    if collection is None:
        # Fallback: return a Listing object without saving (for demo)
        return Listing(
            id="demo",
            title=title,
            description=description,
            category=category,
            size=size,
            condition=condition,
            location=location,
            user_id=user_id,
            images=[image_filename] if image_filename else []
        )
    
    new_listing = Listing(
        id="",  # Will be set after insert
        title=title,
        description=description,
        category=category,
        size=size,
        condition=condition,
        location=location,
        user_id=user_id,
        images=[image_filename] if image_filename else [],
        created_at=datetime.utcnow()
    )
    
    # Insert into MongoDB
    result = collection.insert_one(new_listing.to_dict())
    new_listing.id = str(result.inserted_id)
    
    return new_listing