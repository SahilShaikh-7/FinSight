# Quick Test: Verify ai_summary Fix

## Test 1: Verify Code Changes

### Check syntax
```bash
cd backend
python -m py_compile insight_engine.py server.py
# ✅ No output = no syntax errors
```

### Check imports
```bash
python -c "from insight_engine import generate_all_insights, generate_llm_summary; print('✅ Imports OK')"
```

---

## Test 2: Manual API Test

### Prerequisites
1. Backend running: `python -m uvicorn server:app --reload`
2. Have a valid JWT token from logged-in user
3. User must have some expenses in database

### Test with force=true (bypasses cache)
```powershell
# Set your token
$TOKEN = "YOUR_JWT_TOKEN_HERE"

# Call endpoint with force refresh
$response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/insights?force=true" `
  -Headers @{"Authorization" = "Bearer $TOKEN"} `
  -ContentType "application/json"

# Check for ai_summary
$data = $response.Content | ConvertFrom-Json
if ($data.ai_summary -and $data.ai_summary.Length -gt 0) {
    Write-Host "✅ SUCCESS: ai_summary present"
    Write-Host "📝 Summary: $($data.ai_summary.Substring(0, 100))..."
} else {
    Write-Host "❌ FAILED: ai_summary missing or empty"
}

# Check for error flag
if ($data._error) {
    Write-Host "⚠️  Warning: _error flag set to true - check ai_summary for details"
}
```

### Test cache behavior
```powershell
# Call 1: Generate (should generate, not use cache)
Write-Host "Call 1: Generate..."
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/insights?force=true" `
  -Headers @{"Authorization" = "Bearer $TOKEN"} | Out-Null
Write-Host "✅ Check backend logs for: 'Generating insights for'"

# Call 2: Use cache (within 60m)
Write-Host "Call 2: Use cache..."
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/insights" `
  -Headers @{"Authorization" = "Bearer $TOKEN"} | Out-Null
Write-Host "✅ Check backend logs for: 'Returning cached insights'"
```

---

## Test 3: Backend Logs Analysis

### What to look for in logs:

#### ✅ Success indicators
```
INFO: Generating insights for 42 expenses, ₹50000 income
INFO: Successfully generated AI summary (156 chars)
INFO: Insights generation completed successfully
```

#### ⚠️ Warning indicators (still OK, has fallback)
```
WARNING: GEMINI_API_KEY not set — LLM summaries disabled
WARNING: Cache read error, regenerating: ...
```

#### ❌ Error indicators (should be rare)
```
ERROR: AI summary generation timed out (>10s)
EXCEPTION: Error generating insights: TimeoutError
```

### View logs in real-time
```bash
# Terminal 1: Run backend with logs
cd backend
python -m uvicorn server:app --reload --log-level debug

# Terminal 2: Make requests
# Check Terminal 1 for logs
```

---

## Test 4: Verify Response Structure

### Expected JSON structure
```json
{
  "health": {
    "score": 75,
    "savings_rate": 60.5,
    "stability": 85.2,
    "essential_ratio": 55.0,
    "breakdown": {...},
    "total_spend_this_month": 15000
  },
  "trend": {
    "current_month_spend": 15000,
    "previous_month_spend": 12000,
    "change_pct": 25.0,
    "trend": "up"
  },
  "anomalies": [...],
  "behavioral_patterns": [...],
  "category_overspends": [...],
  "savings_opportunities": [...],
  "ai_summary": "Your spending increased 25% this month, primarily in dining and entertainment. Consider reviewing subscription services and meal prep to reduce food costs.",
  "generated_at": "2026-04-24T12:34:56.789123+00:00"
}
```

### What to verify
- ✅ `ai_summary` field EXISTS
- ✅ `ai_summary` is a STRING (not null, not object)
- ✅ `ai_summary` has meaningful content (not error message unless error occurred)
- ✅ If `_error: true` present → check `ai_summary` for error details
- ✅ All other fields present as expected

---

## Test 5: Error Scenario Testing

### Scenario: Remove GEMINI_API_KEY
```bash
# In .env file
# GEMINI_API_KEY=  # Remove or comment out

# Call endpoint
# Expected: ai_summary = "AI insights unavailable (API not configured)"
# No crash, graceful degradation
```

### Scenario: Simulate timeout
```python
# In insight_engine.py, temporarily change timeout to 0.001 seconds
# and call endpoint
# Expected: ai_summary = "AI summary generation timed out (>10s) — please try again"
# Endpoint still returns 200 OK
```

### Scenario: Check cache bypass
```bash
# Call with force=true multiple times rapidly
# All should regenerate, not use cache
# Check logs for "Generating insights for" each time
```

---

## Troubleshooting

### Issue: ai_summary still missing
**Solution:**
1. Verify file was edited: `grep -n "ai_summary" backend/insight_engine.py`
2. Restart backend: `Ctrl+C` then `python -m uvicorn server:app --reload`
3. Check Python syntax: `python -m py_compile backend/insight_engine.py`
4. Check logs for exceptions: Look for `EXCEPTION` in logs

### Issue: ai_summary is empty string
**Solution:**
1. Check if Gemini API key is set: `echo $env:GEMINI_API_KEY` (PowerShell)
2. Verify Gemini quota not exhausted
3. Check logs for timeout errors
4. Try `force=true` to bypass cache

### Issue: Backend won't start
**Solution:**
1. Check syntax: `python -c "import insight_engine"`
2. Install dependencies: `pip install -r requirements.txt`
3. Check for import errors in logs
4. Revert changes and test import individually

---

## Success Criteria

✅ **All of these must be true:**
1. Endpoint returns 200 OK (not 500 error)
2. Response includes `ai_summary` field
3. `ai_summary` is a non-empty string
4. Logs show "Successfully generated AI summary" or graceful error
5. Cache behavior works (force=true regenerates, normal request uses cache)
6. No crashes or silent failures

---

## Next Steps

Once confirmed working:
1. Deploy to staging environment
2. Monitor logs for 24 hours
3. Check frontend to ensure it displays ai_summary
4. Deploy to production with monitoring alert on `_error: true`

---

**Test Document Version:** 1.0  
**Date:** 2026-04-24  
**Status:** Ready for testing
