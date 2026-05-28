from apex import HTMLResponse

async def handler(request):
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>About (File Route)</title>
        <link rel="stylesheet" href="/static/style.css">
    </head>
    <body>
        <h1>About Page</h1>
        <p>This is served from <code>pages/about.py</code></p>
        <p>File-based routing at work!</p>
        <p><a href="/blog/hello-apex">Check out the blog</a></p>
    </body>
    </html>
    """)
