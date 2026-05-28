from apex import HTMLResponse

async def handler(request):
    slug = request.path_params.get("slug", "unknown")
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Blog: {{slug}}</title>
        <link rel="stylesheet" href="/static/style.css">
    </head>
    <body>
        <h1>Blog Post: {slug}</h1>
        <p>This is a dynamic route!</p>
        <p>The slug "<strong>{slug}</strong>" was extracted from the URL path.</p>
        <p>Try changing it: <a href="/blog/anything-you-want">/blog/anything-you-want</a></p>
        <p><a href="/" style="color:#0070f3;">&larr; Back home</a></p>
    </body>
    </html>
    """)
