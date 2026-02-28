FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app /app/app

# Expose ports for FastAPI (8000) and Streamlit (8501)
EXPOSE 8000
EXPOSE 8501

# Script to run both services
RUN echo '#!/bin/bash\nuvicorn app.api.main:app --host 0.0.1 --port 8000 & \nstreamlit run app/dashboard/dashboard.py --server.port 8501 --server.address 0.0.0.0' > run.sh
RUN chmod +x run.sh

CMD ["./run.sh"]
