#!/bin/bash
# Deploy lien-extraction Cloud Function
# Run this from your local machine with gcloud CLI installed

PROJECT_ID="lien-extraction-sa"
FUNCTION_NAME="lien-extraction"
REGION="us-central1"  # Change if needed

# Set project
gcloud config set project $PROJECT_ID

# Deploy the function
gcloud functions deploy $FUNCTION_NAME \
    --runtime python311 \
    --trigger-http \
    --entry-point main \
    --memory 1GiB \
    --timeout 300s \
    --region $REGION \
    --set-env-vars SHEETS_ID=1qpstqj-kQje69cFPb-txNV48hpicd-N_4bA1mbD1854 \
    --set-env-vars GOOGLE_SERVICE_ACCOUNT_JSON="$(cat service-account-key.json)"

echo "Deployment complete!"
echo "Test with:"
echo "curl -X POST https://$REGION-$PROJECT_ID.cloudfunctions.net/$FUNCTION_NAME \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"sites\":[\"12\"],\"max_results\":2}'"
