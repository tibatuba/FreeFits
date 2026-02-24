from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, send_from_directory, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import requests
from app.models import (
    get_latest_listings, search_listings, get_listing_by_id, create_listing, update_listing, delete_listing,
    get_listings_by_user, create_message, get_conversation_messages, get_user_conversations, get_or_create_conversation_id,
    mark_messages_as_read, get_unread_count,
    create_flag, get_all_flagged_listings, resolve_flag,
    delete_user_and_data,
)
from app.geocoding import geocode_location, geocode_postal_code
from app.image_validation import validate_clothing_image, validate_clothing_image_api4ai, validate_clothing_image_rekognition
from app.s3_storage import upload_image_to_s3, get_s3_image_url, delete_image_from_s3, check_s3_configured
import tempfile

main = Blueprint("main", __name__)


def require_admin():
    """Require current user to be admin. Call at start of admin routes. Aborts with 403 if not."""
    username = session.get("username")
    if not username:
        abort(403)
    db = getattr(current_app, "mongo_db", None)
    if not db:
        abort(403)
    user = db["users"].find_one({"username": username})
    if not user or user.get("role") != "admin":
        abort(403)


@main.route("/api/ping")
def api_ping():
    """Simple health check; confirms the deployed app has the latest routes."""
    return jsonify({"ok": True})


def get_image_url(image_key):
    """
    Helper function to get the URL for an image.
    Checks if image is from S3 or filesystem and returns appropriate URL.
    
    Args:
        image_key: Image filename/key (from database)
    
    Returns:
        Image URL string
    """
    if not image_key:
        return None
    
    # Check if it's an S3 key (not a filesystem path)
    is_s3_image = not image_key.startswith('/') and 'uploads' not in image_key
    
    if is_s3_image:
        try:
            is_configured, _ = check_s3_configured()
            if is_configured:
                s3_url = get_s3_image_url(image_key, signed=False)
                if s3_url:
                    return s3_url
        except Exception as e:
            current_app.logger.warning(f"Error generating S3 URL: {e}")
    
    # Fallback to filesystem URL
    return url_for('main.uploaded_file', filename=image_key)

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
    
    # Generate image URLs for all listings (S3 or filesystem)
    for listing in listings:
        if listing.images and len(listing.images) > 0:
            listing.image_url = get_image_url(listing.images[0])
        else:
            listing.image_url = None
    
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


# Delete account (with confirmation)
@main.route("/account/delete", methods=["GET", "POST"])
def delete_account():
    username = session.get("username")
    if not username:
        flash("Please log in to manage your account.", "error")
        return redirect(url_for("main.login"))
    db = getattr(current_app, "mongo_db", None)
    if not db:
        flash("Service unavailable.", "error")
        return redirect(url_for("main.home"))
    if request.method == "POST":
        confirm = (request.form.get("confirm") or "").strip()
        if confirm != username:
            flash("Confirmation did not match your username. Account was not deleted.", "error")
            return redirect(url_for("main.delete_account"))
        if delete_user_and_data(db, username):
            session.pop("username", None)
            flash("Your account and all associated data have been permanently deleted.", "success")
            return redirect(url_for("main.home"))
        flash("Could not delete account. Please try again.", "error")
        return redirect(url_for("main.delete_account"))
    return render_template("delete_account.html", username=username)


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
        
        # Everyone gets role "user" on signup. Only you can make someone admin by updating the DB (e.g. in MongoDB: db.users.updateOne({ username: "x" }, { $set: { role: "admin" } })).
        users.insert_one({
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "location": location,
            "latitude": latitude,
            "longitude": longitude,
            "created_at": datetime.utcnow(),
            "role": "user",
        })

        session["username"] = username
        return redirect(url_for("main.home"))

    return render_template("register.html")

# --- Flag listing (report) - any logged-in user (except owner) ---
@main.route("/listing/<listing_id>/flag", methods=["GET", "POST"])
def flag_listing(listing_id):
    username = session.get("username")
    if not username:
        flash("Please log in to report a listing.", "error")
        return redirect(url_for("main.login"))
    db = getattr(current_app, "mongo_db", None)
    if not db:
        flash("Service unavailable.", "error")
        return redirect(url_for("main.view_listing", listing_id=listing_id))
    listing = get_listing_by_id(db, listing_id)
    if not listing:
        flash("Listing not found.", "error")
        return redirect(url_for("main.home"))
    if listing.user_id == username:
        flash("You cannot report your own listing.", "error")
        return redirect(url_for("main.view_listing", listing_id=listing_id))
    if request.method == "POST":
        reason = (request.form.get("reason") or "").strip() or "No reason given"
        create_flag(db, listing_id, username, reason)
        flash("Thank you. This listing has been reported for review.", "success")
        return redirect(url_for("main.view_listing", listing_id=listing_id))
    return render_template("flag_listing.html", listing=listing, username=username)


# View individual listing route
@main.route("/listing/<listing_id>")
def view_listing(listing_id):
    username = session.get("username")
    db = getattr(current_app, "mongo_db", None)
    listing = get_listing_by_id(db, listing_id)
    
    if not listing:
        flash("Listing not found.", "error")
        return redirect(url_for("main.home"))
    
    # Get image URL (S3 or filesystem)
    image_url = None
    if listing.images and len(listing.images) > 0:
        image_url = get_image_url(listing.images[0])
    
    # Get unread message count if logged in
    unread_count = 0
    if username and db is not None:
        unread_count = get_unread_count(db, username)
    
    return render_template("listing_detail.html", listing=listing, username=username, unread_count=unread_count, image_url=image_url)

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
        
        # Basic validation (preserve form data on error)
        if not all([title, description, category, condition, location]):
            return render_template("create_listing.html",
                                 username=username,
                                 error="All fields are required.",
                                 form=request.form,
                                 form_size_list=request.form.getlist("size"))
        
        # Validate size (at least one must be selected)
        if not size or not size.strip():
            return render_template("create_listing.html",
                                 username=username,
                                 error="Please select at least one size.",
                                 form=request.form,
                                 form_size_list=request.form.getlist("size"))
        
        # Validate image
        if not image_file or image_file.filename == '':
            return render_template("create_listing.html",
                                 username=username,
                                 error="Please upload an image.",
                                 form=request.form,
                                 form_size_list=request.form.getlist("size"))
        
        # Check if file is an image
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        file_ext = image_file.filename.rsplit('.', 1)[1].lower() if '.' in image_file.filename else ''
        if file_ext not in allowed_extensions:
            return render_template("create_listing.html",
                                 username=username,
                                 error="Invalid image format. Please upload JPG, PNG, GIF, or WEBP.",
                                 form=request.form,
                                 form_size_list=request.form.getlist("size"))
        
        # Check file size (10MB limit)
        image_file.seek(0, os.SEEK_END)  # Seek to end
        file_size = image_file.tell()  # Get file size
        image_file.seek(0)  # Reset to beginning
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
        if file_size > MAX_FILE_SIZE:
            return render_template("create_listing.html",
                                 username=username,
                                 error=f"Image file is too large. Maximum size is {MAX_FILE_SIZE / (1024*1024):.1f}MB.",
                                 form=request.form,
                                 form_size_list=request.form.getlist("size"))
        
        # Check if S3 is configured
        use_s3 = True
        s3_error = None
        try:
            is_configured, s3_error = check_s3_configured()
            if not is_configured:
                current_app.logger.warning(f"S3 not configured, falling back to filesystem: {s3_error}")
                use_s3 = False
        except Exception as e:
            current_app.logger.warning(f"Error checking S3 configuration: {e}")
            use_s3 = False
        
        # Save image temporarily for validation (Rekognition needs file path)
        temp_filepath = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
                image_file.save(temp_file.name)
                temp_filepath = temp_file.name
            
            # Validate that the image contains clothing items
            from config import get_config
            config = get_config()
            validation_api = config.IMAGE_VALIDATION_API or "rekognition"
            
            is_valid = True
            error_message = None
            
            if validation_api == "rekognition":
                # Use AWS Rekognition (RECOMMENDED - reliable, free tier, part of AWS)
                aws_key = config.AWS_ACCESS_KEY_ID
                aws_secret = config.AWS_SECRET_ACCESS_KEY
                aws_region = config.AWS_REGION
                if aws_key and aws_secret:
                    is_valid, error_message = validate_clothing_image_rekognition(temp_filepath, aws_key, aws_secret, aws_region)
                else:
                    current_app.logger.warning("AWS credentials not configured. Skipping image validation.")
            elif validation_api == "api4ai":
                # Use api4ai Fashion API
                api4ai_key = config.API4AI_API_KEY
                if api4ai_key:
                    is_valid, error_message = validate_clothing_image_api4ai(temp_filepath, api4ai_key)
                else:
                    current_app.logger.warning("api4ai API key not configured. Skipping image validation.")
            else:
                # Use Imagga API (fallback)
                imagga_key = config.IMAGGA_API_KEY
                imagga_secret = config.IMAGGA_API_SECRET
                if imagga_key and imagga_secret:
                    is_valid, error_message = validate_clothing_image(temp_filepath, imagga_key, imagga_secret)
                else:
                    # If API credentials are not configured, log a warning but allow upload
                    current_app.logger.warning("Imagga API credentials not configured. Skipping image validation.")
            
            if not is_valid:
                # Clean up temp file
                try:
                    if temp_filepath and os.path.exists(temp_filepath):
                        os.remove(temp_filepath)
                except:
                    pass
                return render_template("create_listing.html",
                                     username=username,
                                     error=error_message or "Image validation failed. Please upload an image of a clothing item.",
                                     form=request.form,
                                     form_size_list=request.form.getlist("size"))
            
            # Upload to S3 or save to filesystem
            filename = None
            if use_s3:
                # Upload to S3 - read from temp file to avoid file handle issues
                try:
                    with open(temp_filepath, 'rb') as temp_file:
                        success, s3_key, upload_error = upload_image_to_s3(temp_file)
                    
                    if success:
                        filename = s3_key
                        current_app.logger.info(f"Successfully uploaded image to S3: {s3_key}")
                    else:
                        # Upload failed, fallback to filesystem
                        current_app.logger.warning(f"S3 upload failed: {upload_error}. Falling back to filesystem.")
                        use_s3 = False
                except Exception as e:
                    current_app.logger.error(f"Error uploading to S3: {e}. Falling back to filesystem.")
                    use_s3 = False
            
            if not use_s3:
                # Fallback to filesystem storage - copy from temp file
                upload_folder = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
                os.makedirs(upload_folder, exist_ok=True)
                
                # Generate unique filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                original_filename = image_file.filename if hasattr(image_file, 'filename') else 'image'
                filename = secure_filename(original_filename)
                filename = f"{timestamp}_{filename}"
                filepath = os.path.join(upload_folder, filename)
                
                # Copy from temp file to upload folder
                import shutil
                shutil.copy2(temp_filepath, filepath)
            
            # Clean up temp file
            try:
                if temp_filepath and os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
            except:
                pass
                
        except Exception as e:
            # Clean up temp file on error
            try:
                if temp_filepath and os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
            except:
                pass
            current_app.logger.error(f"Error processing image: {e}")
            return render_template("create_listing.html",
                                 username=username,
                                 error=f"Error processing image: {str(e)}",
                                 form=request.form,
                                 form_size_list=request.form.getlist("size"))
        
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
                                 error="Database connection error. Please check that MongoDB is running and configured.",
                                 form=request.form,
                                 form_size_list=request.form.getlist("size"))
        
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
                                     error="Failed to save listing. Please try again.",
                                     form=request.form,
                                     form_size_list=request.form.getlist("size"))
            
            flash("Listing created successfully!", "success")
            return redirect(url_for("main.view_listing", listing_id=new_listing.id))
            
        except Exception as e:
            print(f"ERROR creating listing: {e}")
            flash(f"Error creating listing: {str(e)}", "error")
            return render_template("create_listing.html",
                                 username=username,
                                 error=f"Error creating listing: {str(e)}",
                                 form=request.form,
                                 form_size_list=request.form.getlist("size"))
    
    return render_template("create_listing.html", username=username, form=request.form, form_size_list=request.form.getlist("size"))

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
    
    # Generate image URLs for all listings (S3 or filesystem)
    for listing in user_listings:
        if listing.images and len(listing.images) > 0:
            listing.image_url = get_image_url(listing.images[0])
        else:
            listing.image_url = None
    
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
            
            # Check file size (10MB limit)
            image_file.seek(0, os.SEEK_END)  # Seek to end
            file_size = image_file.tell()  # Get file size
            image_file.seek(0)  # Reset to beginning
            MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
            if file_size > MAX_FILE_SIZE:
                return render_template("edit_listing.html",
                                     username=username,
                                     listing=listing,
                                     error=f"Image file is too large. Maximum size is {MAX_FILE_SIZE / (1024*1024):.1f}MB.")
            
            # Check if S3 is configured
            use_s3 = True
            try:
                is_configured, s3_error = check_s3_configured()
                if not is_configured:
                    current_app.logger.warning(f"S3 not configured, falling back to filesystem: {s3_error}")
                    use_s3 = False
            except Exception as e:
                current_app.logger.warning(f"Error checking S3 configuration: {e}")
                use_s3 = False
            
            # Save image temporarily for validation
            temp_filepath = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
                    image_file.save(temp_file.name)
                    temp_filepath = temp_file.name
                
                # Validate that the image contains clothing items
                from config import get_config
                config = get_config()
                validation_api = config.IMAGE_VALIDATION_API or "rekognition"
                
                is_valid = True
                error_message = None
                
                if validation_api == "rekognition":
                    # Use AWS Rekognition (RECOMMENDED - reliable, free tier, part of AWS)
                    aws_key = config.AWS_ACCESS_KEY_ID
                    aws_secret = config.AWS_SECRET_ACCESS_KEY
                    aws_region = config.AWS_REGION
                    if aws_key and aws_secret:
                        is_valid, error_message = validate_clothing_image_rekognition(temp_filepath, aws_key, aws_secret, aws_region)
                    else:
                        current_app.logger.warning("AWS credentials not configured. Skipping image validation.")
                elif validation_api == "api4ai":
                    # Use api4ai Fashion API
                    api4ai_key = config.API4AI_API_KEY
                    if api4ai_key:
                        is_valid, error_message = validate_clothing_image_api4ai(temp_filepath, api4ai_key)
                    else:
                        current_app.logger.warning("api4ai API key not configured. Skipping image validation.")
                else:
                    # Use Imagga API (fallback)
                    imagga_key = config.IMAGGA_API_KEY
                    imagga_secret = config.IMAGGA_API_SECRET
                    if imagga_key and imagga_secret:
                        is_valid, error_message = validate_clothing_image(temp_filepath, imagga_key, imagga_secret)
                    else:
                        # If API credentials are not configured, log a warning but allow upload
                        current_app.logger.warning("Imagga API credentials not configured. Skipping image validation.")
                
                if not is_valid:
                    # Clean up temp file
                    try:
                        if temp_filepath and os.path.exists(temp_filepath):
                            os.remove(temp_filepath)
                    except:
                        pass
                    return render_template("edit_listing.html", 
                                         username=username,
                                         listing=listing,
                                         error=error_message or "Image validation failed. Please upload an image of a clothing item.")
                
                # Upload to S3 or save to filesystem
                if use_s3:
                    # Upload to S3 - read from temp file to avoid file handle issues
                    try:
                        with open(temp_filepath, 'rb') as temp_file:
                            success, s3_key, upload_error = upload_image_to_s3(temp_file)
                        
                        if success:
                            image_filename = s3_key
                            current_app.logger.info(f"Successfully uploaded image to S3: {s3_key}")
                            
                            # Delete old image from S3 if it exists
                            if listing.images and len(listing.images) > 0:
                                old_image_key = listing.images[0]
                                # Check if old image is from S3 (not a filesystem path)
                                if not old_image_key.startswith('/') and 'uploads' not in old_image_key:
                                    try:
                                        delete_image_from_s3(old_image_key)
                                    except:
                                        pass
                        else:
                            # Upload failed, fallback to filesystem
                            current_app.logger.warning(f"S3 upload failed: {upload_error}. Falling back to filesystem.")
                            use_s3 = False
                    except Exception as e:
                        current_app.logger.error(f"Error uploading to S3: {e}. Falling back to filesystem.")
                        use_s3 = False
                
                if not use_s3:
                    # Fallback to filesystem storage - copy from temp file
                    upload_folder = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    # Generate unique filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    original_filename = image_file.filename if hasattr(image_file, 'filename') else 'image'
                    filename = secure_filename(original_filename)
                    filename = f"{timestamp}_{filename}"
                    filepath = os.path.join(upload_folder, filename)
                    
                    # Copy from temp file to upload folder
                    import shutil
                    shutil.copy2(temp_filepath, filepath)
                    
                    # Delete old image from filesystem if it exists
                    if listing.images and len(listing.images) > 0:
                        old_filename = listing.images[0]
                        old_filepath = os.path.join(upload_folder, old_filename)
                        try:
                            if os.path.exists(old_filepath):
                                os.remove(old_filepath)
                        except:
                            pass
                    
                    image_filename = filename
                
                # Clean up temp file
                try:
                    if temp_filepath and os.path.exists(temp_filepath):
                        os.remove(temp_filepath)
                except:
                    pass
                    
            except Exception as e:
                # Clean up temp file on error
                try:
                    if temp_filepath and os.path.exists(temp_filepath):
                        os.remove(temp_filepath)
                except:
                    pass
                current_app.logger.error(f"Error processing image: {e}")
                return render_template("edit_listing.html",
                                     username=username,
                                     listing=listing,
                                     error=f"Error processing image: {str(e)}")
        
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
    
    # Get image URL for display
    image_url = None
    if listing.images and len(listing.images) > 0:
        image_url = get_image_url(listing.images[0])
    
    # Get unread message count
    unread_count = 0
    if db is not None:
        unread_count = get_unread_count(db, username)
    
    return render_template("edit_listing.html", username=username, listing=listing, unread_count=unread_count, image_url=image_url)

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
        # Delete image from S3 or filesystem
        if listing.images and len(listing.images) > 0:
            image_key = listing.images[0]
            
            # Check if S3 is configured
            try:
                is_configured, _ = check_s3_configured()
                if is_configured:
                    # Check if image is from S3 (not a filesystem path)
                    if not image_key.startswith('/') and 'uploads' not in image_key:
                        # Delete from S3
                        delete_success, delete_error = delete_image_from_s3(image_key)
                        if not delete_success:
                            current_app.logger.warning(f"Failed to delete image from S3: {delete_error}")
                    else:
                        # Delete from filesystem
                        upload_folder = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
                        filepath = os.path.join(upload_folder, image_key)
                        try:
                            if os.path.exists(filepath):
                                os.remove(filepath)
                        except Exception as e:
                            current_app.logger.warning(f"Failed to delete image from filesystem: {e}")
                else:
                    # S3 not configured, delete from filesystem
                    upload_folder = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
                    filepath = os.path.join(upload_folder, image_key)
                    try:
                        if os.path.exists(filepath):
                            os.remove(filepath)
                    except Exception as e:
                        current_app.logger.warning(f"Failed to delete image from filesystem: {e}")
            except Exception as e:
                current_app.logger.warning(f"Error checking S3 configuration during delete: {e}")
                # Try filesystem delete as fallback
                upload_folder = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
                filepath = os.path.join(upload_folder, image_key)
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except:
                    pass
        
        success = delete_listing(db, listing_id)
        if success:
            flash("Listing deleted successfully!", "success")
            return redirect(url_for("main.my_listings"))
        else:
            flash("Failed to delete listing. Please try again.", "error")
            return redirect(url_for("main.view_listing", listing_id=listing_id))
    except Exception as e:
        current_app.logger.error(f"ERROR deleting listing: {e}")
        flash(f"Error deleting listing: {str(e)}", "error")
        return redirect(url_for("main.view_listing", listing_id=listing_id))

# Diagnostic: check if location API key works (open in browser: /api/location-status)
@main.route("/api/location-status")
def api_location_status():
    from config import get_config
    key = (get_config().GOOGLE_PLACES_API_KEY or "").strip()
    out = {"key_set": bool(key), "google_status": None, "error_message": None}
    if not key:
        return jsonify(out)
    try:
        r = requests.get(
            "https://maps.googleapis.com/maps/api/place/autocomplete/json",
            params={"input": "toronto", "components": "country:ca", "key": key},
            timeout=8,
        )
        data = r.json()
        out["google_status"] = data.get("status")
        if data.get("status") != "OK" and data.get("status") != "ZERO_RESULTS":
            out["error_message"] = data.get("error_message", "No error_message from Google")
    except Exception as e:
        out["google_status"] = "ERROR"
        out["error_message"] = str(e)
    return jsonify(out)

# Proxy for Google Places Autocomplete (avoids CORS; Canada only)
@main.route("/api/place-autocomplete")
def api_place_autocomplete():
    from config import get_config
    key = (get_config().GOOGLE_PLACES_API_KEY or "").strip()
    if not key:
        return jsonify({"status": "REQUEST_DENIED", "predictions": [], "error_message": "API key not set"})
    q = request.args.get("input", "").strip()
    if not q:
        return jsonify({"status": "ZERO_RESULTS", "predictions": []})
    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {"input": q, "components": "country:ca", "key": key}
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            current_app.logger.warning(f"Place autocomplete Google status={data.get('status')} error_message={data.get('error_message')}")
        return jsonify(data)
    except Exception as e:
        current_app.logger.warning(f"Place autocomplete proxy error: {e}")
        return jsonify({"status": "ERROR", "predictions": [], "error_message": str(e)})

# Proxy for Google Geocoding reverse (avoids CORS; Canada only)
@main.route("/api/geocode/reverse")
def api_geocode_reverse():
    from config import get_config
    key = (get_config().GOOGLE_PLACES_API_KEY or "").strip()
    if not key:
        return jsonify({"status": "REQUEST_DENIED", "results": [], "error_message": "API key not set"})
    latlng = request.args.get("latlng", "").strip()
    if not latlng:
        return jsonify({"status": "ZERO_RESULTS", "results": []})
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"latlng": latlng, "key": key, "components": "country:CA"}
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            current_app.logger.warning(f"Geocode reverse Google status={data.get('status')} error_message={data.get('error_message')}")
        return jsonify(data)
    except Exception as e:
        current_app.logger.warning(f"Geocode reverse proxy error: {e}")
        return jsonify({"status": "ERROR", "results": [], "error_message": str(e)})

# --- Admin: view flagged posts (moderation) ---
@main.route("/admin/flagged")
def admin_flagged():
    require_admin()
    db = getattr(current_app, "mongo_db", None)
    if not db:
        flash("Database not available.", "error")
        return redirect(url_for("main.home"))
    # Show open flags first, then resolved
    flagged = get_all_flagged_listings(db)
    open_items = [x for x in flagged if x["flag"].status == "open"]
    resolved_items = [x for x in flagged if x["flag"].status != "open"]
    username = session.get("username")
    return render_template(
        "admin/flagged.html",
        username=username,
        open_items=open_items,
        resolved_items=resolved_items,
    )


@main.route("/admin/flag/<flag_id>/resolve", methods=["POST"])
def admin_resolve_flag(flag_id):
    require_admin()
    db = getattr(current_app, "mongo_db", None)
    if not db:
        flash("Database not available.", "error")
        return redirect(url_for("main.admin_flagged"))
    status = request.form.get("status", "resolved")  # "resolved" or "dismissed"
    if status not in ("resolved", "dismissed"):
        status = "resolved"
    if resolve_flag(db, flag_id, status):
        flash("Flag marked as " + status + ".", "success")
    else:
        flash("Could not update flag.", "error")
    return redirect(url_for("main.admin_flagged"))


# Favicon (serve header logo to avoid 404)
@main.route("/favicon.ico")
def favicon():
    folder = os.path.join(current_app.root_path, "static", "images")
    return send_from_directory(folder, "headerlogo.png", mimetype="image/png")

# Serve uploaded images
@main.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(os.path.join(current_app.root_path, 'static', 'img', 'uploads'), filename)

# Admin route to delete all listings except the latest one
@main.route("/admin/delete-old-listings", methods=["GET", "POST"])
def delete_old_listings():
    username = session.get("username")
    
    # Require authentication
    if not username:
        flash("Please log in to access admin functions.", "error")
        return redirect(url_for("main.login"))
    
    db = getattr(current_app, "mongo_db", None)
    if db is None:
        flash("Database connection not available.", "error")
        return redirect(url_for("main.home"))
    
    collection = db["listings"]
    
    if request.method == "POST":
        confirm = request.form.get("confirm")
        if confirm != "DELETE":
            flash("Deletion cancelled. Type 'DELETE' to confirm.", "warning")
            return redirect(url_for("main.delete_old_listings"))
        
        # Get all listings sorted by created_at (newest first)
        all_listings = list(collection.find({}).sort("created_at", -1))
        
        if len(all_listings) <= 1:
            flash("No listings to delete. Only one or zero listings found.", "info")
            return redirect(url_for("main.home"))
        
        # Keep the latest one
        latest_listing = all_listings[0]
        listings_to_delete = all_listings[1:]
        
        # Delete all except the latest
        deleted_count = 0
        for listing in listings_to_delete:
            try:
                result = collection.delete_one({'_id': listing.get('_id')})
                if result.deleted_count > 0:
                    deleted_count += 1
            except Exception as e:
                current_app.logger.error(f"Error deleting listing {listing.get('_id')}: {e}")
        
        flash(f"Successfully deleted {deleted_count} listing(s). Kept: {latest_listing.get('title')}", "success")
        return redirect(url_for("main.home"))
    
    # GET request - show confirmation page
    all_listings = list(collection.find({}).sort("created_at", -1))
    
    if len(all_listings) == 0:
        flash("No listings found.", "info")
        return redirect(url_for("main.home"))
    
    if len(all_listings) == 1:
        flash("Only one listing found. Nothing to delete.", "info")
        return redirect(url_for("main.home"))
    
    latest_listing = all_listings[0]
    listings_to_delete = all_listings[1:]
    
    return render_template("delete_old_listings.html",
                         username=username,
                         latest_listing=latest_listing,
                         listings_to_delete=listings_to_delete,
                         total_count=len(all_listings))
