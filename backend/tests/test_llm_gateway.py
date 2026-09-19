import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, __import__("os").path.dirname(__file__) + "/../")

from app import llm_gateway


CFG = llm_gateway.LLMConfig(
    base_url="https://example.test/v1",
    api_key="test-key",
    model_name="test-model",
    temperature=0.8,
    context_window=64000,
)


def sdk_response(content="连接正常"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=None,
    )


def response_dict(content="连接正常"):
    return {"choices": [{"message": {"content": content}}]}


class CompletionTextTests(unittest.TestCase):
    def test_extracts_sdk_response(self):
        self.assertEqual(llm_gateway._extract_completion_text(sdk_response()), "连接正常")

    def test_extracts_dict_response(self):
        self.assertEqual(llm_gateway._extract_completion_text(response_dict()), "连接正常")

    def test_extracts_json_string_response(self):
        response = json.dumps(response_dict("来自字符串响应"))
        self.assertEqual(llm_gateway._extract_completion_text(response), "来自字符串响应")

    def test_accepts_plain_text_response(self):
        self.assertEqual(llm_gateway._extract_completion_text("连接正常"), "连接正常")

    def test_rejects_empty_response(self):
        with self.assertRaisesRegex(ValueError, "空响应"):
            llm_gateway._extract_completion_text(" ")

    def test_rejects_html_response(self):
        with self.assertRaisesRegex(ValueError, "HTML"):
            llm_gateway._extract_completion_text("<!doctype html><html></html>")

    def test_rejects_empty_choices(self):
        with self.assertRaisesRegex(ValueError, "缺少 choices"):
            llm_gateway._extract_completion_text({"choices": []})

    def test_rejects_missing_content(self):
        with self.assertRaisesRegex(ValueError, "文本内容"):
            llm_gateway._extract_completion_text({"choices": [{"message": {}}]})


class ThinkingStripTests(unittest.TestCase):
    def test_strips_complete_think_block(self):
        text = "<think>**Planning detailed chapter scenes**\n\n**Structuring**\n\n</think>\n\n正文第一段"
        self.assertEqual(llm_gateway.strip_thinking(text), "\n\n正文第一段")

    def test_strips_think_with_attributes(self):
        text = '<think model="x">内部思考</think>正文'
        self.assertEqual(llm_gateway.strip_thinking(text), "正文")

    def test_strips_truncated_open_tag(self):
        text = "<think>内部思考没有闭合标签"
        self.assertEqual(llm_gateway.strip_thinking(text), "")

    def test_strips_analysis_and_reasoning_tags(self):
        self.assertEqual(llm_gateway.strip_thinking("<analysis>x</analysis>正文"), "正文")
        self.assertEqual(llm_gateway.strip_thinking("<reasoning>x</reasoning>正文"), "正文")

    def test_leaves_body_intact_when_no_think(self):
        text = "这是正常正文，不含思考标签"
        self.assertEqual(llm_gateway.strip_thinking(text), text)


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_transient_upstream_error(self):
        class TemporaryUpstreamError(Exception):
            status_code = 503

        request = AsyncMock(side_effect=[TemporaryUpstreamError(), "恢复后的响应"])
        with patch.object(llm_gateway.asyncio, "sleep", new=AsyncMock()) as sleep:
            result = await llm_gateway._request_with_retry(request)

        self.assertEqual(result, "恢复后的响应")
        self.assertEqual(request.await_count, 2)
        sleep.assert_awaited_once_with(1)

    async def test_does_not_retry_non_transient_error(self):
        request = AsyncMock(side_effect=ValueError("请求参数错误"))
        with patch.object(llm_gateway.asyncio, "sleep", new=AsyncMock()) as sleep:
            with self.assertRaisesRegex(ValueError, "请求参数错误"):
                await llm_gateway._request_with_retry(request)

        self.assertEqual(request.await_count, 1)
        sleep.assert_not_awaited()

    async def test_connection_handles_string_response(self):
        create = AsyncMock(return_value="连接正常")
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.object(llm_gateway, "build_client", return_value=client):
            result = await llm_gateway.test_connection(CFG)
        self.assertTrue(result["ok"])
        self.assertEqual(result["reply"], "连接正常")
        self.assertGreaterEqual(result["latency_ms"], 0)

    async def test_connection_reports_invalid_response(self):
        create = AsyncMock(return_value={"choices": []})
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.object(llm_gateway, "build_client", return_value=client):
            result = await llm_gateway.test_connection(CFG)
        self.assertFalse(result["ok"])
        self.assertIn("缺少 choices", result["error"])
        self.assertNotIn("str' object has no attribute 'choices'", result["error"])

    async def test_chat_uses_shared_extractor(self):
        create = AsyncMock(return_value=json.dumps(response_dict("普通回复")))
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.object(llm_gateway, "build_client", return_value=client):
            content, usage = await llm_gateway.chat(CFG, [{"role": "user", "content": "hi"}])
        self.assertEqual(content, "普通回复")
        self.assertIsNone(usage)

    async def test_json_chat_uses_shared_extractor(self):
        model_json = '{"title": "测试标题"}'
        create = AsyncMock(return_value=json.dumps(response_dict(model_json)))
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.object(llm_gateway, "build_client", return_value=client):
            result, usage = await llm_gateway.json_chat(
                CFG, [{"role": "user", "content": "return json"}]
            )
        self.assertEqual(result, {"title": "测试标题"})
        self.assertIsNone(usage)

    async def test_stream_chat_accepts_non_streaming_compat_response(self):
        create = AsyncMock(return_value="流式兼容回复")
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.object(llm_gateway, "build_client", return_value=client):
            chunks = [
                text
                async for text in llm_gateway.stream_chat(CFG, [{"role": "user", "content": "hi"}])
            ]
        self.assertEqual(chunks, ["流式兼容回复"])

    async def test_stream_chat_forwards_chunks(self):
        async def stream():
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="第一段"))])
            yield SimpleNamespace(choices=[])
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="第二段"))])

        create = AsyncMock(return_value=stream())
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.object(llm_gateway, "build_client", return_value=client):
            chunks = [
                text
                async for text in llm_gateway.stream_chat(CFG, [{"role": "user", "content": "hi"}])
            ]
        self.assertEqual(chunks, ["第一段", "第二段"])

    async def test_stream_chat_strips_thinking(self):
        async def stream():
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="<think>"))])
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="思考中"))])
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="</think>"))])
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="正文开始"))])

        create = AsyncMock(return_value=stream())
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.object(llm_gateway, "build_client", return_value=client):
            chunks = [
                text
                async for text in llm_gateway.stream_chat(CFG, [{"role": "user", "content": "hi"}])
            ]
        self.assertEqual(chunks, ["正文开始"])

    async def test_stream_chat_drops_unclosed_think(self):
        async def stream():
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="正文前缀<think>"))])
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="思考中，流被截断"))])

        create = AsyncMock(return_value=stream())
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.object(llm_gateway, "build_client", return_value=client):
            chunks = [
                text
                async for text in llm_gateway.stream_chat(CFG, [{"role": "user", "content": "hi"}])
            ]
        self.assertEqual(chunks, ["正文前缀"])


if __name__ == "__main__":
    unittest.main()
