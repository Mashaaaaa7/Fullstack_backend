import httpx
from fastapi import HTTPException

DICTIONARY_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en"

async def get_word_definition(word: str):
    url = f"{DICTIONARY_API_URL}/{word}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Word not found")
            response.raise_for_status()
            data = response.json()
            return normalize_dictionary_data(data)
    except httpx.TimeoutException:
        raise HTTPException(status_code=503, detail="Dictionary API timeout")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Dictionary API error")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

def normalize_dictionary_data(data: list) -> dict:
    if not data:
        return {"word": "", "definitions": []}

    word_data = data[0]
    meanings = word_data.get("meanings", [])
    definitions = []
    for meaning in meanings:
        part_of_speech = meaning.get("partOfSpeech")
        for definition_obj in meaning.get("definitions", [])[:2]:  # не более 2 определений
            definitions.append({
                "partOfSpeech": part_of_speech,
                "definition": definition_obj.get("definition"),
                "example": definition_obj.get("example")
            })
    return {
        "word": word_data.get("word"),
        "phonetic": word_data.get("phonetic"),
        "definitions": definitions
    }