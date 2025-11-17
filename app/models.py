from datetime import datetime
from types import SimpleNamespace
from typing import List, Optional


# -----------------------------
# In-memory "database" fallback
# -----------------------------
_IN_MEMORY_LISTINGS: List[SimpleNamespace] = []
_NEXT_ID = 1


def _use_in_memory(db) -> bool:
    """
    Decide whether to use the in-memory store.
    If db is None (no Mongo configured), we use in-memory.
    """
    return db is None


def _create_listing_object(
    listing_id: str,
    title: str,
    description: str,
    category: str,
    size: str,
    condition: str,
    location: str,
    user_id: str,
    image_filename: str,
    created_at: Optional[datetime] = None,
):
    """
    Helper to build a listing object with attribute-style access.
    """
    return SimpleNamespace(
        id=listing_id,
        title=title,
        description=description,
        category=category,
        size=size,
        condition=condition,
        location=location,
        user_id=user_id,
        image_filename=image_filename,
        created_at=created_at or datetime.utcnow(),
        is_available=True,
    )


# -----------------------------
# Public API used by routes.py
# -----------------------------

def create_listing(
    db,
    title: str,
    description: str,
    category: str,
    size: str,
    condition: str,
    location: str,
    user_id: str,
    image_filename: str,
):
    """
    Create a new listing.

    If a MongoDB database (db) is provided, this function can be extended
    to insert into the real 'listings' collection. For the Architectural
    Release iteration, when db is None, we use an in-memory store so that
    the Create Listing + View Listing use-cases work end-to-end.
    """
    global _NEXT_ID

    # In-memory mode (current iteration)
    if _use_in_memory(db):
        listing_id = str(_NEXT_ID)
        _NEXT_ID += 1

        listing = _create_listing_object(
            listing_id=listing_id,
            title=title,
            description=description,
            category=category,
            size=size,
            condition=condition,
            location=location,
            user_id=user_id,
            image_filename=image_filename,
        )

        _IN_MEMORY_LISTINGS.append(listing)
        return listing

    # -----------------------------
    # Future: MongoDB implementation
    # -----------------------------
    # Example (pseudo-code):
    #
    # collection = db["listings"]
    # doc = {
    #     "title": title,
    #     "description": description,
    #     "category": category,
    #     "size": size,
    #     "condition": condition,
    #     "location": location,
    #     "user_id": user_id,
    #     "image_filename": image_filename,
    #     "created_at": datetime.utcnow(),
    #     "is_available": True,
    # }
    # result = collection.insert_one(doc)
    # listing_id = str(result.inserted_id)
    # return _create_listing_object(listing_id=listing_id, **doc)
    #
    raise RuntimeError("MongoDB path not implemented yet")


def get_latest_listings(db, limit: int = 20):
    """
    Return the most recent listings.

    In-memory mode: sort by created_at descending.
    """
    if _use_in_memory(db):
        return sorted(
            _IN_MEMORY_LISTINGS,
            key=lambda l: l.created_at,
            reverse=True,
        )[:limit]

    # Future: MongoDB implementation
    #
    # collection = db["listings"]
    # docs = collection.find({"is_available": True}).sort("created_at", -1).limit(limit)
    # return [
    #     _create_listing_object(
    #         listing_id=str(doc["_id"]),
    #         title=doc["title"],
    #         description=doc["description"],
    #         category=doc["category"],
    #         size=doc["size"],
    #         condition=doc["condition"],
    #         location=doc["location"],
    #         user_id=doc["user_id"],
    #         image_filename=doc["image_filename"],
    #         created_at=doc.get("created_at"),
    #     )
    #     for doc in docs
    # ]
    #
    raise RuntimeError("MongoDB path not implemented yet")


def get_listing_by_id(db, listing_id: str):
    """
    Return a single listing by id, or None if not found.
    """
    if _use_in_memory(db):
        for l in _IN_MEMORY_LISTINGS:
            if l.id == str(listing_id):
                return l
        return None

    # Future: MongoDB implementation
    #
    # from bson.objectid import ObjectId
    # collection = db["listings"]
    # try:
    #     doc = collection.find_one({"_id": ObjectId(listing_id)})
    # except Exception:
    #     doc = None
    # if not doc:
    #     return None
    # return _create_listing_object(
    #     listing_id=str(doc["_id"]),
    #     title=doc["title"],
    #     description=doc["description"],
    #     category=doc["category"],
    #     size=doc["size"],
    #     condition=doc["condition"],
    #     location=doc["location"],
    #     user_id=doc["user_id"],
    #     image_filename=doc["image_filename"],
    #     created_at=doc.get("created_at"),
    # )
    #
    raise RuntimeError("MongoDB path not implemented yet")


def search_listings(db, query=None, category=None, location=None, max_distance=None):
    """
    Search listings by text + filters.
    """
    if _use_in_memory(db):
        results = _IN_MEMORY_LISTINGS

        if query:
            q = query.lower()
            results = [
                l
                for l in results
                if q in l.title.lower() or q in l.description.lower()
            ]

        if category:
            results = [l for l in results if l.category == category]

        if location:
            results = [l for l in results if l.location == location]

        # max_distance ignored in in-memory mode (no geo)
        return results

    # Future: MongoDB implementation
    #
    # collection = db["listings"]
    # mongo_query = {"is_available": True}
    #
    # if query:
    #     mongo_query["$or"] = [
    #         {"title": {"$regex": query, "$options": "i"}},
    #         {"description": {"$regex": query, "$options": "i"}},
    #     ]
    # if category:
    #     mongo_query["category"] = category
    # if location:
    #     mongo_query["location"] = {"$regex": location, "$options": "i"}
    #
    # docs = collection.find(mongo_query).sort("created_at", -1)
    # return [
    #     _create_listing_object(
    #         listing_id=str(doc["_id"]),
    #         title=doc["title"],
    #         description=doc["description"],
    #         category=doc["category"],
    #         size=doc["size"],
    #         condition=doc["condition"],
    #         location=doc["location"],
    #         user_id=doc["user_id"],
    #         image_filename=doc["image_filename"],
    #         created_at=doc.get("created_at"),
    #     )
    #     for doc in docs
    # ]
    #
    raise RuntimeError("MongoDB path not implemented yet")


def get_listings_by_user(db, username: str):
    """
    Return all listings created by the given username.
    """
    if _use_in_memory(db):
        return [l for l in _IN_MEMORY_LISTINGS if l.user_id == username]

    # Future: MongoDB implementation
    #
    # collection = db["listings"]
    # docs = collection.find({"user_id": username, "is_available": True}).sort("created_at", -1)
    # return [
    #     _create_listing_object(
    #         listing_id=str(doc["_id"]),
    #         title=doc["title"],
    #         description=doc["description"],
    #         category=doc["category"],
    #         size=doc["size"],
    #         condition=doc["condition"],
    #         location=doc["location"],
    #         user_id=doc["user_id"],
    #         image_filename=doc["image_filename"],
    #         created_at=doc.get("created_at"),
    #     )
    #     for doc in docs
    # ]
    #
    raise RuntimeError("MongoDB path not implemented yet")