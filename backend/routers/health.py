from fastapi import APIRouter

router = APIRouter()
parent_route = "/health"

@router.get('')
def health():
    return {
        "route": parent_route+"",
        "data" : {
            "health" : "Server is healthy."
        }  
    }