from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/about", response_class=HTMLResponse)
async def about():
    html_content = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>О проекте | Карточки из PDF</title>
    <meta name="description" content="Превратите PDF в учебные карточки. Учитесь эффективно.">
    <link rel="canonical" href="http://localhost:3000/about">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Карточки из PDF",
        "url": "http://localhost:3000",
        "description": "Создавайте учебные карточки из PDF-файлов",
        "potentialAction": {
            "@type": "SearchAction",
            "target": "http://localhost:3000/search?q={search_term_string}",
            "query-input": "required name=search_term_string"
        }
    }
    </script>
</head>
<body>
    <h1>О проекте</h1>
    <p>Приложение позволяет загружать PDF-документы и создавать из них учебные карточки.</p>
    <p>Используйте встроенный словарь, чтобы быстро узнавать значения английских слов.</p>
</body>
</html>
    """
    return html_content