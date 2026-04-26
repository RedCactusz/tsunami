#!/bin/bash

echo "=== CHECKING SWE API ENDPOINT ==="
echo ""

# Test health endpoint
echo "1. Testing SWE Health:"
curl -s http://localhost:8000/api/swe/health | jq . || echo "Failed to connect"

echo ""
echo "2. Testing SWE Simulate Endpoint (should show available parameters):"
curl -s http://localhost:8000/api/swe/scenarios | jq .

echo ""
echo "3. Checking if server is running on port 8000:"
lsof -i :8000 | grep LISTEN

echo ""
echo "=== Done ==="
echo "Now run a simulation in the browser and check:"
echo "- Browser Console (F12) for errors"
echo "- Network tab for the API response to /api/swe/simulate"
