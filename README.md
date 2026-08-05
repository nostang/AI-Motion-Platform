# 🏸 AI Motion Platform

> AI-powered badminton footwork assessment platform built with FastAPI, MediaPipe Pose, and JavaScript.

An end-to-end AI motion analysis platform that detects badminton footwork from video, evaluates movement quality through a rule-based coach engine, and delivers an interactive web report through REST APIs.

---

# Demo

## Home

Upload a badminton video and start AI analysis.

> *(Insert Home Screenshot Here)*

---

## REST API

Interactive Swagger documentation powered by FastAPI.

> *(Insert Swagger Screenshot Here)*

---

## Motion Report

AI Coach evaluation with radar visualization.

> *(Insert Report Screenshot Here)*

---

# Features

- 🎥 Upload badminton videos
- 🤖 AI Pose Estimation (MediaPipe Pose)
- 🏸 Footwork Motion Detection
- 📐 Rule-based Assessment Engine
- 👨‍🏫 Coach Evaluation Engine
- 📊 Interactive Motion Report
- 📡 RESTful API
- 📁 JSON Report Export

---

## Architecture

![](docs/images/architecture.png)

---

# API

## Create Motion Assessment

```http
POST /api/v1/motion-assessments
```

Upload a badminton video and create a new assessment.

Returns:

```json
{
  "assessment_id": "...",
  "status": "uploaded"
}
```

---

## Get Assessment Status

```http
GET /api/v1/motion-assessments/{assessment_id}
```

Returns

- uploaded
- processing
- completed
- failed

---

## Get Motion Report

```http
GET /api/v1/motion-assessments/{assessment_id}/report
```

Returns

- Motion Summary
- Coach Evaluation
- Skill Scores
- Radar Chart
- Training Suggestions

---

# Tech Stack

| Category | Technology |
|----------|------------|
| Backend | FastAPI |
| AI Vision | MediaPipe Pose |
| Computer Vision | OpenCV |
| Frontend | HTML / CSS / JavaScript |
| Chart | Chart.js |
| Data | JSON |
| Version Control | Git / GitHub |

---

# Project Structure

```text
AI-Motion-Platform
│
├── frontend/
│   ├── index.html
│   ├── report.html
│   ├── css/
│   ├── js/
│   └── assets/
│
├── src/
│
├── tests/
│
├── docs/
│
├── models/
│
├── api_main.py
├── main.py
├── requirements.txt
└── README.md
```

---

# Quick Start

Clone

```bash
git clone https://github.com/nostang/AI-Motion-Platform.git
```

Install

```bash
pip install -r requirements.txt
```

Run Backend

```bash
uvicorn api_main:app --reload
```

Run Frontend

```bash
cd frontend
python -m http.server 8080
```

Open

```
http://127.0.0.1:8080
```

---

# Current Version

**v1.0 MVP**

Implemented

- REST API
- Motion Pipeline
- Footwork Assessment
- Coach Engine
- Interactive Report
- Swagger API
- Web Frontend

---

# Future Roadmap

- Body Stability Score
- Recovery Speed Score
- Split Step Detection
- Extra Steps Detection
- Coach Similarity
- Multi-player Analysis
- Cloud Deployment
- Authentication
- History Dashboard

---

# License

MIT License

---

# Author

Developed by **Yu-Yin Tang**

AI Motion Platform is an experimental project exploring AI-assisted badminton motion analysis using computer vision and modern web technologies.