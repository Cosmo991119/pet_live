"""
工具层：定义 agent 能调用的工具
每个工具有：name, description, 参数 schema, 执行函数
"""
import datetime
import json
import os

NOTES_FILE = "notes.json"

# 工具描述（告诉 LLM 有哪些工具可用）
TOOLS = [
    {
        "name": "search_knowledge",
        "description": "搜索内部知识库，回答关于公司政策、技术文档等问题。当用户问到内部资料相关问题时优先使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词或问题"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_weather",
        "description": "Get the current weather information for a location",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "The location for which to get weather information"}
            },
            "required": ["location"]
        }
    },
    {
        "name": "search_web",
        "description": "Search the internet for information on a topic",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "calculate",
        "description": "Perform a mathematical calculation",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression, e.g. '2 + 2'"}
            },
            "required": ["expression"]
        }
    },
    {
        "name": "get_current_time",
        "description": "Get the current date and time",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "save_note",
        "description": "Save a note to persistent storage. Use this to remember important information across conversations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key":   {"type": "string", "description": "Note name, e.g. 'user_name'"},
                "value": {"type": "string", "description": "Content to save"}
            },
            "required": ["key", "value"]
        }
    },
    {
        "name": "read_note",
        "description": "Read a previously saved note. Use this to recall information from past conversations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Note name to retrieve"}
            },
            "required": ["key"]
        }
    }
]

# Mock 搜索结果数据库
MOCK_SEARCH_DB = {
    "python": "Python is a high-level language known for simplicity. 10-100x slower than C++ in CPU-bound tasks, but faster to develop.",
    "c++": "C++ is a compiled language with manual memory management. Fastest for performance-critical applications.",
    "agent": "AI agents use LLMs to autonomously decide actions, call tools, and complete multi-step tasks.",
    "llm": "Large Language Models like GPT/Claude are trained on vast text data to understand and generate language.",
}

def get_weather(location: str) -> str:
    location_lower = location.lower()
    import requests
    r = requests.get(f"https://wttr.in/{location_lower}?format=3")
    r.encoding = 'utf-8'
    return r.text

def search_web(query: str) -> str:
    """Mock 搜索：在预设数据库里找关键词"""
    query_lower = query.lower()
    for keyword, result in MOCK_SEARCH_DB.items():
        if keyword in query_lower:
            return f"[Search result for '{query}']: {result}"
    return f"[Search result for '{query}']: No specific results found. General info: This is a complex topic with many perspectives."

def calculate(expression: str) -> str:
    """真实计算（不需要 mock）"""
    try:
        result = eval(expression)  # 简化版，生产环境用 safer parser
        return f"Result: {expression} = {result}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_current_time() -> str:
    now = datetime.datetime.now()
    return f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}"

def save_note(key: str, value: str) -> str:
    notes = {}
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "r") as f:
            notes = json.load(f)
    notes[key] = value
    with open(NOTES_FILE, "w") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)
    return f"Saved note '{key}': {value}"

def read_note(key: str) -> str:
    if not os.path.exists(NOTES_FILE):
        return f"No notes found. Nothing saved yet."
    with open(NOTES_FILE, "r") as f:
        notes = json.load(f)
    if key not in notes:
        return f"Note '{key}' not found."
    return f"Note '{key}': {notes[key]}"

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """统一工具执行入口"""
    if tool_name == "search_knowledge":
        from rag import search_knowledge
        return search_knowledge(tool_input["query"])
    elif tool_name == "search_web":
        return search_web(tool_input["query"])
    elif tool_name == "calculate":
        return calculate(tool_input["expression"])
    elif tool_name == "get_current_time":
        return get_current_time()
    elif tool_name == "save_note":
        return save_note(tool_input["key"], tool_input["value"])
    elif tool_name == "read_note":
        return read_note(tool_input["key"])
    elif tool_name == "get_weather":
        return get_weather(tool_input["location"])
    else:
        return f"Error: Unknown tool '{tool_name}'"
