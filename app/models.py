from datetime import datetime
from bson import ObjectId

class Listing:
    def __init__(self, id, title, description, category, size, condition, location, user_id, created_at=None, images=None, is_available=True, latitude=None, longitude=None):
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
        self.latitude = latitude
        self.longitude = longitude
    
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
            is_available=doc.get('is_available', True),
            latitude=doc.get('latitude'),
            longitude=doc.get('longitude')
        )
    
    def to_dict(self):
        """Convert Listing object to dictionary for MongoDB"""
        result = {
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
        # Add coordinates if available
        if self.latitude is not None and self.longitude is not None:
            result['latitude'] = self.latitude
            result['longitude'] = self.longitude
            result['location_coords'] = {
                'type': 'Point',
                'coordinates': [self.longitude, self.latitude]  # MongoDB GeoJSON format: [longitude, latitude]
            }
        return result

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

def search_listings(db, query=None, category=None, location=None, max_distance=None, user_lat=None, user_lon=None):
    """Search listings in MongoDB based on query and filters with geospatial support"""
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
    
    # Geospatial search: if user coordinates and max_distance provided, use $geoNear
    if user_lat is not None and user_lon is not None and max_distance is not None:
        try:
            # Use aggregation pipeline with $geoNear for distance-based search
            pipeline = [
                {
                    "$geoNear": {
                        "near": {
                            "type": "Point",
                            "coordinates": [user_lon, user_lat]  # GeoJSON format: [longitude, latitude]
                        },
                        "distanceField": "distance",
                        "maxDistance": max_distance * 1000,  # Convert km to meters
                        "spherical": True,
                        "query": mongo_query
                    }
                },
                {
                    "$sort": {"distance": 1}  # Sort by distance (nearest first)
                }
            ]
            cursor = collection.aggregate(pipeline)
            listings = []
            for doc in cursor:
                listing = Listing.from_dict(doc)
                # Store distance for display
                if 'distance' in doc:
                    listing.distance_km = doc['distance'] / 1000  # Convert meters to km
                listings.append(listing)
            
            # If geospatial search returned results, use them
            if len(listings) > 0:
                print(f"DEBUG: Geospatial search returned {len(listings)} listings", flush=True)
                return listings
            else:
                # Geospatial search returned 0 results (likely because listings don't have coordinates)
                # Fall back to manual distance calculation
                print(f"DEBUG: Geospatial search returned 0 results, falling back to manual calculation", flush=True)
                # Continue to fallback code below
        except Exception as e:
            # Fallback to regular search if geospatial index doesn't exist or query fails
            print(f"Geospatial search failed, falling back to distance calculation: {e}")
            # Continue to fallback search below
    
    # Fallback: Get all listings and calculate distances manually
    # This works even if geospatial index doesn't exist
    cursor = collection.find(mongo_query)
    all_docs = list(cursor)
    print(f"DEBUG: Found {len(all_docs)} listings matching query filters", flush=True)
    listings = []
    for doc in all_docs:
        listing = Listing.from_dict(doc)
        print(f"DEBUG: Processing listing: {listing.title}, location={listing.location}, lat={listing.latitude}, lon={listing.longitude}", flush=True)
        
        # Calculate distance if user coordinates are available (for display, even if not filtering)
        if user_lat is not None and user_lon is not None:
            listing_has_coords = listing.latitude is not None and listing.longitude is not None
            
            if listing_has_coords:
                # Listing has coordinates, calculate distance directly
                from app.geocoding import calculate_distance
                listing.distance_km = calculate_distance(
                    user_lat, user_lon,
                    listing.latitude, listing.longitude
                )
                print(f"DEBUG: Listing {listing.title} has stored coordinates, distance={listing.distance_km}km", flush=True)
            elif listing.location:
                # Listing doesn't have coordinates, try to geocode it on the fly
                print(f"DEBUG: Listing {listing.title} needs geocoding, location='{listing.location}'", flush=True)
                from app.geocoding import geocode_location
                geocode_result = geocode_location(listing.location)
                if geocode_result:
                    listing_lat, listing_lon, _ = geocode_result
                    listing.latitude = listing_lat
                    listing.longitude = listing_lon
                    from app.geocoding import calculate_distance
                    listing.distance_km = calculate_distance(
                        user_lat, user_lon,
                        listing_lat, listing_lon
                    )
                    print(f"DEBUG: Successfully geocoded {listing.title} to ({listing_lat}, {listing_lon}), distance={listing.distance_km}km", flush=True)
                else:
                    # Can't geocode listing location - try to extract city/province and retry
                    print(f"DEBUG: Failed to geocode {listing.title} location '{listing.location}', trying city/province only", flush=True)
                    
                    # Try to extract city and province from location string
                    location_parts = [p.strip() for p in listing.location.split(',')]
                    city_province = None
                    
                    # Find city and province (skip postal code prefixes like "L6M")
                    import re
                    postal_pattern = re.compile(r'^[A-Za-z]\d[A-Za-z]$')
                    for part in location_parts:
                        if not postal_pattern.match(part) and len(part) > 2:
                            if city_province is None:
                                city_province = part
                            else:
                                city_province = f"{city_province}, {part}"
                    
                    # Retry geocoding with just city/province
                    if city_province and city_province != listing.location:
                        print(f"DEBUG: Retrying geocode for {listing.title} with '{city_province}'", flush=True)
                        geocode_result = geocode_location(city_province)
                        if geocode_result:
                            listing_lat, listing_lon, _ = geocode_result
                            listing.latitude = listing_lat
                            listing.longitude = listing_lon
                            from app.geocoding import calculate_distance
                            listing.distance_km = calculate_distance(
                                user_lat, user_lon,
                                listing_lat, listing_lon
                            )
                            print(f"DEBUG: Successfully geocoded {listing.title} using city/province to ({listing_lat}, {listing_lon}), distance={listing.distance_km}km", flush=True)
                        else:
                            print(f"DEBUG: Still failed to geocode {listing.title} even with city/province", flush=True)
                            if max_distance is not None:
                                print(f"DEBUG: Skipping {listing.title} - can't geocode and distance filter is active", flush=True)
                                continue
                            listing.distance_km = None
                    else:
                        print(f"DEBUG: Could not extract city/province from '{listing.location}'", flush=True)
                        if max_distance is not None:
                            print(f"DEBUG: Skipping {listing.title} - can't geocode and distance filter is active", flush=True)
                            continue
                        listing.distance_km = None
            else:
                # No location text
                print(f"DEBUG: Listing {listing.title} has no location text", flush=True)
                if max_distance is not None:
                    # If distance filter is active, skip listings without location
                    print(f"DEBUG: Skipping {listing.title} - no location and distance filter is active", flush=True)
                    continue
                # If no distance filter, include it anyway
                listing.distance_km = None
            
            # Filter by max distance ONLY if max_distance is specified
            if max_distance is not None:
                if listing.distance_km is not None:
                    print(f"DEBUG: Listing {listing.title} distance={listing.distance_km}km, max={max_distance}km", flush=True)
                    if listing.distance_km > max_distance:
                        print(f"DEBUG: Skipping {listing.title} - too far ({listing.distance_km}km > {max_distance}km)", flush=True)
                        continue
                    else:
                        print(f"DEBUG: Including {listing.title} - within range ({listing.distance_km}km <= {max_distance}km)", flush=True)
                else:
                    # Can't calculate distance but max_distance is set - skip it
                    print(f"DEBUG: Listing {listing.title} - couldn't calculate distance, skipping due to distance filter", flush=True)
                    continue
            # If max_distance is None, include all listings (distance calculated for display)
        elif location:
            # If location text search is used (without coordinates), check if location matches
            if location.lower() not in listing.location.lower():
                continue
        # If no user coordinates and no location filter, include the listing
        # (This handles the case where max_distance is None - show all listings)
        
        listings.append(listing)
    
    # Sort by distance if available, otherwise by created_at
    if user_lat is not None and user_lon is not None:
        listings.sort(key=lambda x: (x.distance_km if hasattr(x, 'distance_km') and x.distance_km is not None else float('inf'), 
                                    -(x.created_at.timestamp() if x.created_at else 0)))
    else:
        listings.sort(key=lambda x: -(x.created_at.timestamp() if x.created_at else 0))
    
    return listings

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
        print(f"DEBUG: Database connection is None for get_listings_by_user")
        return []
    
    print(f"DEBUG: Querying listings for user_id={user_id}")
    cursor = collection.find({"user_id": user_id}).sort("created_at", -1)
    listings = [Listing.from_dict(doc) for doc in cursor]
    print(f"DEBUG: Found {len(listings)} listings for user_id={user_id}")
    
    # Debug: Print all user_ids in database to check for mismatch
    if len(listings) == 0:
        all_listings = list(collection.find({}).limit(5))
        print(f"DEBUG: Sample listings in database:")
        for doc in all_listings:
            print(f"  - user_id='{doc.get('user_id')}', title='{doc.get('title')}'")
    
    return listings

def create_listing(db, title, description, category, size, condition, location, user_id, image_filename=None, latitude=None, longitude=None):
    """Create a new listing and save it to MongoDB"""
    collection = get_listings_collection(db)
    if collection is None:
        # Fallback: return a Listing object without saving (for demo)
        print("WARNING: Database connection is None. Listing not saved to database.")
        return Listing(
            id="demo",
            title=title,
            description=description,
            category=category,
            size=size,
            condition=condition,
            location=location,
            user_id=user_id,
            images=[image_filename] if image_filename else [],
            latitude=latitude,
            longitude=longitude
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
        created_at=datetime.utcnow(),
        latitude=latitude,
        longitude=longitude
    )
    
    # Insert into MongoDB
    try:
        listing_dict = new_listing.to_dict()
        print(f"DEBUG: Inserting listing for user_id={user_id}, title={title}")
        result = collection.insert_one(listing_dict)
        
        if result.inserted_id:
            new_listing.id = str(result.inserted_id)
            print(f"DEBUG: Successfully inserted listing with id={new_listing.id}")
            
            # Verify the insert by querying it back
            verify_doc = collection.find_one({"_id": result.inserted_id})
            if verify_doc:
                print(f"DEBUG: Verified listing exists in database")
            else:
                print(f"ERROR: Listing was inserted but cannot be found in database!")
        else:
            print(f"ERROR: Insert operation did not return an inserted_id")
            raise Exception("Failed to insert listing: no inserted_id returned")
            
    except Exception as e:
        print(f"ERROR: Failed to insert listing into database: {e}")
        raise Exception(f"Failed to save listing to database: {e}")
    
    return new_listing

def update_listing(db, listing_id, title, description, category, size, condition, location, image_filename=None, latitude=None, longitude=None):
    """Update an existing listing in MongoDB"""
    collection = get_listings_collection(db)
    if collection is None:
        print("WARNING: Database connection is None. Cannot update listing.")
        return None
    
    try:
        # Get the existing listing to preserve user_id and created_at
        existing_doc = collection.find_one({"_id": ObjectId(listing_id)})
        if not existing_doc:
            print(f"ERROR: Listing with id={listing_id} not found")
            return None
        
        # Build update dictionary
        update_dict = {
            'title': title,
            'description': description,
            'category': category,
            'size': size,
            'condition': condition,
            'location': location,
        }
        
        # Update image if provided
        if image_filename:
            # Keep existing images and add new one, or replace if needed
            existing_images = existing_doc.get('images', [])
            if image_filename not in existing_images:
                update_dict['images'] = [image_filename]  # Replace with new image
        
        # Update coordinates if provided
        if latitude is not None and longitude is not None:
            update_dict['latitude'] = latitude
            update_dict['longitude'] = longitude
            update_dict['location_coords'] = {
                'type': 'Point',
                'coordinates': [longitude, latitude]
            }
        
        # Perform update
        result = collection.update_one(
            {"_id": ObjectId(listing_id)},
            {"$set": update_dict}
        )
        
        if result.modified_count > 0:
            print(f"DEBUG: Successfully updated listing with id={listing_id}")
            # Return updated listing
            updated_doc = collection.find_one({"_id": ObjectId(listing_id)})
            return Listing.from_dict(updated_doc)
        else:
            print(f"WARNING: Update operation did not modify any documents")
            return None
            
    except Exception as e:
        print(f"ERROR: Failed to update listing: {e}")
        raise Exception(f"Failed to update listing: {e}")

def delete_listing(db, listing_id):
    """Delete a listing from MongoDB"""
    collection = get_listings_collection(db)
    if collection is None:
        print("WARNING: Database connection is None. Cannot delete listing.")
        return False
    
    try:
        result = collection.delete_one({"_id": ObjectId(listing_id)})
        
        if result.deleted_count > 0:
            print(f"DEBUG: Successfully deleted listing with id={listing_id}")
            return True
        else:
            print(f"WARNING: Delete operation did not delete any documents")
            return False
            
    except Exception as e:
        print(f"ERROR: Failed to delete listing: {e}")
        raise Exception(f"Failed to delete listing: {e}")

class Message:
    def __init__(self, id, conversation_id, sender_username, receiver_username, content, listing_id=None, created_at=None, is_read=False):
        self.id = id
        self.conversation_id = conversation_id
        self.sender_username = sender_username
        self.receiver_username = receiver_username
        self.content = content
        self.listing_id = listing_id
        self.created_at = created_at if isinstance(created_at, datetime) else (created_at or datetime.now())
        self.is_read = is_read
    
    @classmethod
    def from_dict(cls, doc):
        """Create a Message object from a MongoDB document"""
        return cls(
            id=str(doc.get('_id', '')),
            conversation_id=doc.get('conversation_id', ''),
            sender_username=doc.get('sender_username', ''),
            receiver_username=doc.get('receiver_username', ''),
            content=doc.get('content', ''),
            listing_id=doc.get('listing_id'),
            created_at=doc.get('created_at', datetime.now()),
            is_read=doc.get('is_read', False)
        )
    
    def to_dict(self):
        """Convert Message object to dictionary for MongoDB"""
        return {
            'conversation_id': self.conversation_id,
            'sender_username': self.sender_username,
            'receiver_username': self.receiver_username,
            'content': self.content,
            'listing_id': self.listing_id,
            'created_at': self.created_at,
            'is_read': self.is_read
        }

def get_messages_collection(db):
    """Get the messages collection from MongoDB"""
    if db is None:
        return None
    return db["messages"]

def create_message(db, conversation_id, sender_username, receiver_username, content, listing_id=None):
    """Create a new message and save it to MongoDB"""
    collection = get_messages_collection(db)
    if collection is None:
        return None
    
    new_message = Message(
        id="",
        conversation_id=conversation_id,
        sender_username=sender_username,
        receiver_username=receiver_username,
        content=content,
        listing_id=listing_id,
        created_at=datetime.utcnow()
    )
    
    message_dict = new_message.to_dict()
    result = collection.insert_one(message_dict)
    new_message.id = str(result.inserted_id)
    
    return new_message

def get_conversation_messages(db, conversation_id):
    """Get all messages for a conversation"""
    collection = get_messages_collection(db)
    if collection is None:
        return []
    
    cursor = collection.find({"conversation_id": conversation_id}).sort("created_at", 1)
    return [Message.from_dict(doc) for doc in cursor]

def get_user_conversations(db, username):
    """Get all conversations for a user, with latest message preview"""
    collection = get_messages_collection(db)
    if collection is None:
        return []
    
    # Get all messages where user is sender or receiver
    cursor = collection.find({
        "$or": [
            {"sender_username": username},
            {"receiver_username": username}
        ]
    }).sort("created_at", -1)
    
    # Group by conversation_id and get latest message for each
    conversations = {}
    for doc in cursor:
        conv_id = doc.get('conversation_id')
        if conv_id not in conversations:
            conversations[conv_id] = Message.from_dict(doc)
    
    # Convert to list and sort by latest message time
    conv_list = list(conversations.values())
    conv_list.sort(key=lambda x: x.created_at, reverse=True)
    
    return conv_list

def get_or_create_conversation_id(username1, username2, listing_id=None):
    """Generate a consistent conversation ID for two users"""
    # Sort usernames to ensure consistent conversation ID regardless of who initiates
    users = sorted([username1, username2])
    conv_id = f"{users[0]}_{users[1]}"
    if listing_id:
        conv_id += f"_{listing_id}"
    return conv_id

def mark_messages_as_read(db, conversation_id, username):
    """Mark all messages in a conversation as read for a specific user"""
    collection = get_messages_collection(db)
    if collection is None:
        return
    
    collection.update_many(
        {
            "conversation_id": conversation_id,
            "receiver_username": username,
            "is_read": False
        },
        {"$set": {"is_read": True}}
    )

def get_unread_count(db, username):
    """Get count of unread messages for a user"""
    collection = get_messages_collection(db)
    if collection is None:
        return 0
    
    return collection.count_documents({
        "receiver_username": username,
        "is_read": False
    })