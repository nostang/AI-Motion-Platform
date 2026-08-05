# AI Motion API v0.9.0 — Local Run

## Install API dependencies

```bash
pip install -r requirements.txt
```

## Start API

```bash
uvicorn api_main:app --reload --host 127.0.0.1 --port 8000
```

OpenAPI UI:

```text
http://127.0.0.1:8000/docs
```

## Create an assessment

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/motion-assessments" \
  -F "assessment_type=footwork" \
  -F "video=@videos/footwork.mov"
```

Use the returned `assessment_id` to query status and report.
