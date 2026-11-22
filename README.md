# Smart Reader Backend

This is the FastAPI backend for the Smart Reader application, designed to be deployed on HuggingFace Spaces.

## Requirements
- Python 3.11+
- Groq API Key

## Environment Variables
Create a `.env` file in the root directory and add the following variables:
```
GROQ_API_KEY=your_groq_api_key_here
CORS_ORIGINS=https://YOUR_PROJECT.vercel.app,http://localhost:5173
DATABASE_URL=sqlite:///./smart_reader.db
```

## Local Development
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the application:
   ```bash
   uvicorn app.main:app --reload --port 8001
   ```

## Docker
Build and run the Docker container locally:
```bash
docker build -t smart-reader-backend .
docker run -p 7860:7860 --env-file .env smart-reader-backend
```

## HuggingFace Deployment
This repository is configured for HuggingFace Spaces using Docker.
- The `Dockerfile` exposes port `7860`.
- Set your `GROQ_API_KEY` and `CORS_ORIGINS` in the HuggingFace Spaces secrets configuration.
