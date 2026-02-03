# S3 Integration Example

This document shows how to integrate S3 storage into your existing routes.

## Step 1: Update config.py

Add S3 configuration to your `Config` class:

```python
class Config:
    # ... existing config ...
    
    # AWS S3 Configuration
    AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME", "")
    AWS_S3_REGION = os.getenv("AWS_S3_REGION", "")  # Optional, defaults to AWS_REGION
```

## Step 2: Update .env file

Add to your `.env`:

```env
AWS_S3_BUCKET_NAME=freefits-images
AWS_S3_REGION=us-east-1
```

## Step 3: Modify routes.py - Create Listing

Replace the image saving section in `create_listing_page()`:

### OLD CODE (Filesystem):
```python
# Save image file
upload_folder = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
os.makedirs(upload_folder, exist_ok=True)

# Generate unique filename
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = secure_filename(image_file.filename)
filename = f"{timestamp}_{filename}"
filepath = os.path.join(upload_folder, filename)
image_file.save(filepath)

# Validate that the image contains clothing items
# ... validation code ...

# After validation, if valid:
image_filename = filename
```

### NEW CODE (S3):
```python
from app.s3_storage import upload_image_to_s3, get_s3_image_url, delete_image_from_s3, check_s3_configured

# Check if S3 is configured (optional fallback to filesystem)
use_s3 = True
s3_error = None
if use_s3:
    is_configured, s3_error = check_s3_configured()
    if not is_configured:
        current_app.logger.warning(f"S3 not configured, falling back to filesystem: {s3_error}")
        use_s3 = False

if use_s3:
    # Upload directly to S3 (no temporary file needed)
    # Reset file pointer for validation
    image_file.seek(0)
    
    # Validate image first (using temporary file or in-memory)
    # For Rekognition, we need a file path, so save temporarily
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
        image_file.save(temp_file.name)
        temp_filepath = temp_file.name
    
    # Validate that the image contains clothing items
    # ... validation code using temp_filepath ...
    
    if is_valid:
        # Upload to S3
        image_file.seek(0)  # Reset for upload
        success, s3_key, upload_error = upload_image_to_s3(image_file)
        
        if success:
            image_filename = s3_key  # Store S3 key in database
            # Clean up temp file
            try:
                os.remove(temp_filepath)
            except:
                pass
        else:
            # Upload failed
            return render_template("create_listing.html",
                                 username=username,
                                 error=f"Failed to upload image: {upload_error}")
    else:
        # Validation failed, clean up temp file
        try:
            os.remove(temp_filepath)
        except:
            pass
        return render_template("create_listing.html",
                             username=username,
                             error=error_message or "Image validation failed.")
else:
    # Fallback to filesystem storage (existing code)
    upload_folder = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
    # ... existing filesystem code ...
```

## Step 4: Update Image Display in Templates

In your listing templates, update image URLs:

### OLD (Filesystem):
```html
<img src="{{ url_for('main.uploaded_file', filename=listing.image_filename) }}" alt="{{ listing.title }}">
```

### NEW (S3):
```python
# In your route/view function, add:
from app.s3_storage import get_s3_image_url, check_s3_configured

# Check if image is from S3 (starts with certain pattern) or filesystem
is_s3_image = not listing.image_filename.startswith('/') and 'uploads' not in listing.image_filename

if is_s3_image:
    image_url = get_s3_image_url(listing.image_filename, signed=False)
else:
    # Fallback to filesystem
    image_url = url_for('main.uploaded_file', filename=listing.image_filename)
```

Then in template:
```html
<img src="{{ image_url }}" alt="{{ listing.title }}">
```

## Step 5: Update Delete Route

When deleting a listing, also delete from S3:

```python
@main.route("/listing/<listing_id>/delete", methods=["POST"])
def delete_listing_route(listing_id):
    # ... existing code ...
    
    # Delete image from S3 if it's an S3 image
    if listing.get('image_filename'):
        from app.s3_storage import delete_image_from_s3, check_s3_configured
        
        is_configured, _ = check_s3_configured()
        if is_configured:
            # Check if it's an S3 key (not a filesystem path)
            image_key = listing['image_filename']
            if not image_key.startswith('/') and 'uploads' not in image_key:
                delete_image_from_s3(image_key)
        else:
            # Delete from filesystem
            upload_folder = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
            filepath = os.path.join(upload_folder, image_key)
            if os.path.exists(filepath):
                os.remove(filepath)
    
    # ... rest of delete code ...
```

## Step 6: Migration Script (Optional)

To migrate existing filesystem images to S3:

```python
# migrate_to_s3.py
import os
from app.s3_storage import upload_image_to_s3, get_s3_image_url
from app.models import get_all_listings  # You'll need to create this

def migrate_images():
    upload_folder = os.path.join('app', 'static', 'img', 'uploads')
    
    # Get all listings with images
    listings = get_all_listings()  # Implement this function
    
    for listing in listings:
        if listing.get('image_filename'):
            old_filename = listing['image_filename']
            old_path = os.path.join(upload_folder, old_filename)
            
            if os.path.exists(old_path):
                # Upload to S3
                with open(old_path, 'rb') as f:
                    success, s3_key, error = upload_image_to_s3(f, filename=old_filename)
                    
                    if success:
                        # Update listing in database
                        update_listing_image_key(listing['_id'], s3_key)
                        print(f"Migrated: {old_filename} -> {s3_key}")
                    else:
                        print(f"Failed to migrate {old_filename}: {error}")
```

## Benefits After Migration

1. **No disk space limits** - Store unlimited images
2. **Automatic backups** - S3 has 99.999999999% durability
3. **Faster delivery** - Can add CloudFront CDN later
4. **Better security** - IAM policies, encryption
5. **Cost-effective** - ~$0.10/month for typical usage

## Testing

1. Test upload with S3 configured
2. Test fallback to filesystem if S3 not configured
3. Test image display (both S3 and filesystem URLs)
4. Test deletion (both S3 and filesystem)

## Rollback Plan

If you need to rollback:
1. Keep filesystem code as fallback
2. Set `AWS_S3_BUCKET_NAME` to empty string
3. System will automatically use filesystem storage

