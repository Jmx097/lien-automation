# GitHub Auto-Deploy Setup

Deploy automatically when you push to main.

## Prerequisites

1. Your code is in this GitHub repo
2. You have access to GCP Console

## Step 1: Store Service Account in Secret Manager

```bash
# Run this once in Cloud Shell or with gcloud CLI
gcloud config set project lien-extraction-sa
gcloud secrets create service-account-key --data-file service-account-key.json
```

## Step 2: Add GitHub Secrets

Go to: GitHub repo → Settings → Secrets and variables → Actions → New repository secret

Add these secrets:

| Secret Name | Value |
|-------------|-------|
| `GCP_SA_KEY` | The entire contents of your service-account-key.json file |
| `SHEETS_ID` | `1qpstqj-kQje69cFPb-txNV48hpicd-N_4bA1mbD1854` |

### To get GCP_SA_KEY:

```bash
# On your local machine (PowerShell)
Get-Content service-account-key.json -Raw
```

Copy the entire output (including `{` and `}`) and paste into the GitHub secret.

## Step 3: Share the Sheet

Share your Google Sheet with:
```
lien-extraction-prod@lien-extraction-sa.iam.gserviceaccount.com
```

Give it **Editor** access.

## Step 4: Enable APIs

In GCP Console, enable these APIs:
- Cloud Functions API
- Secret Manager API
- Cloud Build API

## Step 5: Push to Deploy

```bash
git add .
git commit -m "Ready to deploy"
git push origin main
```

GitHub Actions will automatically deploy!

## Check Deployment

- GitHub: Repo → Actions tab → Watch the workflow run
- GCP: Console → Cloud Functions → Check for `lien-extraction` function

## Test the Function

Once deployed:

```bash
curl -X POST https://us-central1-lien-extraction-sa.cloudfunctions.net/lien-extraction \
  -H "Content-Type: application/json" \
  -d '{"sites":["12"],"max_results":2}'
```

## Troubleshooting

**Build fails**: Check the GitHub Actions logs for syntax errors
**Auth fails**: Verify `GCP_SA_KEY` secret is complete and valid JSON
**Sheet write fails**: Make sure sheet is shared with service account email
