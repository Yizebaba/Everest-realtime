"""MCP client used by the LangGraph worker orchestrator."""
import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


GATEWAY_URL = os.environ.get('ZHUFENJIAN_MCP_GATEWAY', 'http://ai-tools:8080/mcp')


async def _call(tool_name, arguments):
    async with streamablehttp_client(GATEWAY_URL, timeout=360) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            if result.isError:
                raise RuntimeError(result.content[0].text)
            return json.loads(result.content[0].text)


def call(tool_name, arguments=None):
    return asyncio.run(_call(tool_name, arguments or {}))
