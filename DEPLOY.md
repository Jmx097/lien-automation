# Quick Deploy Instructions

## Prerequisites
- gcloud CLI installed and authenticated
- Service account key saved as `service-account-key.json`

## Step 1: Save the service account key
Save the JSON you gave me to a file named `service-account-key.json` in the repo root.

## Step 2: Deploy
```bash
# From the repo root directory:
./deploy.sh
```

Or run the gcloud command directly:
```bash
gcloud config set project lien-extraction-sa

gcloud functions deploy lien-extraction \
    --runtime python311 \
    --trigger-http \
    --entry-point main \
    --memory 1GiB \
    --timeout 300s \
    --region us-central1 \
    --set-env-vars SHEETS_ID=1qpstqj-kQje69cFPb-txNV48hpicd-N_4bA1mbD1854 \
    --set-env-vars GOOGLE_SERVICE_ACCOUNT_JSON="$(cat service-account-key.json)"
```

## Step 3: Test
```bash
curl -X POST https://us-central1-lien-extraction-sa.cloudfunctions.net/lien-extraction \
  -H "Content-Type: application/json" \
  -d '{"sites":["12"],"max_results":2}'
```

## Step 4: Share the Sheet
Make sure the Google Sheet is shared with:
`lien-extraction-prod@lien-extraction-sa.iam.gserviceaccount.com`

(Give it Editor access)

## Troubleshooting

If deployment fails, check:
1. Sheet is shared with the service account email
2. Service account has Cloud Functions Developer role
3. Billing is enabled on the project
