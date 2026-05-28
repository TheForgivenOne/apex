from apex import JSONResponse

async def handler(request):
    return JSONResponse({
        "message": "Hello from file-based API route!",
        "path": request.path,
        "method": request.method,
    })
