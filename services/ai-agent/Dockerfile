FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (leverages Docker cache for faster rebuilds)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Copy your application code
COPY src/ src/

# Expose the port FastAPI runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]