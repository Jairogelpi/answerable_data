from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import dataclass

from answerable.execution.errors import ExecutionTimedOut, UnsafePython

_CALLS = frozenset({"abs", "len", "max", "min", "round", "sorted", "sum"})
_NODES = (
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Set,
    ast.Subscript,
    ast.Slice,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Call,
    ast.keyword,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Not,
    ast.And,
    ast.Or,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
)

_RUNNER = """
import json, sys
allowed = {name: getattr(__builtins__, name) for name in %r}
data = json.loads(sys.stdin.read())
result = eval(compile(%r, "<analysis>", "eval"), {"__builtins__": allowed}, {"data": data})
sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")))
"""


@dataclass(frozen=True, slots=True)
class PythonSandboxExecutor:
    expression: str
    timeout_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._validate()

    def execute(self, payload: dict[str, object]) -> object:
        command = [sys.executable, "-I", "-S", "-c", _RUNNER % (sorted(_CALLS), self.expression)]
        try:
            completed = subprocess.run(
                command,
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise ExecutionTimedOut("sandbox exceeded its deadline") from error
        if completed.returncode != 0:
            raise UnsafePython("sandbox expression failed")
        return json.loads(completed.stdout)

    def _validate(self) -> None:
        try:
            tree = ast.parse(self.expression, mode="eval")
        except SyntaxError as error:
            raise UnsafePython("expression could not be parsed") from error
        for node in ast.walk(tree):
            if not isinstance(node, _NODES):
                raise UnsafePython(f"syntax is not allowed: {type(node).__name__}")
            if isinstance(node, ast.Name) and node.id not in _CALLS | {"data"}:
                raise UnsafePython(f"name is not allowed: {node.id}")
            if isinstance(node, ast.Call) and (
                not isinstance(node.func, ast.Name) or node.func.id not in _CALLS
            ):
                raise UnsafePython("call is not allowed")
