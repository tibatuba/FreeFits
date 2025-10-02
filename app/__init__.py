from flask import Flask

app = Flask(__name__)
app.secret_key = "supersecretkey"  # change this in production

# Import and register blueprints
from app.routes import main
app.register_blueprint(main)
