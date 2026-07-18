# Vision Module

Handles all AI-powered visual verification for Guardian. Uses Gemini Vision to extract license plates from photos and detect structural vehicle damage.

---

## What's Built

- **License plate extraction** from a photo via Gemini OCR
- **Manual plate entry fallback** (pure string match, no AI)
- **Structural damage detection** from 1–5 crash scene photos
- **Unified incident pipeline** — runs plate check first, then damage check in one request

## What's NOT Implemented Yet

- DB lookup of registered plate by QR token / `incident_token` — currently the caller passes `registered_plate` directly
- Owner crash endpoint (`POST /vision/app/analyze`) with g-force + GPS context
- Rate limiting on vision endpoints
- Multi-vehicle plate matching (one owner, multiple registered vehicles)

---

## APIs

### 1. `POST /vision/verify-incident` ← Main endpoint
Runs the full pipeline in one shot. Plate check gates damage check.

**Input** (`multipart/form-data`)

| Field | Type | Required | Description |
|---|---|---|---|
| `registered_plate` | string | ✅ | Plate from QR scan |
| `damage_images` | file(s) | ✅ | 1–5 crash scene photos (JPEG/PNG/WEBP) |
| `plate_image` | file | either/or | Photo of the license plate for OCR |
| `manual_plate` | string | either/or | Manually typed plate (fallback) |

> `plate_image` or `manual_plate` must be provided. If both, `plate_image` takes precedence.

**Output**
```json
{
  "overall_verified": true,
  "plate_result": {
    "plate_match": true,
    "plate_extracted": "JH10CNN0029",
    "plate_registered": "JH10CNN0029",
    "plate_visible": true,
    "confidence": 0.95,
    "fallback_used": false,
    "mismatch_reason": null
  },
  "damage_result": {
    "verified": true,
    "confidence": 0.98,
    "damage_confirmed": true,
    "damage_description": "...",
    "analysis_notes": "...",
    "image_count_analyzed": 1,
    "threshold_used": 0.8
  }
}
```
> `damage_result` is `null` if plate match fails — damage scan is skipped entirely.

---

### 2. `POST /vision/plate/verify`
Standalone plate verification using a photo.

**Input** (`multipart/form-data`): `plate_image` (file), `registered_plate` (string)

**Output**: `PlateVerificationResult` (see schema above, without `damage_result`)

---

### 3. `POST /vision/plate/verify-manual`
Standalone plate verification using manually typed text. No Gemini call.

**Input** (`application/json`): `{ "manual_plate": "JH10CNN0029", "registered_plate": "JH10CNN0029" }`

**Output**: `PlateVerificationResult` with `fallback_used: true`, `confidence: 1.0`

---

### 4. `POST /vision/webapp/analyze`
Standalone damage detection only. No plate check.

**Input** (`multipart/form-data`): `images` — 1 to 5 files (JPEG/PNG/WEBP)

**Output**
```json
{
  "verified": true,
  "confidence": 0.98,
  "damage_confirmed": true,
  "damage_description": "...",
  "analysis_notes": "...",
  "image_count_analyzed": 1,
  "threshold_used": 0.8
}
```

---

## Error Codes

| Code | Meaning |
|---|---|
| `400` | Missing/invalid input (no images, unsupported format, empty plate) |
| `503` | Gemini API key not configured |
| `502` | Gemini API call failed |

---

## Normalization
Both image-extracted and manually entered plates are normalized before comparison:
- Uppercased
- All spaces, hyphens, and dots stripped

So `JH 10-CNN 0029` == `JH10CNN0029`.
