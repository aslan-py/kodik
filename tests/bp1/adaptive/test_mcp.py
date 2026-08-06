"""Тесты для MCP-сервера (mcp_server.py)."""

import pytest

from src.bp1.adaptive.mcp_server import MCPServer


@pytest.mark.asyncio
async def test_initialize_returns_protocol_info():
    """initialize возвращает информацию о протоколе."""
    server = MCPServer()
    response = await server._dispatch(
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}
    )
    assert response['result']['protocolVersion'] == '2024-11-05'
    assert response['result']['serverInfo']['name'] == 'bp1-adaptive'


@pytest.mark.asyncio
async def test_tools_list_returns_tools():
    """tools/list возвращает список инструментов."""
    server = MCPServer()
    response = await server._dispatch(
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}
    )
    tools = response['result']['tools']
    names = {tool['name'] for tool in tools}
    assert 'classify_source' in names
    assert 'run_adaptive_parse' in names
    assert 'list_strategies' in names


@pytest.mark.asyncio
async def test_tools_call_list_strategies():
    """tools/call list_strategies возвращает список стратегий."""
    server = MCPServer()
    response = await server._dispatch(
        {
            'jsonrpc': '2.0',
            'id': 3,
            'method': 'tools/call',
            'params': {'name': 'list_strategies', 'arguments': {}},
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
        {'jsonrpc': '2.0', 'id': 4, 'method': 'unknown/method'}
    )
    assert response['error']['code'] == -32601


@pytest.mark.asyncio
async def test_unknown_tool_returns_error():
    """Неизвестный инструмент возвращает ошибку."""
    server = MCPServer()
    response = await server._dispatch(
        {
            'jsonrpc': '2.0',
            'id': 5,
            'method': 'tools/call',
            'params': {'name': 'nonexistent', 'arguments': {}},
        }
    )
    assert response['error']['code'] == -32603
