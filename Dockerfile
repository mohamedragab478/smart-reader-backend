FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies using uv
RUN uv pip install --system --no-cache -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 7860 for HuggingFace Spaces
EXPOSE 7860

# Run Uvicorn on 0.0.0.0:7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
