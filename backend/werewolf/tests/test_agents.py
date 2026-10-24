import json
from unittest.mock import patch

import pytest

from simulation.llm import LLMError
from werewolf.agents import (
    AgentResponse,
    LLMAgent,
    ReplayAgent,
    ScriptedAgent,
    ToolCall,
)

TOOLS = [{"type": "function", "function": {"name": "pass"}}]
MESSAGES = [{"role": "user", "content": "hi"}]


def _body(tool_calls, usage=None):
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls,
                }
            }
        ],
        "usage": usage or {"prompt_tokens": 11, "completion_tokens": 5},
    }


def _tc(id_, name, args):
    return {
        "id": id_,
        "type": "function",
        "function": {"name": name, "arguments": args},
    }


@patch("werewolf.agents.post_chat")
def test_llm_agent_payload(mock_post, settings):
    settings.WEREWOLF_LLM_MODEL = "test/model"
    mock_post.return_value = _body([_tc("a", "pass", "{}")])

    LLMAgent(timeout=7).respond(MESSAGES, TOOLS)

    payload = mock_post.call_args[0][0]
    assert payload["model"] == "test/model"
    assert payload["messages"] == MESSAGES
    assert payload["tools"] == TOOLS
    assert payload["tool_choice"] == "required"
    assert mock_post.call_args.kwargs["timeout"] == 7


@patch("werewolf.agents.post_chat")
def test_llm_agent_explicit_model_overrides_setting(mock_post):
    mock_post.return_value = _body([])
    LLMAgent(model="x/y").respond(MESSAGES, TOOLS)
    assert mock_post.call_args[0][0]["model"] == "x/y"


@patch("werewolf.agents.post_chat")
def test_llm_agent_parses_tool_calls_and_usage(mock_post):
    mock_post.return_value = _body([
        _tc("a", "append_note", '{"text": "x"}'),
        _tc("b", "speak", '{"message": "hello"}'),
    ])

    resp = LLMAgent().respond(MESSAGES, TOOLS)

    assert resp.tool_calls == [
        ToolCall("a", "append_note", {"text": "x"}, '{"text": "x"}'),
        ToolCall("b", "speak", {"message": "hello"}, '{"message": "hello"}'),
    ]
    assert (resp.tokens_in, resp.tokens_out) == (11, 5)
    assert resp.raw["role"] == "assistant"
    assert len(resp.raw["tool_calls"]) == 2


@patch("werewolf.agents.post_chat")
def test_llm_agent_bad_json_arguments_gives_none(mock_post):
    mock_post.return_value = _body([_tc("a", "speak", "{not json")])
    (call,) = LLMAgent().respond(MESSAGES, TOOLS).tool_calls
    assert call.arguments is None
    assert call.raw_arguments == "{not json"


@patch("werewolf.agents.post_chat")
def test_llm_agent_non_object_arguments_gives_none(mock_post):
    mock_post.return_value = _body([_tc("a", "speak", "[1]")])
    (call,) = LLMAgent().respond(MESSAGES, TOOLS).tool_calls
    assert call.arguments is None


@patch("werewolf.agents.post_chat")
def test_llm_agent_no_tool_calls_and_missing_usage(mock_post):
    mock_post.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "chat"}}]
    }
    resp = LLMAgent().respond(MESSAGES, TOOLS)
    assert resp.tool_calls == []
    assert resp.content == "chat"
    assert (resp.tokens_in, resp.tokens_out) == (0, 0)


def test_scripted_agent_iterable_of_steps():
    agent = ScriptedAgent([[("speak", {"message": "a"})], [("pass", {})]])
    r1 = agent.respond(MESSAGES, TOOLS)
    r2 = agent.respond(MESSAGES, TOOLS)
    assert r1.tool_calls[0].name == "speak"
    assert r1.tool_calls[0].arguments == {"message": "a"}
    assert json.loads(r1.tool_calls[0].raw_arguments) == {"message": "a"}
    assert r2.tool_calls[0].name == "pass"
    assert r1.tool_calls[0].id != r2.tool_calls[0].id
    assert (r1.tokens_in, r1.tokens_out) == (0, 0)
    assert r1.raw["tool_calls"][0]["id"] == r1.tool_calls[0].id


def test_scripted_agent_callable():
    seen = []

    def script(messages, tools):
        seen.append((messages, tools))
        return [("pass", {})]

    resp = ScriptedAgent(script).respond(MESSAGES, TOOLS)
    assert resp.tool_calls[0].name == "pass"
    assert seen == [(MESSAGES, TOOLS)]


def test_scripted_agent_exhausted_raises():
    agent = ScriptedAgent([])
    with pytest.raises(RuntimeError):
        agent.respond(MESSAGES, TOOLS)


def test_replay_agent_yields_then_raises_on_errors():
    ok = AgentResponse([], "c", 1, 2, {"role": "assistant"})
    agent = ReplayAgent(iter([ok, LLMError("boom")]))
    assert agent.respond(MESSAGES, TOOLS) is ok
    with pytest.raises(LLMError, match="boom"):
        agent.respond(MESSAGES, TOOLS)
