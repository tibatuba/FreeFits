# Google Places API Setup (Optional - for better postal code support)

The app now supports **Google Places Autocomplete API** which provides excellent postal code recognition. If you don't set up an API key, it will automatically fall back to Nominatim (OpenStreetMap).

## Why use Google Places API?
- ✅ **Excellent postal code recognition** - Works with postal codes worldwide
- ✅ **Better autocomplete** - More accurate suggestions
- ✅ **Free tier available** - $200 free credit per month (usually enough for development)

## How to Get a Free Google Places API Key:

1. **Go to Google Cloud Console:**
   - Visit: https://console.cloud.google.com/

2. **Create a New Project (or select existing):**
   - Click "Select a project" → "New Project"
   - Name it "FreeFits" (or any name)
   - Click "Create"

3. **Enable Places API:**
   - Go to "APIs & Services" → "Library"
   - Search for "Places API"
   - Click "Places API" → "Enable"

4. **Create API Key:**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "API Key"
   - Copy the API key

5. **Restrict the API Key (Recommended for security):**
   - Click on your new API key
   - Under "API restrictions", select "Restrict key"
   - Choose "Places API" only
   - Under "Application restrictions", you can restrict to HTTP referrers (your domain) for production
   - Click "Save"

6. **Add to your .env file:**
   - Create or edit `.env` file in the project root
   - Add this line:
   ```
   GOOGLE_PLACES_API_KEY=your_api_key_here
   ```
   - Replace `your_api_key_here` with your actual API key

7. **Restart the app:**
   - The app will automatically use Google Places API if the key is found
   - If no key is provided, it falls back to Nominatim

## Free Tier Limits:
- $200 free credit per month
- Places Autocomplete: $2.83 per 1000 requests
- That's about **70,000 requests per month free**
- More than enough for development and small projects!

## Notes:
- The API key is stored in `.env` which is already in `.gitignore` (won't be committed)
- Never commit your API key to Git
- For production, always restrict your API key to specific domains/IPs


