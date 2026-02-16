# Google Location API – Implementation Steps & Cost Estimate

## Overview

FreeFits now uses **Google Places API** (autocomplete) and **Google Geocoding API** (reverse geocode and server-side geocoding), restricted to **Canada only**, replacing Geocoder.ca and Nominatim (OpenStreetMap).

---

## Implementation Steps

### 1. Enable APIs in Google Cloud

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Select your project (or create one).
3. **Enable these APIs:**
   - **Places API** (for autocomplete and place details).
   - **Geocoding API** (for reverse geocode and server-side address → coordinates).
4. **Credentials:** Create an API key (or use existing `GOOGLE_PLACES_API_KEY`).
5. **Restrict the key (recommended):**
   - **Application restrictions:** Use **None** or **IP addresses** (your server’s public IP). Do **not** use “HTTP referrers” only: the app calls Google from the **server** (proxy), not the browser, so referrer restriction causes `REQUEST_DENIED`.
   - **API restrictions:** Restrict to “Places API” and “Geocoding API” only.

### 2. Environment variable

Ensure your app has the key set:

```env
GOOGLE_PLACES_API_KEY=your_google_api_key_here
```

The same key is used for Places and Geocoding. No separate key is required.

### 3. Code changes (already done in this repo)

- **Backend:** `app/geocoding.py` uses Google Geocoding API with `components=country:CA` so all server-side location → lat/lon is Canada-only.
- **Frontend:**
  - **home.html:** Location search uses Google Place Autocomplete with `components=country:ca`. “Use current location” uses Google Geocoding (reverse) with Canada restriction.
  - **create_listing.html**, **edit_listing.html**, and **register.html:** Location field uses the same Google Place Autocomplete (Canada only).
- **Removed:** All use of Geocoder.ca and Nominatim (OpenStreetMap) for location search and geocoding.

### 4. Troubleshooting (location API “not working”)

Open **https://free-fits.com/api/location-status** in your browser. You’ll see JSON:

- **`key_set: false`** → Add `GOOGLE_PLACES_API_KEY` to `/home/ubuntu/FreeFits/.env` on the server and restart the app (`sudo systemctl restart freefits`).
- **`google_status: "REQUEST_DENIED"`** and an `error_message` → Usually the API key is restricted to “HTTP referrers” only. The app calls Google from the **server**, so set **Application restrictions** to **None** or **IP addresses** (your server’s Elastic IP) in Google Cloud Console → APIs & Services → Credentials → your key.
- **`google_status: "OK"`** → API is working; if the UI still fails, check the browser Network tab for the `/api/place-autocomplete` request and its response.

### 5. Testing

1. **Home page:** Type in the location box → only Canadian suggestions. Click “Use current location” (in Canada) → address resolves to a Canadian format.
2. **Create/Edit listing:** Location autocomplete shows only Canadian addresses/places.
3. **Search:** Submit search with a chosen location and distance → results and distance filter should match backend geocoding (Google, Canada-only).

### 6. Optional: Restrict key to Canada only

In Google Cloud Console, you can further lock down the key to only be valid for requests that restrict to Canada (e.g. component restriction). The code already sends `components=country:ca` (or `country:CA`) on all relevant requests.

---

## Cost Estimate

Google Maps Platform gives a **$200 monthly credit** (as of 2024–2025) that applies to these APIs. Prices below are USD per 1,000 requests after the free tier.

| SKU | Free tier (per month) | Cost per 1,000 (after free) |
|-----|------------------------|-----------------------------|
| **Autocomplete (Places API New)** | 10,000 | $2.83 |
| **Place Details Essentials** | 10,000 | $5.00 |
| **Geocoding** | 10,000 | $5.00 |

### Typical usage (example)

- **Autocomplete:** User types in location → ~5–15 requests per search session. Assume **~10 requests per user per month** for location search + create/edit listing.
- **Place Details:** One request when user selects a suggestion (optional; can be skipped if you only need the suggestion text). Assume **~2 requests per user per month** (create/edit listing).
- **Geocoding:** “Use current location” (reverse) + server-side geocoding for search and listing location. Assume **~3 requests per user per month**.

Rough **per user per month:**  
~10 autocomplete + ~2 place details + ~3 geocoding ≈ **15 billable events**.

### Monthly cost examples (after $200 credit)

- **~1,300 users** (each doing the above): ~19,500 requests total. First 10k of each SKU free → remaining billable usage is still well under $200 → **~$0**.
- **~5,000 users:** ~75,000 autocomplete, ~10,000 place details, ~15,000 geocoding. After free tiers: e.g. 65k autocomplete × ($2.83/1000) ≈ $184; place details and geocoding within free tier or small amount → **roughly $0–50** depending on mix.
- **~20,000+ heavy users:** Could exceed $200 credit; monitor in [Google Cloud Billing](https://console.cloud.google.com/billing).

### Recommendations

1. **Set budget alerts** in Google Cloud (e.g. $50, $100) so you get notified before overspend.
2. **Use session tokens** for Autocomplete (already considered in “Places API New” session pricing): first 12 autocomplete requests in a session + 1 Place Details count as a session; extra autocomplete requests in that session are not charged. The implementation can use one session per “location search” or “create listing” flow to reduce cost.
3. **Optional:** Skip Place Details when you only need the suggestion text (e.g. for search) to save the $5/1000 Place Details calls; use the autocomplete suggestion description as the stored location string where acceptable.

---

## Summary

- **APIs:** Places API + Geocoding API, both restricted to Canada in code.
- **Config:** One key in `GOOGLE_PLACES_API_KEY`.
- **Cost:** $200/month credit usually covers small-to-medium traffic; beyond that, order of **$2.83–5.00 per 1,000** requests depending on SKU. Set billing alerts and optionally skip Place Details where not needed.
