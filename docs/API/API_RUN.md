# AI Motion API — Local Run Guide

## 1. Activate Environment

```bash
source .venv/bin/activate
```

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## 3. Start Backend

```bash
uvicorn api_main:app --reload --host 127.0.0.1 --port 8000
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## 4. Start Frontend

Open another Terminal:

```bash
cd frontend
python -m http.server 8080
```

Frontend:

```text
http://127.0.0.1:8080
```

## 5. Create an Assessment with curl

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/motion-assessments" \
  -F "assessment_type=footwork" \
  -F "video=@videos/footwork.mov"
```

Use the returned `assessment_id` to query:

```text
GET /api/v1/motion-assessments/{assessment_id}
GET /api/v1/motion-assessments/{assessment_id}/report
```
