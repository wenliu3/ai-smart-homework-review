"""测试假件（假模型/假 Agent）：保证测试不依赖外部 AI API。"""
from langchain_core.messages import AIMessageChunk


class FakeAgent:
    """模拟 langgraph agent.stream 的输出协议：迭代 (AIMessageChunk, metadata)。

    chunks: 依次产出的文本分片；error: 非空时 stream 开始即抛出。
    received_input / received_context: 记录调用入参，供断言上下文注入。
    """

    def __init__(self, chunks=(), error=None):
        self.chunks = list(chunks)
        self.error = error
        self.received_input = None
        self.received_context = None

    def stream(self, input, context=None, stream_mode=None):
        self.received_input = input
        self.received_context = context
        if self.error:
            raise self.error
        for text in self.chunks:
            yield (AIMessageChunk(content=text), {})
