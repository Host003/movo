import json
import asyncio

from app.dsh_runtime.model_gateway.tool_query_scope import scope_knowledge_tool_arguments
from app.dsh_runtime.model_gateway.service import ModelGatewayRequest, ModelGatewayService
from app.dsh_runtime.model_gateway.token import ModelGatewayTokenService
from app.llm.types import LLMResponse, Message, Role


def test_model_query_keeps_exact_filename_from_user_turn() -> None:
    result = scope_knowledge_tool_arguments(
        name="knowledge_search", arguments=json.dumps({"query": "Serving Kit 综合性能提升"}),
        messages=[{"role": "user", "content": "请根据《火山引擎AI 一体机核心介绍v1.0.pdf》回答综合性能提升多少"}],
    )
    assert json.loads(result)["query"] == "《火山引擎AI 一体机核心介绍v1.0.pdf》 Serving Kit 综合性能提升"


def test_script_arguments_are_never_rewritten() -> None:
    raw = '{"code":"print(1)"}'
    assert scope_knowledge_tool_arguments(
        name="run_script", arguments=raw,
        messages=[{"role": "user", "content": "《门店销售数据表.xlsx》"}],
    ) == raw


def test_tool_result_wrapped_as_user_does_not_hide_original_question() -> None:
    result = scope_knowledge_tool_arguments(
        name="knowledge_search", arguments='{"query":"GR0010218"}',
        messages=[
            {"role": "user", "content": "《门店销售数据表.xlsx》里 GR0010218 的店名？"},
            {"role": "user", "content": [{"type": "tool-result", "content": [{"type": "text", "text": "result"}]}]},
        ],
    )
    assert json.loads(result)["query"] == "《门店销售数据表.xlsx》 GR0010218"


def test_stream_rewrites_knowledge_tool_call_before_runtime_receives_it() -> None:
    class Client:
        async def astream(self, _messages, **_kwargs):
            yield LLMResponse(message=Message(role=Role.ASSISTANT, content="", tool_calls=[{
                "index": 0, "id": "search-1", "name": "knowledge_search",
                "arguments": '{"query":"GR0010218 的店名"}',
            }]))

    async def run():
        async def factory(*_args):
            return Client()

        tokens = ModelGatewayTokenService("named-knowledge-regression-secret")
        claims = tokens.verify(tokens.issue(
            tenant_id="tenant", profile_version="profile", model_instance_id="model",
        ))
        request = ModelGatewayRequest(
            profileVersion="profile", modelInstanceId="model", provider="askai-model-gateway",
            model="test", messages=[{"role": "user", "content": "请根据《门店销售数据表.xlsx》回答 GR0010218 的店名"}],
            tools=[{"name": "knowledge_search", "parameters": {"type": "object"}}, {"name": "run_script", "parameters": {"type": "object"}}],
        )
        stream = await ModelGatewayService(factory).stream(request, claims)
        return [event async for event in stream]

    events = asyncio.run(run())
    call = next(event for event in events if event["type"] == "tool-call")
    assert json.loads(call["arguments"])["query"].startswith("《门店销售数据表.xlsx》")
