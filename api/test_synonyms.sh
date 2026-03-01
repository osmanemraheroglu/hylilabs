#!/bin/bash
BASE_URL="http://localhost:8000"

echo "=== 1. LOGIN ==="
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@demo.com", "password": "demo123"}')

echo "$LOGIN_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$LOGIN_RESPONSE"

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo "❌ Login başarısız!"
  exit 1
fi
echo "✅ Token alındı"
echo ""

AUTH="Authorization: Bearer $TOKEN"

echo "=== 2. PENDING COUNT ==="
curl -s -H "$AUTH" "$BASE_URL/api/synonyms/pending/count" | python3 -m json.tool
echo ""

echo "=== 3. PENDING LIST ==="
curl -s -H "$AUTH" "$BASE_URL/api/synonyms/pending?limit=5" | python3 -m json.tool
echo ""

echo "=== 4. KEYWORD SYNONYMS (python) ==="
curl -s -H "$AUTH" "$BASE_URL/api/synonyms?keyword=python" | python3 -m json.tool
echo ""

echo "=== 5. MANUEL SYNONYM EKLE ==="
curl -s -X POST "$BASE_URL/api/synonyms" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "test_keyword", "synonym": "test_synonym", "synonym_type": "english", "auto_approve": false}' | python3 -m json.tool
echo ""

echo "=== 6. PENDING COUNT (artmış olmalı) ==="
curl -s -H "$AUTH" "$BASE_URL/api/synonyms/pending/count" | python3 -m json.tool
echo ""

echo "=== 7. AI GENERATE (python keyword) ==="
curl -s -X POST "$BASE_URL/api/synonyms/generate" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "yazılım geliştirme"}' | python3 -m json.tool
echo ""

echo "=== TEST TAMAMLANDI ==="
