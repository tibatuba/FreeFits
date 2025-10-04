from flask import Flask

def create_app():
    app = Flask(__name__)
    app.secret_key = "supersecretkey"  # change this in production

    # Import and register blueprints
    from app.routes import main
    app.register_blueprint(main)
    
    return app

# Create the app instance for flask run command
app = create_app()
