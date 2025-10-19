from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# --- Mock Data ---
LISTINGS = [
    {
        "id": 1,
        "title": "Winter Jacket (M)",
        "category": "Clothing",
        "location": "Mississauga",
        "description": "Warm insulated jacket, lightly used. Pick-up only.",
        "owner": "Alice",
        "image": "jacket.png",
    },
    {
        "id": 2,
        "title": "Backpack",
        "category": "Accessories",
        "location": "Oakville",
        "description": "Sturdy backpack with laptop sleeve.",
        "owner": "Ben",
        "image": "backpack.png",
    },
    {
        "id": 3,
        "title": "Running Shoes (9)",
        "category": "Footwear",
        "location": "Brampton",
        "description": "Clean, good condition. Fits size 9.",
        "owner": "Carla",
        "image": "shoes.png",
    },
]

CONVERSATIONS = [
    {
        "id": 101,
        "with": "Alice",
        "listing_id": 1,
        "messages": [
            {"sender": "You", "text": "Hi! Is the jacket still available?"},
            {"sender": "Alice", "text": "Yes, still available!"},
            {"sender": "You", "text": "Great, can we meet at Sheridan?"},
        ],
    },
    {
        "id": 102,
        "with": "Carla",
        "listing_id": 3,
        "messages": [
            {"sender": "You", "text": "Interested in the shoes."},
            {"sender": "Carla", "text": "Sure, when would you like to pick up?"},
        ],
    },
]

CURRENT_USER = {
    "name": "FreeFits User",
    "email": "user@example.com",
    "listings": [1],  # listing ids the user posted
}


# --- Helpers ---
def filter_listings(q=None, category=None, location=None):
    items = LISTINGS
    if q:
        ql = q.lower()
        items = [l for l in items if ql in l["title"].lower() or ql in l["description"].lower()]
    if category:
        items = [l for l in items if l["category"].lower() == category.lower()]
    if location:
        items = [l for l in items if l["location"].lower() == location.lower()]
    return items


# --- Routes ---
@app.route("/")
def home():
    q = request.args.get("q", "").strip() or None
    category = request.args.get("category") or None
    location = request.args.get("location") or None
    items = filter_listings(q=q, category=category, location=location)
    categories = sorted({l["category"] for l in LISTINGS})
    locations = sorted({l["location"] for l in LISTINGS})
    return render_template("home.html", listings=items, categories=categories, locations=locations, q=q, category=category, location=location)


@app.route("/listing/<int:listing_id>")
def listing_detail(listing_id):
    listing = next((l for l in LISTINGS if l["id"] == listing_id), None)
    if not listing:
        return render_template("404.html"), 404
    # Find any conversation related to this listing for the current user (mock logic)
    convo = next((c for c in CONVERSATIONS if c["listing_id"] == listing_id), None)
    return render_template("listing_detail.html", listing=listing, convo=convo)


@app.route("/messages")
def messages():
    return render_template("messages.html", conversations=CONVERSATIONS)


@app.route("/messages/<int:convo_id>")
def conversation(convo_id):
    convo = next((c for c in CONVERSATIONS if c["id"] == convo_id), None)
    if not convo:
        return render_template("404.html"), 404
    return render_template("conversation.html", convo=convo)


@app.route("/profile")
def profile():
    my_listings = [l for l in LISTINGS if l["id"] in CURRENT_USER["listings"]]
    return render_template("profile.html", user=CURRENT_USER, my_listings=my_listings, conversations=CONVERSATIONS)


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True)
