from apex import HTMLResponse

async def handler(request):
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>File-Routed Page</title>
        <link rel="stylesheet" href="/static/style.css">
    </head>
    <body>
        <h1>File-Based Route: /</h1>
        <p>This page is served from <code>pages/index.py</code></p>
        <p>Apex automatically maps files to routes.</p>
        <p><a href="/about" style="color:#0070f3;">Go to /about (also file-routed)</a></p>
    </body>
    </html>
    """)
