from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from app.models import get_latest_listings, search_listings, get_listing_by_id, create_listing, update_listing, delete_listing, get_listings_by_user, create_message, get_conversation_messages, get_user_conversations, get_or_create_conversation_id, mark_messages_as_read, get_unread_count
from app.geocoding import geocode_location, geocode_postal_code

main = Blueprint("main", __name__)

# Home route - Marketplace
@main.route("/")
def home():
    username = session.get("username")  # None if not logged in
    db = getattr(current_app, "mongo_db", None)
    
    # Get search parameters
    search_query = request.args.get('search', '')
    location_filter = request.args.get('location', '')
    category_filter = request.args.get('category', '')
    distance_filter = request.args.get('distance', '')
    
    # Get coordinates from browser geolocation (if provided)
    user_lat = request.args.get('user_lat')
    user_lon = request.args.get('user_lon')
    if user_lat and user_lon:
        try:
            user_lat = float(user_lat)
            user_lon = float(user_lon)
        except (ValueError, TypeError):
            user_lat = None
            user_lon = None
    
    max_distance_km = None
    
    # Get user's profile location for display (if logged in)
    user_profile_location = None
    if username and db is not None:
        user = db["users"].find_one({"username": username})
        if user:
            user_profile_location = user.get("location")
            # If no coordinates from browser, try to use profile coordinates
            if not user_lat and not user_lon:
                user_lat = user.get("latitude")
                user_lon = user.get("longitude")
                if user_lat and user_lon and not location_filter:
                    location_filter = user_profile_location
    
    # Geocode user location if provided (and not already have coordinates)
    if location_filter and not (user_lat and user_lon):
        print(f"DEBUG ROUTES: Geocoding location_filter='{location_filter}'")
        # Try to geocode the location (postal code or city)
        geocode_result = geocode_location(location_filter)
        if geocode_result:
            user_lat, user_lon, formatted_location = geocode_result
            print(f"DEBUG ROUTES: Successfully geocoded to lat={user_lat}, lon={user_lon}")
        else:
            # If geocoding fails, still try to search by text location
            print(f"DEBUG ROUTES: Geocoding failed for '{location_filter}'")
            flash(f"Could not find exact coordinates for '{location_filter}'. Showing results by location text match.", "warning")
    
    # Set max distance if distance filter is provided
    # Note: We'll still try to use distance even if we don't have user coordinates yet
    if distance_filter:
        try:
            max_distance_km = float(distance_filter) if distance_filter else None
        except (ValueError, TypeError):
            max_distance_km = None
    
    # If distance filter is set but we don't have coordinates, try to geocode location_filter
    if max_distance_km is not None and not (user_lat and user_lon) and location_filter:
        geocode_result = geocode_location(location_filter)
        if geocode_result:
            user_lat, user_lon, formatted_location = geocode_result
    
    # Get listings based on search/filters
    # If location or distance filter is provided, always use search (even if no other filters)
    # But if distance_filter is empty/None, don't filter by distance - show all listings
    if search_query or location_filter or category_filter or (distance_filter and distance_filter.strip()):
        # Debug: Print search parameters (force flush to see immediately)
        import sys
        print(f"DEBUG: search_query={search_query}, location_filter={location_filter}, category_filter={category_filter}, distance_filter={distance_filter}", flush=True)
        print(f"DEBUG: user_lat={user_lat}, user_lon={user_lon}, max_distance_km={max_distance_km}", flush=True)
        
        listings = search_listings(
            db,
            query=search_query if search_query else None,
            category=category_filter if category_filter else None,
            location=location_filter if location_filter and not (user_lat and user_lon) else None,
            max_distance=max_distance_km,
            user_lat=user_lat,
            user_lon=user_lon
        )
        print(f"DEBUG: Found {len(listings)} listings", flush=True)
        
        # If no listings found, try to get all listings to see if database has any
        if len(listings) == 0 and db is not None:
            all_listings = db["listings"].find({"is_available": True}).limit(5)
            all_listings_list = list(all_listings)
            print(f"DEBUG: Database has {len(all_listings_list)} available listings total", flush=True)
            for listing_doc in all_listings_list:
                print(f"DEBUG: Sample listing - title: {listing_doc.get('title')}, location: {listing_doc.get('location')}, lat: {listing_doc.get('latitude')}, lon: {listing_doc.get('longitude')}", flush=True)
    else:
        listings = get_latest_listings(db)
    
    
    # Get unread message count if logged in
    unread_count = 0
    if username and db is not None:
        unread_count = get_unread_count(db, username)
    
    return render_template("home.html", 
                         username=username, 
                         listings=listings,
                         search_query=search_query,
                         location_filter=location_filter,
                         category_filter=category_filter,
                         distance_filter=distance_filter,
                         user_profile_location=user_profile_location,
                         unread_count=unread_count)

# Login route
@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            return render_template("login.html", error="Username and password are required.")

        # Verify against MongoDB if configured
        db = getattr(current_app, "mongo_db", None)
        if db is None:
            # Fallback: simple session login (no DB configured)
            session["username"] = username
            return redirect(url_for("main.home"))

        user = db["users"].find_one({"username": username})
        if not user or not check_password_hash(user.get("password_hash", ""), password):
            return render_template("login.html", error="Invalid username or password.")

        session["username"] = username
        return redirect(url_for("main.home"))

    return render_template("login.html")

# Logout route
@main.route("/logout")
def logout():
    session.pop("username", None)  # Remove username from session
    return redirect(url_for("main.home"))

# Register route
@main.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        location = request.form.get("location")

        # Basic validation
        if not username or not email or not password or not confirm_password or not location:
            return render_template("register.html", error="All fields are required.")
        
        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match.")
        
        
        if len(password) < 8:
            return render_template("register.html", error="Password must be at least 8 characters long.")

        db = getattr(current_app, "mongo_db", None)
        if db is None:
            # Fallback if DB not configured
            session["username"] = username
            return redirect(url_for("main.home"))

        users = db["users"]
        # Check if username or email already exists
        existing = users.find_one({"$or": [{"username": username}, {"email": email}]})
        if existing:
            return render_template("register.html", error="Username or email already exists.")

        password_hash = generate_password_hash(password)
        
        # Geocode user location to store coordinates
        latitude = None
        longitude = None
        geocode_result = geocode_location(location)
        if geocode_result:
            latitude, longitude, formatted_location = geocode_result
        
        users.insert_one({
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "location": location,
            "latitude": latitude,
            "longitude": longitude,
            "created_at": datetime.utcnow()
        })

        session["username"] = username
        return redirect(url_for("main.home"))

    return render_template("register.html")

# View individual listing route
@main.route("/listing/<listing_id>")
def view_listing(listing_id):
    username = session.get("username")
    db = getattr(current_app, "mongo_db", None)
    listing = get_listing_by_id(db, listing_id)
    
    if not listing:
        flash("Listing not found.", "error")
        return redirect(url_for("main.home"))
    
    # Get unread message count if logged in
    unread_count = 0
    if username and db is not None:
        unread_count = get_unread_count(db, username)
    
    return render_template("listing_detail.html", listing=listing, username=username, unread_count=unread_count)

# Create listing route (requires authentication)
@main.route("/create", methods=["GET", "POST"])
def create_listing_page():
    username = session.get("username")
    
    # Require authentication to create listing
    if not username:
        flash("Please log in to create a listing.", "error")
        return redirect(url_for("main.login"))
    
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        category = request.form.get("category")
        size_list = request.form.getlist("size")
        size = ", ".join(size_list) if size_list else request.form.get("size")
        condition = request.form.get("condition")
        location = request.form.get("location")
        image_file = request.files.get("image")
        
        # Basic validation
        if not all([title, description, category, condition, location]):
            return render_template("create_listing.html", 
                                 username=username,
                                 error="All fields are required.")
        
        # Validate size (at least one must be selected)
        if not size or not size.strip():
            return render_template("create_listing.html", 
                                 username=username,
                                 error="Please select at least one size.")
        
        # Validate image
        if not image_file or image_file.filename == '':
            return render_template("create_listing.html", 
                                 username=username,
                                 error="Please upload an image.")
        
        # Check if file is an image
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        file_ext = image_file.filename.rsplit('.', 1)[1].lower() if '.' in image_file.filename else ''
        if file_ext not in allowed_extensions:
            return render_template("create_listing.html", 
                                 username=username,
                                 error="Invalid image format. Please upload JPG, PNG, GIF, or WEBP.")
        
        # Save image file
        upload_folder = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = secure_filename(image_file.filename)
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(upload_folder, filename)
        image_file.save(filepath)
        
        # Geocode the location to get coordinates
        latitude = None
        longitude = None
        geocode_result = geocode_location(location)
        if geocode_result:
            latitude, longitude, formatted_location = geocode_result
            # Optionally update location with formatted version
            # location = formatted_location
        
        # Create the listing
        db = getattr(current_app, "mongo_db", None)
        
        # Check if database is available
        if db is None:
            # Check if MongoDB URI is configured
            cfg = getattr(current_app, "config", None)
            if cfg:
                from config import get_config
                config = get_config()
                if not config.MONGO_URI:
                    error_msg = "MongoDB is not configured. Please set MONGO_URI in your .env file."
                    print(f"ERROR: {error_msg}")
                else:
                    error_msg = f"MongoDB connection failed. URI configured but connection not established. Please check your MongoDB server."
                    print(f"ERROR: {error_msg}")
            else:
                error_msg = "Database connection not available. Please restart the application."
                print(f"ERROR: {error_msg}")
            
            flash("Database connection error. Please check server logs for details.", "error")
            return render_template("create_listing.html", 
                                 username=username,
                                 error="Database connection error. Please check that MongoDB is running and configured.")
        
        try:
            new_listing = create_listing(
                db,
                title=title,
                description=description,
                category=category,
                size=size,
                condition=condition,
                location=location,
                user_id=username,
                image_filename=filename,
                latitude=latitude,
                longitude=longitude
            )
            
            # Verify the listing was created and has a valid ID
            if not new_listing or not new_listing.id or new_listing.id == "demo":
                flash("Failed to save listing. Please try again.", "error")
                return render_template("create_listing.html", 
                                     username=username,
                                     error="Failed to save listing. Please try again.")
            
            flash("Listing created successfully!", "success")
            return redirect(url_for("main.view_listing", listing_id=new_listing.id))
            
        except Exception as e:
            print(f"ERROR creating listing: {e}")
            flash(f"Error creating listing: {str(e)}", "error")
            return render_template("create_listing.html", 
                                 username=username,
                                 error=f"Error creating listing: {str(e)}")
    
    return render_template("create_listing.html", username=username)

# Contact/Message seller route (requires authentication)
@main.route("/listing/<listing_id>/contact", methods=["POST"])
def contact_seller(listing_id):
    username = session.get("username")
    db = getattr(current_app, "mongo_db", None)
    
    # Require authentication to contact seller
    if not username:
        flash("Please log in to contact the seller.", "error")
        return redirect(url_for("main.login"))
    
    listing = get_listing_by_id(db, listing_id)
    if not listing:
        flash("Listing not found.", "error")
        return redirect(url_for("main.home"))
    
    # Don't allow users to message themselves
    if listing.user_id == username:
        flash("You cannot message yourself.", "error")
        return redirect(url_for("main.view_listing", listing_id=listing_id))
    
    # Create conversation and redirect to messages
    conversation_id = get_or_create_conversation_id(username, listing.user_id, listing_id)
    
    # Check if this is the first message in the conversation
    existing_messages = get_conversation_messages(db, conversation_id)
    if not existing_messages:
        # Create initial message
        initial_message = f"Hi! I'm interested in your listing '{listing.title}'."
        create_message(db, conversation_id, username, listing.user_id, initial_message, listing_id)
        flash("Message sent! Check your messages to continue the conversation.", "success")
    else:
        flash("Redirecting to your conversation...", "info")
    
    return redirect(url_for("main.messages", conversation_id=conversation_id))

# My Listings route (requires authentication)
@main.route("/my-listings")
def my_listings():
    username = session.get("username")
    
    # Require authentication to view my listings
    if not username:
        flash("Please log in to view your listings.", "error")
        return redirect(url_for("main.login"))
    
    # Get all listings created by this user
    db = getattr(current_app, "mongo_db", None)
    user_listings = get_listings_by_user(db, username)
    
    # Get unread message count
    unread_count = 0
    if db is not None:
        unread_count = get_unread_count(db, username)
    
    return render_template("my_listings.html", username=username, listings=user_listings, unread_count=unread_count)

# Messages route - list all conversations
@main.route("/messages")
def messages():
    username = session.get("username")
    
    # Require authentication
    if not username:
        flash("Please log in to view your messages.", "error")
        return redirect(url_for("main.login"))
    
    db = getattr(current_app, "mongo_db", None)
    conversation_id = request.args.get('conversation_id')
    
    # Get all conversations for this user
    conversations = get_user_conversations(db, username)
    
    # Get unread count
    unread_count = get_unread_count(db, username)
    
    # If a specific conversation is requested, get its messages
    messages_list = []
    other_user = None
    listing = None
    if conversation_id:
        messages_list = get_conversation_messages(db, conversation_id)
        # Mark messages as read when viewing conversation
        mark_messages_as_read(db, conversation_id, username)
        
        # Get the other user's username
        if messages_list:
            first_message = messages_list[0]
            if first_message.sender_username == username:
                other_user = first_message.receiver_username
            else:
                other_user = first_message.sender_username
            
            # Get listing info if available
            if first_message.listing_id:
                listing = get_listing_by_id(db, first_message.listing_id)
    
    return render_template("messages.html", 
                         username=username,
                         conversations=conversations,
                         messages=messages_list,
                         conversation_id=conversation_id,
                         other_user=other_user,
                         listing=listing,
                         unread_count=unread_count)

# Send message route
@main.route("/messages/send", methods=["POST"])
def send_message():
    username = session.get("username")
    
    # Require authentication
    if not username:
        flash("Please log in to send messages.", "error")
        return redirect(url_for("main.login"))
    
    conversation_id = request.form.get("conversation_id")
    receiver_username = request.form.get("receiver_username")
    content = request.form.get("content")
    listing_id = request.form.get("listing_id")
    
    if not conversation_id or not receiver_username or not content:
        flash("Missing required fields.", "error")
        return redirect(url_for("main.messages"))
    
    db = getattr(current_app, "mongo_db", None)
    create_message(db, conversation_id, username, receiver_username, content, listing_id if listing_id else None)
    
    flash("Message sent!", "success")
    return redirect(url_for("main.messages", conversation_id=conversation_id))

# Edit listing route (requires authentication and ownership)
@main.route("/listing/<listing_id>/edit", methods=["GET", "POST"])
def edit_listing(listing_id):
    username = session.get("username")
    
    # Require authentication
    if not username:
        flash("Please log in to edit a listing.", "error")
        return redirect(url_for("main.login"))
    
    db = getattr(current_app, "mongo_db", None)
    listing = get_listing_by_id(db, listing_id)
    
    if not listing:
        flash("Listing not found.", "error")
        return redirect(url_for("main.home"))
    
    # Check ownership
    if listing.user_id != username:
        flash("You can only edit your own listings.", "error")
        return redirect(url_for("main.view_listing", listing_id=listing_id))
    
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        category = request.form.get("category")
        size_list = request.form.getlist("size")
        size = ", ".join(size_list) if size_list else request.form.get("size")
        condition = request.form.get("condition")
        location = request.form.get("location")
        image_file = request.files.get("image")
        
        # Basic validation
        if not all([title, description, category, condition, location]):
            return render_template("edit_listing.html", 
                                 username=username,
                                 listing=listing,
                                 error="All fields are required.")
        
        # Validate size (at least one must be selected)
        if not size or not size.strip():
            return render_template("edit_listing.html", 
                                 username=username,
                                 listing=listing,
                                 error="Please select at least one size.")
        
        # Handle image upload (optional for edit)
        image_filename = None
        if image_file and image_file.filename != '':
            # Check if file is an image
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            file_ext = image_file.filename.rsplit('.', 1)[1].lower() if '.' in image_file.filename else ''
            if file_ext not in allowed_extensions:
                return render_template("edit_listing.html", 
                                     username=username,
                                     listing=listing,
                                     error="Invalid image format. Please upload JPG, PNG, GIF, or WEBP.")
            
            # Save image file
            upload_folder = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = secure_filename(image_file.filename)
            filename = f"{timestamp}_{filename}"
            filepath = os.path.join(upload_folder, filename)
            image_file.save(filepath)
            image_filename = filename
        
        # Geocode the location to get coordinates
        latitude = None
        longitude = None
        geocode_result = geocode_location(location)
        if geocode_result:
            latitude, longitude, formatted_location = geocode_result
        
        # Update the listing
        try:
            updated_listing = update_listing(
                db,
                listing_id=listing_id,
                title=title,
                description=description,
                category=category,
                size=size,
                condition=condition,
                location=location,
                image_filename=image_filename,
                latitude=latitude,
                longitude=longitude
            )
            
            if updated_listing:
                flash("Listing updated successfully!", "success")
                return redirect(url_for("main.view_listing", listing_id=listing_id))
            else:
                flash("Failed to update listing. Please try again.", "error")
                return render_template("edit_listing.html", 
                                     username=username,
                                     listing=listing,
                                     error="Failed to update listing. Please try again.")
        except Exception as e:
            print(f"ERROR updating listing: {e}")
            flash(f"Error updating listing: {str(e)}", "error")
            return render_template("edit_listing.html", 
                                 username=username,
                                 listing=listing,
                                 error=f"Error updating listing: {str(e)}")
    
    # GET request - show edit form
    unread_count = 0
    if db is not None:
        unread_count = get_unread_count(db, username)
    
    return render_template("edit_listing.html", username=username, listing=listing, unread_count=unread_count)

# Delete listing route (requires authentication and ownership)
@main.route("/listing/<listing_id>/delete", methods=["POST"])
def delete_listing_route(listing_id):
    username = session.get("username")
    
    # Require authentication
    if not username:
        flash("Please log in to delete a listing.", "error")
        return redirect(url_for("main.login"))
    
    db = getattr(current_app, "mongo_db", None)
    listing = get_listing_by_id(db, listing_id)
    
    if not listing:
        flash("Listing not found.", "error")
        return redirect(url_for("main.home"))
    
    # Check ownership
    if listing.user_id != username:
        flash("You can only delete your own listings.", "error")
        return redirect(url_for("main.view_listing", listing_id=listing_id))
    
    try:
        success = delete_listing(db, listing_id)
        if success:
            flash("Listing deleted successfully!", "success")
            return redirect(url_for("main.my_listings"))
        else:
            flash("Failed to delete listing. Please try again.", "error")
            return redirect(url_for("main.view_listing", listing_id=listing_id))
    except Exception as e:
        print(f"ERROR deleting listing: {e}")
        flash(f"Error deleting listing: {str(e)}", "error")
        return redirect(url_for("main.view_listing", listing_id=listing_id))

# Serve uploaded images
@main.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(os.path.join(current_app.root_path, 'static', 'img', 'uploads'), filename)
