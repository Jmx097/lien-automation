#!/bin/bash
# Test the lien extraction Cloud Run endpoint

SERVICE_URL=${1:-""}

if [ -z "$SERVICE_URL" ]; then
  echo "Usage: ./test-endpoint.sh <cloud-run-url>"
  echo ""
  echo "Example:"
  echo "  ./test-endpoint.sh https://lien-extraction-abc123-uc.a.run.app"
  echo ""
  echo "Or find your URL with:"
  echo "  gcloud run services list --platform managed"
  exit 1
fi

echo "Testing lien extraction endpoint: $SERVICE_URL"
echo ""

# Test with a single site, limited results
echo "Sending test request (site 12, max 5 results)..."
RESPONSE=$(curl -s -X POST "$SERVICE_URL" \
  -H "Content-Type: application/json" \
  -d '{"sites":["12"],"max_results":5}' \
  -w "\nHTTP_CODE:%{http_code}")

HTTP_CODE=$(echo "$RESPONSE" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed 's/HTTP_CODE:.*//')

echo ""
echo "Response Code: $HTTP_CODE"
echo ""
echo "Response Body:"
echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
echo ""

if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ Test PASSED"
  echo ""
  echo "Summary:"
  echo "$BODY" | jq -r '{success: .success, sites: .sites_processed, records: .total_records_found, written: .total_records_written, sheet: .sheet_url}'
else
  echo "❌ Test FAILED (HTTP $HTTP_CODE)"
fi
