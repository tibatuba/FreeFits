# FreeFits – Flask UI Prototype (Inception Release: Part IV)

This repository contains a **UI-only** Flask prototype that showcases the **main page** and **navigation** across the key functional areas of FreeFits:
- Browse Listings (home)
- Listing Details
- Messages & Conversation thread
- User Profile

> **Note:** This is a mock UI. No database or backend logic is required at this stage. Data is hard-coded in-memory as per the Inception Release requirements.

## Running locally

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

# Run
python app.py
# or
# flask --app app.py run
```

Open http://127.0.0.1:5000 in your browser.

## What to demo
- Use the navbar to navigate between **Browse Listings**, **Messages**, and **Profile**.
- On **Browse Listings**, try the search and filters (basic in-memory filtering).
- Click a card to open **Listing Details** and then **Contact Seller** to jump to Messages.
- In **Messages**, open a **Conversation** to view the mock thread UI.
- **Profile** shows user's listings with disabled Edit/Delete buttons as placeholders.

## Folder structure
```
FreeFits-Flask-UI/
  app.py
  requirements.txt
  templates/
  static/
```

## Aligns with Inception Release – Part IV
- Start-up screen + navigation (navbar) ✅
- UI screens for multiple functional areas ✅
- Mock data only (no business logic) ✅
- Demonstrates navigation between screens ✅
