"""FastAPI HTTP wrapper exposing the same tools as the stdio MCP server."""
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from gestnova_accounting.server import build_server


class CallRequest(BaseModel):
    name: str
    arguments: dict


app = FastAPI(title="gestnova-accounting-mcp HTTP")
_server = build_server()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/tools")
async def list_tools():
    tools = await _server.list_tools()
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in tools
    ]


@app.post("/call")
async def call_tool(req: CallRequest):
    try:
        result = await _server.call_tool(req.name, req.arguments)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


def main():
    port = int(os.getenv("PORT", "8014"))
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
