from flask import Blueprint, render_template, request, redirect, url_for, session
from app.models import get_latest_listings, search_listings

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
