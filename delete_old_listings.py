"""
Script to delete all listings except the latest one.
Uses Flask app context to access the same database connection.
"""

from app import create_app
from pymongo import MongoClient

# Create Flask app to get database connection
app = create_app()

with app.app_context():
    db = app.mongo_db
    
    if db is None:
        print("ERROR: Could not connect to MongoDB.")
        print("Please ensure MongoDB is running and MONGO_URI is configured.")
        exit(1)
    
    collection = db["listings"]
    
    print("✓ Connected to MongoDB")
    
    # Get all listings sorted by created_at (newest first)
    all_listings = list(collection.find({}).sort("created_at", -1))
    
    if len(all_listings) == 0:
        print("No listings found in database.")
        exit(0)
    
    if len(all_listings) == 1:
        print("Only one listing found. Nothing to delete.")
        exit(0)
    
    # Keep the latest one (first in sorted list)
    latest_listing = all_listings[0]
    listings_to_delete = all_listings[1:]
    
    print(f"\nTotal listings: {len(all_listings)}")
    print(f"Keeping latest listing:")
    print(f"  - ID: {latest_listing.get('_id')}")
    print(f"  - Title: {latest_listing.get('title')}")
    print(f"  - Created: {latest_listing.get('created_at')}")
    print(f"\nWill delete {len(listings_to_delete)} listing(s):")
    
    for listing in listings_to_delete:
        print(f"  - {listing.get('title')} (ID: {listing.get('_id')})")
    
    # Confirm deletion
    print(f"\n⚠️  WARNING: This will permanently delete {len(listings_to_delete)} listing(s).")
    confirm = input("Type 'DELETE' to confirm: ")
    
    if confirm != "DELETE":
        print("Cancelled. No listings were deleted.")
        exit(0)
    
    # Delete all except the latest
    deleted_count = 0
    for listing in listings_to_delete:
        try:
            result = collection.delete_one({'_id': listing.get('_id')})
            if result.deleted_count > 0:
                deleted_count += 1
                print(f"✓ Deleted: {listing.get('title')}")
        except Exception as e:
            print(f"✗ Error deleting {listing.get('title')}: {e}")
    
    print(f"\n✓ Successfully deleted {deleted_count} listing(s).")
    print(f"✓ Kept latest listing: {latest_listing.get('title')}")
