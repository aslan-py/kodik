"""
MCP-сервер для управления адаптивным сбором данных (BP-1 Adaptive).

Реализует Model Context Protocol (MCP) поверх JSON-RPC 2.0 через stdio.
Позволяет ИИ-агентам (Claude, GPT и др.) управлять сбором данных:

- ``initialize`` — рукопожатие протокола.
- ``tools/list`` — список доступных инструментов.
- ``tools/call`` — вызов инструмента.
- ``resources/list`` — список ресурсов.

Инструменты:
- ``classify_source`` — классифицировать источник.
- ``run_adaptive_parse`` — выполнить адаптивный парсинг.
- ``get_adapter`` — получить адаптер из кэша.
- ``clear_adapter`` — очистить адаптер.
- ``list_strategies`` — список стратегий обхода.

Сервер не зависит от внешнего пакета ``mcp`` и работает на stdlib.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections.abc import Awaitable, Callable
from typing import Any

from ..core.cache import UnifiedCache
from ..processing.parser import AdaptiveParser
from ..schemas import MCPTool, StrategyType
from ..strategies.classifier import SourceClassifier
from ..strategies.orchestrator import AgenticOrchestrator

logger = logging.getLogger(__name__)

# Версия протокола MCP.
MCP_PROTOCOL_VERSION = '2024-11-05'
SERVER_NAME = 'bp1-adaptive'
SERVER_VERSION = '1.0.0'


class MCPServer:
    """
    MCP-сервер для управления адаптивным сбором данных.

    Читает JSON-RPC-запросы из stdin и пишет ответы в stdout.
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        cache: UnifiedCache | None = None,
    ):
        self._logger = logger or logging.getLogger(__name__)
        self._classifier = SourceClassifier()
        self._parser = AdaptiveParser()
        self._orchestrator = AgenticOrchestrator()
        self._cache = cache or UnifiedCache()
        self._tools: dict[str, MCPTool] = {}
        self._register_tools()

    # ========================================================================
    # Регистрация инструментов
    # ========================================================================

    def _register_tools(self) -> None:
        """Регистрирует инструменты MCP-сервера."""
        self._tools['classify_source'] = MCPTool(
            name='classify_source',
            description='Классифицировать источник по URL',
            parameters={
                'type': 'object',
                'properties': {
                    'source_name': {'type': 'string'},
                    'source_url': {'type': 'string'},
                },
                'required': ['source_name', 'source_url'],
            },
        )
        self._tools['run_adaptive_parse'] = MCPTool(
            name='run_adaptive_parse',
            description='Выполнить адаптивный парсинг URL',
            parameters={
                'type': 'object',
                'properties': {
                    'url': {'type': 'string'},
                    'source_name': {'type': 'string'},
                    'competitor': {'type': 'string'},
                    'trigger': {'type': 'string'},
                },
                'required': ['url', 'source_name'],
            },
        )
        self._tools['list_strategies'] = MCPTool(
            name='list_strategies',
            description='Список доступных стратегий обхода',
            parameters={'type': 'object', 'properties': {}},
        )
        self._tools['get_adapter'] = MCPTool(
            name='get_adapter',
            description='Получить адаптер источника из кэша',
            parameters={
                'type': 'object',
                'properties': {'source_name': {'type': 'string'}},
                'required': ['source_name'],
            },
        )
        self._tools['clear_adapter'] = MCPTool(
            name='clear_adapter',
            description='Очистить адаптер источника из кэша',
            parameters={
                'type': 'object',
                'properties': {'source_name': {'type': 'string'}},
                'required': ['source_name'],
            },
        )

    # ========================================================================
    # Обработка запросов
    # ========================================================================

    @staticmethod
    def _text_response(text: str) -> dict[str, Any]:
        """Формирует MCP-ответ с текстовым контентом."""
        return {'content': [{'type': 'text', 'text': text}]}

    async def _handle_tool_call(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Выполняет вызов инструмента."""
        if name == 'classify_source':
            classification = await self._classifier.classify(
                source_name=arguments.get('source_name', ''),
                source_url=arguments.get('source_url', ''),
            )
            return self._text_response(classification.model_dump_json())

        if name == 'run_adaptive_parse':
            result = await self._parser.parse(
                url=arguments['url'],
                source_name=arguments.get('source_name', 'adaptive'),
                competitor=arguments.get('competitor', ''),
                trigger=arguments.get('trigger', ''),
            )
            return self._text_response(result.model_dump_json())

        if name == 'list_strategies':
            strategies = [s.value for s in StrategyType]
            return self._text_response(
                json.dumps({'strategies': strategies}, ensure_ascii=False)
            )

        if name == 'get_adapter':
            adapter = await self._cache.get_adapter(
                arguments.get('source_name', '')
            )
            text = (
                adapter.model_dump_json()
                if adapter
                else json.dumps({'adapter': None})
            )
            return self._text_response(text)

        if name == 'clear_adapter':
            await self._cache.clear_adapter(arguments.get('source_name', ''))
            return self._text_response(json.dumps({'cleared': True}))

        raise ValueError(f'unknown tool: {name}')

    async def _dispatch(
        self,
        message: dict[str, Any],
    ) -> dict[str, Any]:
        """Обрабатывает JSON-RPC-сообщение и возвращает ответ."""
        request_id = message.get('id')
        method = message.get('method')

        try:
            if method == 'initialize':
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'result': {
                        'protocolVersion': MCP_PROTOCOL_VERSION,
                        'capabilities': {
                            'tools': {},
                            'resources': {},
                        },
                        'serverInfo': {
                            'name': SERVER_NAME,
                            'version': SERVER_VERSION,
                        },
                    },
                }

            if method == 'tools/list':
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'result': {
                        'tools': [
                            tool.model_dump() for tool in self._tools.values()
                        ]
                    },
                }

            if method == 'tools/call':
                params = message.get('params', {})
                result = await self._handle_tool_call(
                    params.get('name', ''),
                    params.get('arguments', {}),
                )
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'result': result,
                }

            if method == 'resources/list':
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'result': {'resources': []},
                }

            if method == 'notifications/initialized':
                return {'jsonrpc': '2.0', 'id': request_id, 'result': {}}

            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': -32601,
                    'message': f'method not found: {method}',
                },
            }
        except Exception as e:
            self._logger.error(
                'Ошибка обработки MCP-запроса (метод=%s): %s',
                method,
                e,
            )
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': -32603,
                    'message': str(e),
                },
            }

    # ========================================================================
    # Запуск
    # ========================================================================

    async def serve(
        self,
        stdin: Any = None,
        stdout: Any = None,
    ) -> None:
        """
        Запускает MCP-сервер, читая запросы из stdin.

        Args:
            stdin: поток ввода (по умолчанию sys.stdin).
            stdout: поток вывода (по умолчанию sys.stdout).
        """
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout

        self._logger.info('MCP-сервер запущен: %s', SERVER_NAME)

        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue

            response = await self._dispatch(message)
            if response:
                stdout.write(json.dumps(response) + '\n')
                stdout.flush()


def run_mcp_server() -> None:
    """Точка входа для запуска MCP-сервера из CLI."""
    server = MCPServer()
    asyncio.run(server.serve())


# Тип обработчика инструмента (для совместимости с внешними MCP-клиентами).
ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
