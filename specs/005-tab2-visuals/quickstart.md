# Quickstart: Tab 2 Visuals

**Phase 1 Output** | **Date**: 2025-12-23

This document provides setup instructions and test scenarios for the Tab 2 Visuals feature.

---

## Prerequisites

### Backend

```bash
cd backend

# Install Pillow (if not already installed)
pip install Pillow

# Verify MongoDB is running
mongosh --eval "db.runCommand({ ping: 1 })"

# Start backend
uvicorn src.api.main:app --reload
```

### Frontend

```bash
cd frontend

# Install dependencies (if needed)
npm install

# Start frontend
npm run dev
```

---

## Dev Environment Setup

### 1. Create a Test Project

```bash
# Create a project via API
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Visual Test Project", "webinarType": "training_tutorial"}'

# Note the project ID from response
export PROJECT_ID="<id_from_response>"
```

### 2. Generate Visual Opportunities (from Tab 3)

To have opportunities to assign, first generate a draft:

1. Open the frontend at `http://localhost:5173`
2. Go to Tab 1, add transcript and outline
3. Go to Tab 3, set Visual Density to "Medium"
4. Click "Generate Draft"
5. Verify opportunities exist in MongoDB:

```bash
mongosh webinar2ebook --eval '
  db.projects.findOne({}, {"visualPlan.opportunities": 1})
'
```

### 3. Prepare Test Images

Create test images for upload testing:

```bash
# Create a simple test image (requires ImageMagick)
convert -size 100x100 xc:blue test_blue.png
convert -size 200x200 xc:red test_red.jpg
convert -size 5000x5000 xc:green test_large.png  # ~75MB, for rejection test

# Or download sample images
curl -o test_photo.jpg https://picsum.photos/800/600
```

---

## Test Scenarios

### TS-1: Upload Single Image

**Steps**:
1. Open Tab 2 in browser
2. Drag `test_blue.png` onto the upload dropzone
3. Wait for upload to complete

**Expected**:
- Thumbnail appears in library grid
- Card shows filename, dimensions
- Caption defaults to "test_blue"

**Verify in MongoDB**:
```bash
mongosh webinar2ebook --eval '
  const p = db.projects.find().sort({updatedAt: -1}).limit(1).next();
  print("Assets:", p.visualPlan?.assets?.length || 0);
  printjson(p.visualPlan?.assets?.[0]);
'
```

---

### TS-2: Upload Multiple Images

**Steps**:
1. Select multiple images (up to 10)
2. Drop on upload zone

**Expected**:
- All images upload
- All thumbnails appear
- Each has unique ID and caption

---

### TS-3: Upload Rejection - Wrong Type

**Steps**:
1. Try to upload a PDF or text file

**Expected**:
- Toast: "Unsupported file type"
- File not added to library

---

### TS-4: Upload Rejection - Too Large

**Steps**:
1. Try to upload file > 10MB

**Expected**:
- Toast: "File too large"
- File not added to library

---

### TS-5: Assign Asset to Opportunity

**Prerequisites**: Have at least one opportunity and one asset

**Steps**:
1. In Opportunities section, click "Assign" on an opportunity
2. Modal shows library assets
3. Click an asset to select
4. Confirm assignment

**Expected**:
- Opportunity card shows assigned thumbnail
- Status changes from "Unassigned" to asset thumbnail

**Verify in MongoDB**:
```bash
mongosh webinar2ebook --eval '
  const p = db.projects.find().sort({updatedAt: -1}).limit(1).next();
  print("Assignments:", p.visualPlan?.assignments?.length || 0);
  printjson(p.visualPlan?.assignments);
'
```

---

### TS-6: Skip Opportunity

**Steps**:
1. Click "Skip" on an opportunity

**Expected**:
- Opportunity shows "Skipped" state
- Assignment record created with `status: "skipped"`

---

### TS-7: Delete Asset

**Steps**:
1. Click delete on an asset card
2. Confirm deletion

**Expected**:
- Asset removed from library
- Any assignments to that asset become unassigned
- GridFS bytes deleted

**Verify GridFS cleanup**:
```bash
mongosh webinar2ebook --eval '
  db.fs.files.find({}).toArray()
'
# Should not contain the deleted asset ID
```

---

### TS-8: Persistence (Refresh)

**Steps**:
1. Upload an asset
2. Assign it to an opportunity
3. Refresh the browser

**Expected**:
- Asset still visible in library
- Assignment still shows on opportunity

---

### TS-9: Serve Endpoint (API)

**Test thumbnail serving**:
```bash
# Get thumbnail
curl -o thumb.png \
  "http://localhost:8000/api/projects/${PROJECT_ID}/visuals/assets/${ASSET_ID}/content?size=thumb"

# Get full size
curl -o full.png \
  "http://localhost:8000/api/projects/${PROJECT_ID}/visuals/assets/${ASSET_ID}/content?size=full"

# Verify images
file thumb.png full.png
```

---

### TS-10: Project Isolation (Security)

**Steps**:
1. Create two projects with assets
2. Try to access Project A's asset via Project B's endpoint

**Expected**:
- 404 Not Found
- Asset not served

```bash
# Should fail with 404
curl -i "http://localhost:8000/api/projects/${PROJECT_B_ID}/visuals/assets/${PROJECT_A_ASSET_ID}/content"
```

---

## Acceptance Scenarios (from spec)

| ID | Scenario | Status |
|----|----------|--------|
| AS-001 | Upload image shows in library | [ ] |
| AS-002 | Assign asset to opportunity | [ ] |
| AS-003 | Skip opportunity | [ ] |
| AS-004 | Delete assigned asset | [ ] |
| AS-005 | No opportunities state | [ ] |
| AS-006 | Regenerate clears assignments | [ ] |
| AS-007 | Upload validation error | [ ] |

---

## Debugging Tips

### Check GridFS Contents

```bash
mongosh webinar2ebook --eval '
  print("Files in GridFS:");
  db.fs.files.find({}, {filename: 1, length: 1, "metadata.asset_id": 1}).forEach(printjson);
'
```

### Check Upload Logs

Backend logs upload events:
```
INFO:     Uploaded asset abc123: test.png (1.2MB) -> thumb generated
```

### Clear Test Data

```bash
mongosh webinar2ebook --eval '
  // Clear all assets from all projects (dev only!)
  db.projects.updateMany({}, {$set: {"visualPlan.assets": [], "visualPlan.assignments": []}});

  // Clear GridFS
  db.fs.files.deleteMany({});
  db.fs.chunks.deleteMany({});
'
```
