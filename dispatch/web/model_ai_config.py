"""Read and edit model_ai's five connection fields without executing Python.

Only string-literal value spans are replaced.  All comments, whitespace and
unrelated expressions retain their original source text.  Ambiguous or dynamic
configuration is rejected rather than reporting a successful partial update.
The HTTP integration must redact ``db_password`` in the returned change list.
"""
import ast
from collections.abc import Mapping
import re


class ModelAiConfigError(ValueError):
    """A safe configuration error; its message never contains field values."""


FIELDS = ("linux_ip", "box_ip", "db_user", "db_password", "db_name")
_POOL_FIELDS = {"user": "db_user", "password": "db_password", "database": "db_name"}


def _names(target):
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return {name for item in target.elts for name in _names(item)}
    if isinstance(target, ast.Starred):
        return _names(target.value)
    return set()


def _string_node(node, field):
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        raise ModelAiConfigError("model_ai.py 的 %s 必须直接使用字符串常量，未写入任何文件" % field)
    if not all(hasattr(node, key) for key in ("lineno", "col_offset", "end_lineno", "end_col_offset")):
        raise ModelAiConfigError("当前 Python 版本不能安全定位配置字段，未写入任何文件")
    return node


def _module_nodes(node):
    """Walk module control flow without confusing function/class local scopes."""
    yield node
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return
    for child in ast.iter_child_nodes(node):
        yield from _module_nodes(child)


def _locate(text):
    if not isinstance(text, str):
        raise ModelAiConfigError("model_ai.py 必须为文本")
    try:
        tree = ast.parse(text, filename="model_ai.py")
    except (SyntaxError, ValueError, UnicodeError, RecursionError):
        raise ModelAiConfigError("model_ai.py 语法无效，未写入任何文件") from None

    result = {}
    for field in ("linux_ip", "box_ip"):
        matches = []
        for statement in tree.body:
            targets = statement.targets if isinstance(statement, ast.Assign) else (
                [statement.target] if isinstance(statement, (ast.AnnAssign, ast.AugAssign)) else [])
            if any(field in _names(target) for target in targets):
                matches.append(statement)
        if len(matches) != 1:
            raise ModelAiConfigError("model_ai.py 的 %s 顶层赋值缺失或不唯一，未写入任何文件" % field)
        statement = matches[0]
        if (not isinstance(statement, ast.Assign) or len(statement.targets) != 1 or
                not isinstance(statement.targets[0], ast.Name)):
            raise ModelAiConfigError("model_ai.py 的 %s 必须使用独立的简单赋值，未写入任何文件" % field)
        # A later conditional/loop assignment or named expression can override
        # the apparent top-level literal.  Reject this ambiguity as well.
        bindings = [node for node in _module_nodes(tree) if (
            isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == field or
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == field or
            isinstance(node, ast.alias) and (node.asname or node.name.split(".")[0]) == field)]
        if len(bindings) != 1 or bindings[0] is not statement.targets[0]:
            raise ModelAiConfigError("model_ai.py 的 %s 存在其他模块级赋值，未写入任何文件" % field)
        result[field] = _string_node(statement.value, field)

    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and (
        isinstance(node.func, ast.Name) and node.func.id == "PooledDB" or
        isinstance(node.func, ast.Attribute) and node.func.attr == "PooledDB")]
    if len(calls) != 1:
        raise ModelAiConfigError("model_ai.py 的 PooledDB 调用缺失或不唯一，未写入任何文件")
    pool = calls[0]
    if any(keyword.arg is None for keyword in pool.keywords):
        raise ModelAiConfigError("model_ai.py 的 PooledDB 不支持动态展开参数，未写入任何文件")
    for keyword_name, field in _POOL_FIELDS.items():
        matches = [keyword.value for keyword in pool.keywords if keyword.arg == keyword_name]
        if len(matches) != 1:
            raise ModelAiConfigError("model_ai.py 的 PooledDB.%s 参数缺失或不唯一，未写入任何文件" % keyword_name)
        result[field] = _string_node(matches[0], field)
    return result


def extract_model_ai(text):
    """Return linux_ip/box_ip and the three database fields from safe literals."""
    return {field: node.value for field, node in _locate(text).items()}


def _offset(lines, starts, line_number, byte_column):
    # AST columns count UTF-8 bytes, whereas Python string slices count Unicode
    # characters.  Source may contain Chinese before a same-line keyword.
    try:
        prefix = lines[line_number - 1].encode("utf-8")[:byte_column].decode("utf-8")
        return starts[line_number - 1] + len(prefix)
    except (IndexError, UnicodeError):
        raise ModelAiConfigError("无法安全定位 model_ai.py 字段，未写入任何文件") from None


def _literal(value, previous):
    # Preserve the ordinary quote style where possible, but remove raw-string
    # prefixes: the new value is escaped explicitly and must retain its value.
    match = re.match(r"(?i:[ru]*)(['\"])", previous)
    quote = match.group(1) if match else "'"
    escaped = value.replace("\\", "\\\\").replace(quote, "\\" + quote)
    escaped = escaped.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    # repr handles remaining control characters without altering ordinary
    # Unicode text.  Escape them explicitly so a new value cannot add syntax.
    escaped = "".join("\\x%02x" % ord(char) if ord(char) < 32 or ord(char) == 127 else char
                      for char in escaped)
    return quote + escaped + quote


def apply_model_ai(text, values):
    """Return (new source, changed literal count, structured changes).

    Missing fields and None values are retained.  Empty strings are explicit
    values here; the secure facade removes blank form fields before calling.
    Other form keys are ignored.  Existing configuration values must all be
    unambiguous literals even when only one field is being changed.
    """
    if not isinstance(values, Mapping):
        raise ModelAiConfigError("model_ai.py 配置字段必须为映射")
    located = _locate(text)
    # Python's parser counts CR/LF lines; str.splitlines would additionally
    # split Unicode separators that may legitimately appear inside a literal.
    lines = [line for line in re.findall(r"[^\r\n]*(?:\r\n|\r|\n|$)", text) if line]
    starts, length = [], 0
    for line in lines:
        starts.append(length)
        length += len(line)
    replacements, changes = [], []
    for field in FIELDS:
        if field not in values or values[field] is None:
            continue
        value = values[field]
        if not isinstance(value, str):
            raise ModelAiConfigError("model_ai.py 的 %s 新值必须为文本" % field)
        node = located[field]
        if node.value == value:
            continue
        start = _offset(lines, starts, node.lineno, node.col_offset)
        end = _offset(lines, starts, node.end_lineno, node.end_col_offset)
        replacements.append((start, end, _literal(value, text[start:end])))
        changes.append({"section": "py", "key": field, "old": node.value, "new": value})
    result = text
    for start, end, replacement in sorted(replacements, reverse=True):
        result = result[:start] + replacement + result[end:]
    # Assert the produced literals parse and match every requested value.  This
    # check does not import or execute any part of the target module.
    if replacements:
        after = extract_model_ai(result)
        if any(after[item["key"]] != item["new"] for item in changes):
            raise ModelAiConfigError("model_ai.py 改写校验失败，未写入任何文件")
    return result, len(changes), changes
