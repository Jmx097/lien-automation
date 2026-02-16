#!/bin/bash
# Create Cloud Scheduler job for daily lien extraction
# Run this after Cloud Run deployment is complete

PROJECT_ID="lien-extraction-sa"
REGION="us-central1"
SERVICE_NAME="lien-extraction"
SCHEDULE="0 9 * * *"  # 9 AM ET daily
TIMEZONE="America/New_York"

echo "Creating Cloud Scheduler job for lien extraction..."
echo "Project: $PROJECT_ID"
echo "Schedule: $SCHEDULE (9 AM ET)"
echo ""

# Get the Cloud Run service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --project $PROJECT_ID \
  --format 'value(status.url)' 2>/dev/null)

if [ -z "$SERVICE_URL" ]; then
  echo "❌ Cloud Run service not found. Is it deployed?"
  echo "Check: https://github.com/Jmx097/lien-automation/actions"
  exit 1
fi

echo "✅ Found Cloud Run URL: $SERVICE_URL"
echo ""

# Create or update the scheduler job
gcloud scheduler jobs create http lien-extraction-daily \
  --schedule="$SCHEDULE" \
  --uri="$SERVICE_URL" \
  --http-method=POST \
  --message-body='{"sites":["12","10","20"],"max_results":50}' \
  --headers="Content-Type=application/json" \
  --time-zone="$TIMEZONE" \
  --project=$PROJECT_ID \
  --location=$REGION \
  --description="Daily lien extraction from sheriff sites" \
  2>/dev/null || \
gcloud scheduler jobs update http lien-extraction-daily \
  --schedule="$SCHEDULE" \
  --uri="$SERVICE_URL" \
  --http-method=POST \
  --message-body='{"sites":["12","10","20"],"max_results":50}' \
  --headers="Content-Type=application/json" \
  --time-zone="$TIMEZONE" \
  --project=$PROJECT_ID \
  --location=$REGION \
  --description="Daily lien extraction from sheriff sites"

if [ $? -eq 0 ]; then
  echo ""
  echo "✅ Cloud Scheduler job created/updated successfully!"
  echo ""
  echo "Job Details:"
  echo "  Name: lien-extraction-daily"
  echo "  Schedule: 9:00 AM ET daily"
  echo "  URL: $SERVICE_URL"
  echo "  Sites: 12, 10, 20 (max 50 results each)"
  echo ""
  echo "To test manually:"
  echo "  curl -X POST $SERVICE_URL \\"
  echo "    -H 'Content-Type: application/json' \\"
  echo "    -d '{\"sites\":[\"12\"],\"max_results\":10}'"
  echo ""
  echo "To view job status:"
  echo "  gcloud scheduler jobs describe lien-extraction-daily --location=$REGION"
else
  echo ""
  echo "❌ Failed to create scheduler job"
  echo "Make sure you have gcloud CLI installed and authenticated:"
  echo "  gcloud auth login"
  echo "  gcloud config set project $PROJECT_ID"
fi
