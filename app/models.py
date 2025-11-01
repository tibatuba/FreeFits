from datetime import datetime

class Listing:
    def __init__(self, id, title, description, category, size, condition, location, user_id, created_at=None):
        self.id = id
        self.title = title
        self.description = description
        self.category = category
        self.size = size
        self.condition = condition
        self.location = location
        self.user_id = user_id
        self.created_at = created_at or datetime.now()
        self.images = []
        self.is_available = True

# Sample data for demonstration (will be replaced with MongoDB later)
sample_listings = [
    Listing(
        id=1,
        title="🌿 Organic Cotton T-Shirt",
        description="100% organic cotton t-shirt in forest green. Gently worn, perfect for eco-conscious fashion!",
        category="Tops",
        size="M",
        condition="Excellent",
        location="Toronto, ON",
        user_id="user1"
    ),
    Listing(
        id=2,
        title="🦥 Vintage Denim Jacket",
        description="Classic denim jacket with a sloth patch! Perfect for sustainable fashion lovers.",
        category="Jackets",
        size="M",
        condition="Good",
        location="Toronto, ON",
        user_id="user2"
    ),
    Listing(
        id=3,
        title="🌱 Bamboo Fiber Dress",
        description="Beautiful sustainable bamboo fiber dress. Soft, breathable, and eco-friendly!",
        category="Dresses",
        size="S",
        condition="Like New",
        location="Toronto, ON",
        user_id="user3"
    ),
    Listing(
        id=4,
        title="🌿 Hand-Knit Wool Sweater",
        description="Cozy hand-knit sweater made from recycled wool. One-of-a-kind sustainable piece!",
        category="Sweaters",
        size="L",
        condition="Good",
        location="Toronto, ON",
        user_id="user1"
    ),
    Listing(
        id=5,
        title="🦥 Sloth Print Tote Bag",
        description="Cute canvas tote bag with sloth print. Perfect for grocery shopping and reducing plastic waste!",
        category="Accessories",
        size="One Size",
        condition="Excellent",
        location="Toronto, ON",
        user_id="user2"
    ),
    Listing(
        id=6,
        title="🌱 Hemp Yoga Pants",
        description="Comfortable hemp fiber yoga pants. Sustainable and perfect for eco-friendly workouts!",
        category="Pants",
        size="M",
        condition="Good",
        location="Toronto, ON",
        user_id="user3"
    )
]

def get_latest_listings(limit=20):
    """Get the latest listings, sorted by creation date"""
    return sorted(sample_listings, key=lambda x: x.created_at, reverse=True)[:limit]

def search_listings(query, category=None, location=None, max_distance=None):
    """Search listings based on query and filters"""
    results = sample_listings.copy()
    
    # Filter by search query
    if query:
        query_lower = query.lower()
        results = [listing for listing in results 
                  if query_lower in listing.title.lower() or 
                     query_lower in listing.description.lower()]
    
    # Filter by category
    if category:
        results = [listing for listing in results if listing.category == category]
    
    # Filter by location (simplified for demo - will use proper geolocation later)
    if location:
        results = [listing for listing in results if location.lower() in listing.location.lower()]
    
    return sorted(results, key=lambda x: x.created_at, reverse=True)

def get_listing_by_id(listing_id):
    """Get a listing by its ID"""
    for listing in sample_listings:
        if listing.id == listing_id:
            return listing
    return None

def create_listing(title, description, category, size, condition, location, user_id):
    """Create a new listing and add it to sample_listings"""
    # Get the next available ID
    next_id = max([listing.id for listing in sample_listings], default=0) + 1
    
    new_listing = Listing(
        id=next_id,
        title=title,
        description=description,
        category=category,
        size=size,
        condition=condition,
        location=location,
        user_id=user_id
    )
    
    sample_listings.append(new_listing)
    return new_listing