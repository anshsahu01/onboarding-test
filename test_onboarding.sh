#!/bin/bash
SESSION_ID="6416b300-9b9d-41e8-912c-f9b0174ee9a9"

echo "=== Testing Complete Onboarding Flow ==="
echo ""
echo "1. /start endpoint already created session: $SESSION_ID"
echo ""
echo "2. Submitting answer..."
curl -X POST http://localhost:8001/api/onboarding/answer \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\", \"answer\": \"My name is John\"}" \
  2>/dev/null | python -m json.tool

echo ""
echo "3. Getting session..."
curl http://localhost:8001/api/onboarding/session/$SESSION_ID 2>/dev/null | python -m json.tool
