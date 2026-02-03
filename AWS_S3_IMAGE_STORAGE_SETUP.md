# AWS S3 Image Storage Setup Guide

## Overview
This guide explains how to migrate from filesystem storage to AWS S3 for secure, scalable image storage.

## Why S3 Instead of Filesystem?

### Current Issues (Filesystem Storage):
- ❌ Limited by server disk space
- ❌ No built-in backup/redundancy
- ❌ Harder to scale across multiple servers
- ❌ Security relies on web server configuration
- ❌ No CDN integration
- ❌ Manual backup process

### S3 Benefits:
- ✅ Unlimited storage capacity
- ✅ 99.999999999% durability (automatic backups)
- ✅ Built-in access control (IAM policies)
- ✅ CloudFront CDN integration for fast delivery
- ✅ Automatic versioning and lifecycle management
- ✅ Cost-effective: ~$0.023/GB/month
- ✅ Works seamlessly with AWS Rekognition

## Setup Steps

### 1. Create S3 Bucket

1. Go to AWS Console → S3
2. Click "Create bucket"
3. Configure:
   - **Bucket name**: `freefits-images` (must be globally unique)
   - **Region**: Same as your Lightsail instance (e.g., `us-east-1`)
   - **Block Public Access**: 
     - ✅ Uncheck "Block all public access" (we'll use public-read for images)
     - OR keep it blocked and use signed URLs (more secure)
   - **Bucket Versioning**: Enable (optional, for backup)
   - **Encryption**: Enable (SSE-S3 is fine, free)
   - **Object Ownership**: ACLs disabled (recommended)

4. Click "Create bucket"

### 2. Configure Bucket Policy (Public Read Access)

If you want images publicly accessible (simpler, but less secure):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::freefits-images/*"
        }
    ]
}
```

**OR** Use signed URLs (more secure, recommended):
- Keep bucket private
- Generate temporary signed URLs (valid for 1 hour, 1 day, etc.)
- Better security, slightly more complex

### 3. Update Environment Variables

Add to your `.env` file:

```env
# AWS S3 Configuration
AWS_S3_BUCKET_NAME=freefits-images
AWS_S3_REGION=us-east-1
# Use same credentials as Rekognition
# AWS_ACCESS_KEY_ID=your_key (already set)
# AWS_SECRET_ACCESS_KEY=your_secret (already set)
```

### 4. Install boto3 (Already Installed)

`boto3` is already in `requirements.txt` for Rekognition, so you're good!

### 5. Implementation Options

#### Option A: Direct S3 Upload (Recommended)
- Upload directly from Flask to S3
- No temporary files on server
- Faster, more secure

#### Option B: Hybrid Approach
- Save to filesystem temporarily
- Upload to S3 after validation
- Delete local file
- Good for migration/testing

## Cost Estimate

### Free Tier (First 12 Months):
- 5 GB storage
- 20,000 GET requests
- 2,000 PUT requests

### After Free Tier (Typical Usage):
- **Storage**: $0.023/GB/month
  - 1,000 images × 2MB each = 2GB = **$0.046/month**
- **Requests**: 
  - PUT (uploads): $0.005 per 1,000 = **~$0.01/month** (200 uploads)
  - GET (views): $0.0004 per 1,000 = **~$0.04/month** (10,000 views)
- **Total**: ~**$0.10/month** for 1,000 images

**Very affordable!** Even with 10,000 images, you're looking at ~$1/month.

## Security Best Practices

1. **Use Signed URLs** (instead of public bucket)
   - Images accessible only via temporary URLs
   - Expire after set time (e.g., 1 hour)
   - More secure, prevents direct linking

2. **IAM User with Limited Permissions**
   - Create dedicated IAM user for S3 access
   - Only grant `s3:PutObject` and `s3:GetObject` permissions
   - Don't use root AWS credentials

3. **Enable Encryption**
   - SSE-S3 (server-side encryption)
   - Free, automatic encryption at rest

4. **Bucket Policy Restrictions**
   - Limit uploads to specific file types
   - Set max file size limits
   - Restrict by IP (optional)

## Migration Strategy

1. **Phase 1**: Implement S3 upload alongside filesystem (dual-write)
2. **Phase 2**: Update templates to use S3 URLs
3. **Phase 3**: Migrate existing images to S3 (optional script)
4. **Phase 4**: Remove filesystem storage code

## Alternative Options (If Not Using S3)

### Option 1: Cloudinary (Easiest)
- Free tier: 25GB storage, 25GB bandwidth
- Built-in image optimization/resizing
- Simple API
- **Cost**: Free for small projects, then ~$89/month

### Option 2: DigitalOcean Spaces
- S3-compatible API
- $5/month for 250GB
- Good if you want S3-like but simpler pricing

### Option 3: Keep Filesystem + Backup
- Use current approach
- Add automated backups to S3/Backblaze
- Cheaper but less scalable

## Recommendation

**Use AWS S3** because:
1. You're already using AWS (Lightsail + Rekognition)
2. Consistent ecosystem
3. Very affordable (~$0.10/month for typical usage)
4. Professional, scalable solution
5. Easy integration with existing AWS credentials

