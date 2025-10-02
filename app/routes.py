from flask import Blueprint, render_template, request, redirect, url_for, session

main = Blueprint("main", __name__)

# Home route
@main.route("/")
def home():
    username = session.get("username")  # None if not logged in
    return render_template("home.html", username=username)

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

# Register route placeholder
@main.route("/register")
def register():
    return "Registration page coming soon."
