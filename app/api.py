from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid
import json

# Import the database function we wrote earlier
from engine.db import get_db_connection
from engine.redis_queue import push_job_to_queue

# Initialize the FastAPI app
app = FastAPI(title="VortexQueue API")

# 1. Define the Expected Input (The Pydantic Model)
# This tells FastAPI to expect a JSON body with a task_name and a payload dictionary.
class JobRequest(BaseModel):
    task_name: str
    payload: dict

# 2. The Endpoint
@app.post("/api/jobs")
async def create_job(request: JobRequest):
    # Generate a unique ID for this specific job
    job_id = str(uuid.uuid4())
    
    # Connect to PostgreSQL
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    try:
        # Open a cursor to run SQL commands
        with conn.cursor() as cur:
            # Insert the job into our table. 
            # We convert the Python dictionary 'payload' into a JSON string for PostgreSQL.
            cur.execute("""
                INSERT INTO jobs (job_id, task_name, payload, status)
                VALUES (%s, %s, %s, 'PENDING')
            """, (job_id, request.task_name, json.dumps(request.payload)))

        push_job_to_queue(job_id, request.task_name, request.payload)
            
        # Return a success message back to the user/frontend
        return {
            "message": "Job successfully received",
            "job_id": job_id,
            "status": "PENDING"
        }
        
    except Exception as e:
        # If the SQL fails, throw a clean 500 Internal Server Error
        raise HTTPException(status_code=500, detail=f"Failed to save job: {str(e)}")
    finally:
        # ALWAYS close the connection so we don't leak memory
        conn.close()