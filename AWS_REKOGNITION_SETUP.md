# AWS Rekognition Setup (RECOMMENDED - FREE & Reliable!)

**AWS Rekognition** is the best choice for your clothing detection because:
- ✅ **FREE Tier**: 5,000 images/month for first 12 months
- ✅ **Reliable**: Part of AWS infrastructure (same as your Lightsail hosting)
- ✅ **Accurate**: Specifically designed for object detection including apparel
- ✅ **Simple**: No complex API endpoints or authentication issues
- ✅ **Integrated**: Works seamlessly with your AWS setup

## Setup Steps (10 minutes)

### Step 1: Create AWS Account (if you don't have one)

1. Go to: **https://aws.amazon.com/**
2. Click **"Create an AWS Account"** or **"Sign In"**
3. Follow the signup process (requires credit card, but free tier won't charge you)

### Step 2: Create IAM User for Rekognition

1. Log into AWS Console: **https://console.aws.amazon.com/**
2. Search for **"IAM"** in the top search bar
3. Click **"Users"** in the left sidebar
4. Click **"Create user"**
5. Enter username: `freefits-rekognition` (or any name you like)
6. Click **"Next"**
7. Under **"Set permissions"**, select **"Attach policies directly"**
8. Search for and select: **`AmazonRekognitionReadOnlyAccess`**
9. Click **"Next"** → **"Create user"**

### Step 3: Create Access Keys

1. Click on the user you just created
2. Go to **"Security credentials"** tab
3. Scroll down to **"Access keys"** section
4. Click **"Create access key"**
5. Select **"Application running outside AWS"** (or "Local code")
6. Click **"Next"** → **"Create access key"**
7. **IMPORTANT**: Copy both:
   - **Access key ID** (looks like: `AKIAIOSFODNN7EXAMPLE`)
   - **Secret access key** (looks like: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`)
   
   ⚠️ **Save these immediately!** You won't be able to see the secret key again.

### Step 4: Add Credentials to Your .env File

Open your `.env` file in the project root and add:

```env
AWS_ACCESS_KEY_ID=your_access_key_id_here
AWS_SECRET_ACCESS_KEY=your_secret_access_key_here
AWS_REGION=us-east-1
IMAGE_VALIDATION_API=rekognition
```

**Example:**
```env
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1
IMAGE_VALIDATION_API=rekognition
```

**Note:** You can use any AWS region (us-east-1, us-west-2, eu-west-1, etc.). `us-east-1` is usually the cheapest.

### Step 5: Install boto3 Library

Run this command in your terminal:

```bash
pip install boto3
```

Or if using virtual environment:

```bash
venv\Scripts\pip.exe install boto3
```

### Step 6: Restart Your Flask App

The app will now use AWS Rekognition for image validation!

## How It Works

1. User uploads an image
2. Image is sent to AWS Rekognition `DetectLabels` API
3. API analyzes the image and returns detected objects/labels
4. If clothing items detected (shirt, pants, dress, etc.) → **ACCEPT** ✅
5. If non-clothing detected (house, car, furniture) → **REJECT** ❌
6. If no clothing found → **REJECT** ❌

## Free Tier Limits

- **5,000 images per month** for first 12 months
- After free tier: ~$1.00 per 1,000 images
- Perfect for development and small-scale production

## Troubleshooting

**"boto3 library not installed"**
- Run: `pip install boto3`

**"AWS credentials not configured"**
- Make sure you added `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` to your `.env` file
- Restart your Flask app after adding credentials

**"InvalidAccessKeyId" or "SignatureDoesNotMatch"**
- Your AWS credentials are incorrect
- Double-check you copied both keys correctly (no extra spaces)
- Make sure you created the access keys for the IAM user

**"AccessDenied"**
- Your IAM user doesn't have Rekognition permissions
- Go back to IAM → Users → Your user → Permissions
- Make sure `AmazonRekognitionReadOnlyAccess` is attached

**"Region not found"**
- Check your `AWS_REGION` in `.env` file
- Common regions: `us-east-1`, `us-west-2`, `eu-west-1`

## Cost Management

- Free tier covers 5,000 images/month for 12 months
- After that: ~$1.00 per 1,000 images
- Monitor usage in AWS Console → Rekognition → Usage metrics
- Set up billing alerts in AWS Billing Dashboard

## Security Best Practices

1. **Never commit `.env` file** to Git (already in `.gitignore`)
2. **Use IAM user with minimal permissions** (ReadOnlyAccess is enough)
3. **Rotate access keys** periodically (every 90 days recommended)
4. **Use AWS Secrets Manager** in production (for now, `.env` is fine for development)

## Testing

Once set up, try uploading:
- ✅ **Clothing items** (shirt, pants, dress) → Should be accepted
- ❌ **Non-clothing** (house, car, table) → Should be rejected

That's it! AWS Rekognition is much more reliable than third-party APIs. 🎉

