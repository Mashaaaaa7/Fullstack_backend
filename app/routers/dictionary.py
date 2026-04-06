from fastapi import APIRouter, Query, HTTPException
from app.services.dictionary_service import get_word_definition

router = APIRouter()

@router.get("")
async def dictionary(word: str = Query(..., description="English word to define")):
    try:
        return await get_word_definition(word)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))