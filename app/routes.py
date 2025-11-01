from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.models import get_latest_listings, search_listings, get_listing_by_id, create_listing, get_listings_by_user

main = Blueprint("main", __name__)

# Home route - Marketplace
@main.route("/")
def home():
    username = session.get("username")  # None if not logged in
    
    # Get search parameters
    search_query = request.args.get('search', '')
    location_filter = request.args.get('location', '')
    category_filter = request.args.get('category', '')
    distance_filter = request.args.get('distance', '')
    
    # Get listings based on search/filters
    if search_query or location_filter or category_filter:
        listings = search_listings(
            query=search_query,
            category=category_filter if category_filter else None,
            location=location_filter if location_filter else None
        )
    else:
        listings = get_latest_listings()
    
    return render_template("home.html", 
                         username=username, 
                         listings=listings,
                         search_query=search_query,
                         location_filter=location_filter,
                         category_filter=category_filter,
                         distance_filter=distance_filter)

# Login route
@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # For demo: accept any username/password (you can add real validation later)
        if username and password:
            session["username"] = username  # Save username in session
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
        
        if len(password) < 6:
            return render_template("register.html", error="Password must be at least 6 characters long.")

        # For demo: accept any valid registration (you can add real validation later)
        session["username"] = username  # Save username in session
        return redirect(url_for("main.home"))

    return render_template("register.html")

# View individual listing route
@main.route("/listing/<int:listing_id>")
def view_listing(listing_id):
    username = session.get("username")
    listing = get_listing_by_id(listing_id)
    
    if not listing:
        flash("Listing not found.", "error")
        return redirect(url_for("main.home"))
    
    return render_template("listing_detail.html", listing=listing, username=username)

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
        size = request.form.get("size")
        condition = request.form.get("condition")
        location = request.form.get("location")
        
        # Basic validation
        if not all([title, description, category, size, condition, location]):
            return render_template("create_listing.html", 
                                 username=username,
                                 error="All fields are required.")
        
        # Create the listing
        new_listing = create_listing(
            title=title,
            description=description,
            category=category,
            size=size,
            condition=condition,
            location=location,
            user_id=username
        )
        
        flash("Listing created successfully!", "success")
        return redirect(url_for("main.view_listing", listing_id=new_listing.id))
    
    return render_template("create_listing.html", username=username)

# Contact/Message seller route (requires authentication)
@main.route("/listing/<int:listing_id>/contact", methods=["POST"])
def contact_seller(listing_id):
    username = session.get("username")
    
    # Require authentication to contact seller
    if not username:
        flash("Please log in to contact the seller.", "error")
        return redirect(url_for("main.login"))
    
    listing = get_listing_by_id(listing_id)
    if not listing:
        flash("Listing not found.", "error")
        return redirect(url_for("main.home"))
    
    # For now, just show a message (you can implement actual messaging later)
    flash(f"Message sent to seller for '{listing.title}'! (This is a demo - messaging will be implemented later)", "success")
    return redirect(url_for("main.view_listing", listing_id=listing_id))

# My Listings route (requires authentication)
@main.route("/my-listings")
def my_listings():
    username = session.get("username")
    
    # Require authentication to view my listings
    if not username:
        flash("Please log in to view your listings.", "error")
        return redirect(url_for("main.login"))
    
    # Get all listings created by this user
    user_listings = get_listings_by_user(username)
    
    return render_template("my_listings.html", username=username, listings=user_listings)
