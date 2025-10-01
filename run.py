from app import create_app

# Create the Flask app instance
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)  # remove debug=True in production
