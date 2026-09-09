"""12 种节点执行器实现。

start / end / llm / rag / http / tool / condition / loop / human /
code / variable_assign / template_render。
"""
import time

from app.core.engine.nodes.base import BaseNodeExecutor, NodeRouter
from app.core.engine.state import resolve, resolve_dict


class StartExecutor(BaseNodeExecutor):
    async def run(self, state: dict) -> dict:
        return {"current_node": self.node_id}


class EndExecutor(BaseNodeExecutor):
    async def run(self, state: dict) -> dict:
        return {"current_node": self.node_id, "status": "completed"}


class LLMExecutor(BaseNodeExecutor):
    async def run(self, state: dict) -> dict:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from app.providers.langchain_factory import build_chat_model

        t0 = time.perf_counter()
        llm = await build_chat_model(
            use="qa",
            temperature=self.config.get("temperature", 0.7),
            max_tokens=self.config.get("max_tokens"),
        )
        sys_prompt = resolve(self.config.get("system_prompt", ""), state)
        usr_prompt = resolve(self.config.get("user_prompt", ""), state)
        prompt = ChatPromptTemplate.from_messages([("system", sys_prompt), ("human", usr_prompt)])
        chain = prompt | llm | StrOutputParser()
        out = await chain.ainvoke({})
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        outputs = {**state.get("node_outputs", {}), self.node_id: {"output": out}}
        timings = {**state.get("node_timings", {}), self.node_id: elapsed}
        return {"node_outputs": outputs, "node_timings": timings}


class RAGExecutor(BaseNodeExecutor):
    async def run(self, state: dict) -> dict:
        from app.core.retrieval.hybrid_retriever import HybridRetriever
        from app.core.scenes import get_scene_config

        t0 = time.perf_counter()
        query = resolve(self.config.get("query", ""), state)
        doc_ids = self.config.get("document_ids", [])
        scene = await get_scene_config(self.config.get("scene", "general"))
        retriever = HybridRetriever(
            doc_ids=doc_ids, scene_config=scene,
            top_k=self.config.get("top_k", 5),
            enable_nav=self.config.get("enable_navigation", True),
        )
        docs = await retriever.ainvoke(query)
        answer = ""
        if self.config.get("generate_answer"):
            from langchain_core.output_parsers import StrOutputParser
            from langchain_core.prompts import ChatPromptTemplate
            from app.providers.langchain_factory import build_chat_model
            gen_llm = await build_chat_model(use="qa")
            context = "\n\n".join(d.page_content for d in docs)
            prompt = ChatPromptTemplate.from_messages([
                ("system", "根据以下上下文回答问题。\n\n{context}"),
                ("human", query),
            ])
            answer = await (prompt | gen_llm | StrOutputParser()).ainvoke({"context": context})
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        outputs = {**state.get("node_outputs", {}), self.node_id: {
            "chunks": [d.page_content for d in docs], "answer": answer,
        }}
        timings = {**state.get("node_timings", {}), self.node_id: elapsed}
        return {"node_outputs": outputs, "node_timings": timings}


class HTTPExecutor(BaseNodeExecutor):
    async def run(self, state: dict) -> dict:
        import httpx
        t0 = time.perf_counter()
        cfg = resolve_dict(self.config, state)
        url = cfg.get("url", "")
        method = cfg.get("method", "GET").upper()
        headers = cfg.get("headers", {})
        body = cfg.get("body")
        timeout = cfg.get("timeout", 30)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, url, headers=headers, json=body)
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        ok_ = resp.status_code < 400
        data = resp.json() if ok_ else resp.text
        outputs = {**state.get("node_outputs", {}), self.node_id: {
            "output": data, "status_code": resp.status_code,
        }}
        timings = {**state.get("node_timings", {}), self.node_id: elapsed}
        return {"node_outputs": outputs, "node_timings": timings}


class ToolExecutor(BaseNodeExecutor):
    async def run(self, state: dict) -> dict:
        from app.services.tool_service import execute_tool
        t0 = time.perf_counter()
        tool_id = self.config.get("tool_id", "")
        args = resolve_dict(self.config.get("args", {}), state)
        result = await execute_tool(tool_id, args)
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        outputs = {**state.get("node_outputs", {}), self.node_id: result}
        timings = {**state.get("node_timings", {}), self.node_id: elapsed}
        return {"node_outputs": outputs, "node_timings": timings}


class ConditionExecutor(BaseNodeExecutor):
    async def run(self, state: dict) -> dict:
        conditions = self.config.get("conditions", [])
        for rule in conditions:
            if self._eval(rule, state):
                return {"current_node": self.node_id, "_branch": rule.get("id", "true")}
        return {"current_node": self.node_id, "_branch": self.config.get("default_branch", "else")}

    def _eval(self, rule: dict, state: dict) -> bool:
        left = resolve(str(rule.get("left", "")), state)
        right = str(rule.get("right", ""))
        op = rule.get("operator", "==")
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "contains":
            return right in left
        if op == ">":
            return float(left) > float(right)
        if op == "<":
            return float(left) < float(right)
        return False


class LoopExecutor(BaseNodeExecutor):
    async def run(self, state: dict) -> dict:
        items_key = self.config.get("items", "")
        items = state.get("node_outputs", {}).get(items_key, {}).get("output", [])
        if not isinstance(items, list):
            items = []
        loop_stack = state.get("loop_stack", [])
        if loop_stack and len(loop_stack) < len(items):
            idx = len(loop_stack)
            return {
                "current_node": self.node_id,
                "_loop": {"item": items[idx], "index": idx},
                "loop_stack": loop_stack + [idx],
            }
        return {"current_node": self.node_id, "_loop": {}, "loop_stack": []}


class HumanExecutor(BaseNodeExecutor):
    async def run(self, state: dict) -> dict:
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import select
        from app.db.session import async_session
        from app.models.workflow import WorkflowTodo
        timeout_hours = self.config.get("timeout_hours", 24)
        deadline = datetime.now(timezone.utc) + timedelta(hours=timeout_hours)
        todo = WorkflowTodo(
            execution_id=state["execution_id"],
            workflow_id=state["workflow_id"],
            node_id=self.node_id,
            title=self.config.get("title", "人工审核"),
            source=self.config.get("source", "流程"),
            description=self.config.get("description"),
            form_schema=self.config.get("form_schema", []),
            status="pending",
            deadline=deadline,
        )
        async with async_session() as s:
            s.add(todo)
            await s.commit()
            await s.refresh(todo)
        return {"current_node": self.node_id, "status": "paused"}


class CodeExecutor(BaseNodeExecutor):
    async def run(self, state: dict) -> dict:
        t0 = time.perf_counter()
        code = self.config.get("code", "")
        inputs = resolve_dict(self.config.get("input_mapping", {}), state)
        try:
            from app.providers.sandbox import run_in_sandbox
            r = await run_in_sandbox(
                code=code, inputs=inputs,
                timeout=self.config.get("timeout_seconds", 30),
                memory_mb=self.config.get("memory_limit_mb", 256),
            )
            out = r.output
            err = r.error
        except ImportError:
            local: dict = {"args": inputs, "result": None}
            try:
                exec(code, {"__builtins__": __builtins__}, local)
                out = local.get("result")
                err = None
            except Exception as e:
                out = None
                err = str(e)
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        outputs = {**state.get("node_outputs", {}), self.node_id: {"output": out, "error": err}}
        timings = {**state.get("node_timings", {}), self.node_id: elapsed}
        return {"node_outputs": outputs, "node_timings": timings}


class VariableAssignExecutor(BaseNodeExecutor):
    async def run(self, state: dict) -> dict:
        variables = dict(state.get("variables", {}))
        for assignment in self.config.get("assignments", []):
            key = assignment.get("key", "")
            val = resolve(str(assignment.get("value", "")), state)
            if key:
                variables[key] = val
        return {"variables": variables}


class TemplateRenderExecutor(BaseNodeExecutor):
    async def run(self, state: dict) -> dict:
        from jinja2 import Template
        t0 = time.perf_counter()
        template_str = self.config.get("template", "")
        context = resolve_dict(self.config.get("context", {}), state)
        try:
            result = Template(template_str).render(**context)
        except Exception:
            result = resolve(template_str, state)
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        outputs = {**state.get("node_outputs", {}), self.node_id: {"output": result}}
        timings = {**state.get("node_timings", {}), self.node_id: elapsed}
        return {"node_outputs": outputs, "node_timings": timings}


# 注册所有执行器
for _name, _cls in [
    ("start", StartExecutor), ("end", EndExecutor),
    ("llm", LLMExecutor), ("rag", RAGExecutor),
    ("http", HTTPExecutor), ("tool", ToolExecutor),
    ("condition", ConditionExecutor), ("loop", LoopExecutor),
    ("human", HumanExecutor), ("code", CodeExecutor),
    ("variable_assign", VariableAssignExecutor),
    ("template_render", TemplateRenderExecutor),
]:
    NodeRouter.register(_name, _cls)
 
