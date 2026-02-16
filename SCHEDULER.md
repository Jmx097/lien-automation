# Daily Automation Setup

## Option 1: Cloud Scheduler (Recommended)

Run this to schedule daily runs at 9 AM:

```bash
gcloud scheduler jobs create http lien-extraction-daily \
  --schedule="0 9 * * *" \
  --uri="https://us-central1-lien-extraction-sa.cloudfunctions.net/lien-extraction" \
  --http-method=POST \
  --message-body='{"sites":["12","10","20"],"max_results":50}' \
  --time-zone="America/New_York" \
  --project=lien-extraction-sa
```

## Option 2: Cloud Console

1. Go to: https://console.cloud.google.com/cloudscheduler?project=lien-extraction-sa
2. Click **Create Job**
3. **Name**: `lien-extraction-daily`
4. **Frequency**: `0 9 * * *` (9 AM daily)
5. **Timezone**: America/New_York
6. **Target**: HTTP
7. **URL**: `https://us-central1-lien-extraction-sa.cloudfunctions.net/lien-extraction`
8. **Method**: POST
9. **Body**: `{"sites":["12","10","20"],"max_results":50}`
10. Click **Create**

## Schedule Options

| Schedule | Description |
|----------|-------------|
| `0 9 * * *` | 9 AM daily |
| `0 9 * * 1` | 9 AM Mondays only |
| `0 */6 * * *` | Every 6 hours |
| `0 9,17 * * *` | 9 AM and 5 PM daily |

## Verify Job

```bash
gcloud scheduler jobs list --project=lien-extraction-sa
```

## Test Job Manually

```bash
gcloud scheduler jobs run lien-extraction-daily --project=lien-extraction-sa
```

## View Logs

```bash
gcloud logging read "resource.type=cloud_function" --limit=50 --project=lien-extraction-sa
```
