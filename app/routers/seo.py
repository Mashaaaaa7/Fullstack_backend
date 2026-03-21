from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

router = APIRouter()

@router.get("/sitemap.xml")
async def sitemap():
    base_url = "http://localhost:3000"
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{base_url}/</loc>
    <priority>1.0</priority>
  </url>
  <!-- если будете добавлять другие публичные страницы, добавьте их сюда -->
</urlset>"""
    return Response(content=xml_content, media_type="application/xml")

@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    content = """User-agent: *
Allow: /
Disallow: /login
Disallow: /register
Disallow: /app
Disallow: /profile
Disallow: /admin
Disallow: /forbidden
Sitemap: https://yourdomain.com/sitemap.xml
"""
    return content