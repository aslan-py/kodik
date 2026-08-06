"""Тесты для MCP-сервера (mcp_server.py)."""

import pytest

from src.bp1.adaptive.integration.mcp_server import MCPServer

from .constants import (
    MCP_ERROR_INTERNAL,
    MCP_ERROR_METHOD_NOT_FOUND,
    MCP_JSONRPC,
    MCP_METHOD_INITIALIZE,
    MCP_METHOD_TOOLS_CALL,
    MCP_METHOD_TOOLS_LIST,
    MCP_PROTOCOL_VERSION,
    MCP_SERVER_NAME,
    MCP_TOOL_CLASSIFY_SOURCE,
    MCP_TOOL_LIST_STRATEGIES,
    MCP_TOOL_RUN_PARSE,
)


@pytest.mark.asyncio
async def test_initialize_returns_protocol_info():
    """initialize возвращает информацию о протоколе."""
    server = MCPServer()
    response = await server._dispatch(
        {'jsonrpc': MCP_JSONRPC, 'id': 1, 'method': MCP_METHOD_INITIALIZE}
    )
    assert response['result']['protocolVersion'] == MCP_PROTOCOL_VERSION
    assert response['result']['serverInfo']['name'] == MCP_SERVER_NAME


@pytest.mark.asyncio
async def test_tools_list_returns_tools():
    """tools/list возвращает список инструментов."""
    server = MCPServer()
    response = await server._dispatch(
        {'jsonrpc': MCP_JSONRPC, 'id': 2, 'method': MCP_METHOD_TOOLS_LIST}
    )
    tools = response['result']['tools']
    names = {tool['name'] for tool in tools}
    assert MCP_TOOL_CLASSIFY_SOURCE in names
    assert MCP_TOOL_RUN_PARSE in names
    assert MCP_TOOL_LIST_STRATEGIES in names


@pytest.mark.asyncio
async def test_tools_call_list_strategies():
    """tools/call list_strategies возвращает список стратегий."""
    server = MCPServer()
    response = await server._dispatch(
        {
            'jsonrpc': MCP_JSONRPC,
            'id': 3,
            'method': MCP_METHOD_TOOLS_CALL,
            'params': {'name': MCP_TOOL_LIST_STRATEGIES, 'arguments': {}},
        }
    )
    text = response['result']['content'][0]['text']
    assert 'FAST' in text
    assert 'STEALTH' in text
    assert 'HITL' in text


@pytest.mark.asyncio
async def test_unknown_method_returns_error():
    """Неизвестный метод возвращает ошибку -32601."""
    server = MCPServer()
    response = await server._dispatch(
        {'jsonrpc': MCP_JSONRPC, 'id': 4, 'method': 'unknown/method'}
    )
    assert response['error']['code'] == MCP_ERROR_METHOD_NOT_FOUND


@pytest.mark.asyncio
async def test_unknown_tool_returns_error():
    """Неизвестный инструмент возвращает ошибку."""
    server = MCPServer()
    response = await server._dispatch(
        {
            'jsonrpc': MCP_JSONRPC,
            'id': 5,
            'method': MCP_METHOD_TOOLS_CALL,
            'params': {'name': 'nonexistent', 'arguments': {}},
        }
    )
    assert response['error']['code'] == MCP_ERROR_INTERNAL
