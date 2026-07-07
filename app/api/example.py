from fastapi import APIRouter, Body

from app.workers.example_task import sample_task

router = APIRouter()

@router.post("/test")
async def trigger_test(message: str = Body(..., embed=True)):
    """Dispatch a Celery background task.
    
    Returns immediately after queuing the task.
    """
    sample_task.apply_async(args=(message,), countdown=10)
    return {"status": "task dispatched"}