"""Restricted, secret-redacting configuration transactions for the dispatch UI.

Only this facade may expose the legacy module to an HTTP handler.  A preview is
an opaque, short-lived transaction; the client never receives configuration
text, existing credentials, or the generated replacement secret.
"""
import ast
import copy
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile
import threading
import time
import unicodedata

from model_ai_config import ModelAiConfigError


class ConfigError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _secret(key):
    return bool(re.search(r"password|secret|token", str(key), re.I))


def _sha(data):
    return hashlib.sha256(data).hexdigest()


class SecurityConfig:
    MAX_FILE_BYTES = 8 * 1024 * 1024
    MAX_PLANS = 128
    MAX_PLAN_BYTES = 64 * 1024 * 1024

    def __init__(self, legacy, allowed_paths, backup_root, *, data_root="/data/AIGO/platform_start",
                 strict_permissions=False, plan_ttl=300, clock=None):
        self.legacy = legacy
        self.lock = threading.RLock()
        self.root = Path(data_root).absolute()
        self.backup_root = Path(backup_root).absolute()
        self.strict_permissions = strict_permissions
        self.plan_ttl = plan_ttl
        self.clock = clock or time.monotonic
        self._plans = {}
        self._known_fields = {item[0] for item in legacy.FIELDS} | {"primary_ip"}
        self._secret_fields = {key for key in self._known_fields if _secret(key)}
        if not isinstance(allowed_paths, list) or not allowed_paths:
            raise ConfigError("必须配置非空的文件白名单", 500)
        self._check_chain(self.root, directory=True)
        discovered = copy.deepcopy(legacy.discover(force=True))
        by_path = {str(Path(f["path"]).absolute()): (d, f)
                   for d in discovered for f in d["files"] if f.get("exists")}
        self._allowed = {}
        self._dirs = []
        groups = {}
        for value in allowed_paths:
            if not isinstance(value, str) or not Path(value).is_absolute():
                raise ConfigError("白名单必须使用绝对路径", 500)
            path = Path(value).absolute()
            self._check_target(path)
            key = str(path)
            if key not in by_path:
                raise ConfigError("白名单包含无法识别的配置文件", 500)
            if key in self._allowed:
                raise ConfigError("白名单包含重复文件", 500)
            directory, entry = by_path[key]
            self._allowed[key] = entry["key"]
            group_key = (directory["kind"], directory["path"])
            if group_key not in groups:
                group = {k: copy.deepcopy(v) for k, v in directory.items() if k != "files"}
                group["files"] = []
                groups[group_key] = group
                self._dirs.append(group)
            entry = copy.deepcopy(entry)
            entry["path"] = key
            groups[group_key]["files"].append(entry)
        self._check_backup_location()
        # Restrict legacy state construction itself, rather than filtering a
        # broad scan after it has already read unrelated configuration files.
        legacy.discover = self.discover
        legacy.read_text = self._read_text

    def _under_root(self, path):
        if ".." in path.parts:
            raise ConfigError("配置路径不允许包含上级目录跳转", 403)
        try:
            path.relative_to(self.root)
        except ValueError:
            raise ConfigError("配置文件必须位于指定的数据目录", 403) from None

    @staticmethod
    def _check_chain(path, directory=False, allow_missing=False):
        for part in list(reversed(path.parents)) + [path]:
            try:
                mode = part.lstat().st_mode
            except FileNotFoundError:
                if allow_missing:
                    continue
                raise ConfigError("配置路径已失效，请重新预览", 409) from None
            if stat.S_ISLNK(mode):
                raise ConfigError("不允许使用符号链接配置路径", 403)
            if part != path or directory:
                if not stat.S_ISDIR(mode):
                    raise ConfigError("配置路径的父级必须是目录", 403)

    def _check_target(self, path):
        self._under_root(path)
        self._check_chain(path)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ConfigError("只允许操作普通配置文件", 403)
        if self.strict_permissions and info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise ConfigError("配置文件权限过宽，须先限制组和其他用户的写权限", 403)
        return info

    def _check_backup_location(self):
        self._under_root(self.backup_root)
        self._check_chain(self.backup_root, directory=True, allow_missing=True)

    def _read(self, path):
        path = Path(path)
        if str(path) not in self._allowed:
            raise ConfigError("选择了未授权的配置文件", 403)
        checked = self._check_target(path)
        fd = None
        try:
            fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or
                    (info.st_dev, info.st_ino) != (checked.st_dev, checked.st_ino)):
                raise ConfigError("配置文件在读取时发生变化，请重新预览", 409)
            if info.st_size > self.MAX_FILE_BYTES:
                raise ConfigError("配置文件超过允许大小", 413)
            with os.fdopen(fd, "rb") as stream:
                fd = None
                raw = stream.read(self.MAX_FILE_BYTES + 1)
            if len(raw) > self.MAX_FILE_BYTES:
                raise ConfigError("配置文件超过允许大小", 413)
            return raw, info
        except ConfigError:
            raise
        except OSError:
            raise ConfigError("无法安全读取配置文件", 409) from None
        finally:
            if fd is not None:
                os.close(fd)

    @staticmethod
    def _decode(raw):
        if raw.startswith(b"\xef\xbb\xbf"):
            return raw.decode("utf-8-sig"), "utf-8-sig"
        for encoding in ("utf-8", "gbk", "gb18030", "latin-1"):
            try:
                return raw.decode(encoding), encoding
            except UnicodeDecodeError:
                pass
        raise ConfigError("无法识别配置文件编码", 422)

    def _read_text(self, path):
        return self._decode(self._read(path)[0])

    def _extract(self, path, kind, text, encoding):
        # extract() is legacy's format-aware parser.  Force it to use the exact
        # bytes whose revision was checked, even if an external process writes.
        original = self.legacy.read_text
        self.legacy.read_text = lambda selected: (text, encoding) if Path(selected) == path else self._read_text(selected)
        try:
            return self.legacy.extract(path, kind)
        finally:
            self.legacy.read_text = original

    def discover(self, force=False):
        with self.lock:
            result = copy.deepcopy(self._dirs)
            for group in result:
                for item in group["files"]:
                    self._check_target(Path(item["path"]))
                    item["exists"] = True
            return result

    @staticmethod
    def _safe_field_text(value):
        return (isinstance(value, str) and len(value) <= 256 and
                not any(unicodedata.category(c).startswith("C") for c in value) and
                not any(c in value for c in "'\"\\"))

    def _saved_db_password(self):
        """Read the sole fixed reuse source; never accept a client source path."""
        source = self.root / "Config_files" / "config.ini"
        if self._allowed.get(str(source)) != "app_ini":
            raise ConfigError("主配置密码源不在授权文件中，无法沿用，请重新输入数据库密码", 422)
        try:
            raw, _ = self._read(source)
            text, encoding = self._decode(raw)
            password = self._extract(source, "app_ini", text, encoding).get("db_password")
        except Exception:
            raise ConfigError("无法安全读取主配置密码源，请检查主配置后重新预览", 422) from None
        if not password:
            raise ConfigError("主配置未配置数据库密码，无法沿用，请重新输入数据库密码", 422)
        if not self._safe_field_text(password):
            raise ConfigError("主配置密码不兼容安全派发格式，无法沿用，请重新输入符合规则的数据库密码", 422)
        return source, password, _sha(raw)

    def _check_secret_dependencies(self, dependencies):
        for source, expected_sha in dependencies.items():
            try:
                current_sha = _sha(self._read(Path(source))[0])
            except Exception:
                raise ConfigError("主配置密码源已失效，请重新预览，未覆盖外部修改", 409) from None
            if current_sha != expected_sha:
                raise ConfigError("主配置密码源已被其他操作修改，请重新预览，未覆盖外部修改", 409)

    def state(self):
        with self.lock:
            try:
                result = self.legacy.build_state()
                defaults = result.get("defaults", {})
                configured = {key: bool(defaults.get(key)) for key in self._secret_fields}
                # Some deployments have the streaming secret only in zlk.ini.
                for name, kind in self._allowed.items():
                    for key, value in self.legacy.extract(Path(name), kind).items():
                        if _secret(key):
                            configured[key] = configured.get(key, False) or bool(value)
                result["defaults"] = {key: value for key, value in defaults.items() if not _secret(key)}
                result["secret_configured"] = configured
                try:
                    self._saved_db_password()
                    saved_db_available = True
                except ConfigError:
                    saved_db_available = False
                result["saved_secret_sources"] = {"db_password": {
                    "available": saved_db_available,
                    "path": str(self.root / "Config_files" / "config.ini")}}
                result["auth_required"] = True
                result["backup_root"] = str(self.backup_root)
                for directory in result.get("dirs", []):
                    for item in directory["files"]:
                        item["revision"] = _sha(self._read(Path(item["path"]))[0])
                return result
            except ModelAiConfigError as error:
                raise ConfigError(str(error), 422) from None
            except ConfigError:
                raise
            except Exception:
                raise ConfigError("读取配置状态失败，请联系管理员", 500) from None

    def _validate_payload(self, payload):
        if not isinstance(payload, dict) or set(payload) - {"files", "values", "reuse_db_password"}:
            raise ConfigError("预览请求格式不正确")
        reuse = payload.get("reuse_db_password", False)
        if type(reuse) is not bool:
            raise ConfigError("沿用主配置密码选项必须为布尔值")
        values, files = payload.get("values"), payload.get("files")
        if not isinstance(values, dict) or not isinstance(files, list) or not files:
            raise ConfigError("请选择配置文件并提交有效字段")
        if len(files) > len(self._allowed) or any(not isinstance(p, str) for p in files):
            raise ConfigError("配置文件选择不正确")
        if len(files) != len(set(files)) or any(p not in self._allowed for p in files):
            raise ConfigError("选择了未授权或重复的配置文件", 403)
        if set(values) - self._known_fields:
            raise ConfigError("请求包含未知配置字段")
        if reuse and values.get("db_password") not in (None, ""):
            raise ConfigError("沿用主配置密码与输入新数据库密码不能同时使用，请选择一种方式")
        clean = {}
        hosts = set(self.legacy.IP_LIKE_FIELDS) | {"primary_ip"}
        for key, value in values.items():
            if not isinstance(value, str) or len(value) > 256:
                raise ConfigError("配置字段必须为不超过 256 个字符的文本")
            if not self._safe_field_text(value):
                raise ConfigError("配置值不能包含引号、反斜杠或控制字符；密码也须遵守此规则")
            if not value:
                clean[key] = value
                continue
            if key in hosts:
                if len(value) > 253 or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", value):
                    raise ConfigError("主机字段仅支持 IPv4 地址或合法主机名")
                if re.fullmatch(r"[0-9.]+", value):
                    try:
                        ipaddress.IPv4Address(value)
                    except ValueError:
                        raise ConfigError("IPv4 地址格式不正确") from None
                elif any(not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                         for label in value.split(".")):
                    raise ConfigError("主机名格式不正确")
            if key.endswith("_port"):
                if not re.fullmatch(r"[0-9]{1,5}", value) or not 1 <= int(value) <= 65535:
                    raise ConfigError("端口必须是 1 至 65535 的整数")
            clean[key] = value
        if clean.get("zlk_secret") == "__RANDOM__":
            clean["zlk_secret"] = secrets.token_hex(32)
        # Missing service hosts retain the original form's primary-IP behavior;
        # explicitly empty fields preserve each file's existing value instead.
        # platform-site-dispatch-v1
        import sys
        folder = self.root / 'Config_files'
        if (self.root / 'platform_ops/state/site-config.json').exists():
            sys.path.insert(0, str(folder))
            from platform_site_config import guard_legacy_values, SiteConfigError
            try:
                guard_legacy_values(self.root, clean)
            except SiteConfigError as error:
                raise ConfigError(str(error), 409) from None
        else:
            self.legacy.fill_ip_defaults(clean)
        return clean, files, reuse

    @staticmethod
    def _safe_result(kind, path, encoding, changes, skipped):
        safe = []
        for change in changes:
            item = {key: change.get(key, "") for key in ("section", "key")}
            if _secret(item["key"]):
                item.update(old="已配置" if change.get("old") else "未配置", new="将更新")
            else:
                item.update(old=change.get("old", ""), new=change.get("new", ""))
            safe.append(item)
        return {"kind": kind, "path": str(path), "encoding": encoding,
                "changed": len(changes), "changes": safe,
                "skipped": [{"key": key, "reason": "留空，保留各文件原值"} for key in skipped]}

    def _expire(self):
        now = self.clock()
        self._plans = {key: plan for key, plan in self._plans.items() if plan["expires"] > now}

    def preview(self, payload, session_id):
        with self.lock:
            if not isinstance(session_id, str) or not session_id:
                raise ConfigError("会话无效，请重新登录", 401)
            values, files, reuse = self._validate_payload(payload)
            self._expire()
            if len(self._plans) >= self.MAX_PLANS:
                raise ConfigError("待执行的预览过多，请稍后再试", 429)
            records, results = [], []
            dependencies = {}
            source = None
            if reuse:
                source, password, source_sha = self._saved_db_password()
                values["db_password"] = password
                dependencies[str(source)] = source_sha
            try:
                for name in files:
                    path, kind = Path(name), self._allowed[name]
                    raw, info = self._read(path)
                    if name in dependencies and _sha(raw) != dependencies[name]:
                        raise ConfigError("主配置密码源在预览期间已变化，请重新预览", 409)
                    text, encoding = self._decode(raw)
                    current = self._extract(path, kind, text, encoding)
                    effective = {key: value for key, value in values.items() if value != ""}
                    skipped = [key for key, value in values.items() if value == "" and current.get(key)]
                    new_text, count, changes = self.legacy.apply_values(text, kind, effective)
                    if path.suffix.lower() == ".py":
                        try:
                            ast.parse(new_text, filename=path.name)
                        except (SyntaxError, ValueError):
                            raise ConfigError("生成的 Python 配置语法无效，未写入任何文件", 422) from None
                    try:
                        new_raw = new_text.encode(encoding)
                    except UnicodeError:
                        raise ConfigError("新值无法使用原文件编码保存", 422) from None
                    records.append({"path": path, "raw": raw, "new": new_raw,
                                    "sha": _sha(raw), "info": info, "changed": count,
                                    "encoding": encoding})
                    results.append(self._safe_result(kind, path, encoding, changes, skipped))
            except ModelAiConfigError as error:
                raise ConfigError(str(error), 422) from None
            except ConfigError:
                raise
            except Exception:
                raise ConfigError("配置预览失败，未写入任何文件", 500) from None
            plan_id = secrets.token_urlsafe(32)
            memory = sum(len(item["raw"]) + len(item["new"]) for item in records)
            retained = sum(plan["bytes"] for plan in self._plans.values())
            if memory + retained > self.MAX_PLAN_BYTES:
                raise ConfigError("待执行预览占用过多，请先完成现有预览或稍后再试", 429)
            self._plans[plan_id] = {"session": session_id, "expires": self.clock() + self.plan_ttl,
                                    "records": records, "results": results, "bytes": memory,
                                    "dependencies": dependencies, "reuse_db_password": reuse,
                                    "secret_sync_source": str(source) if source is not None else None}
            return {"ok": True, "plan_id": plan_id, "expires_in": self.plan_ttl,
                    "results": copy.deepcopy(results), "reuse_db_password": reuse,
                    "secret_sync_source": str(source) if source is not None else None}

    @staticmethod
    def _fsync_directory(path):
        if os.name != "posix":
            return
        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _private_backup(self, records):
        self._check_backup_location()
        self.backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._check_backup_location()
        os.chmod(str(self.backup_root), 0o700)
        folder = Path(tempfile.mkdtemp(prefix=time.strftime("%Y%m%d-%H%M%S-") , dir=str(self.backup_root)))
        os.chmod(str(folder), 0o700)
        manifest = []
        for index, record in enumerate(records):
            destination = folder / ("%02d-%s" % (index + 1, record["path"].name))
            fd = os.open(str(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                if hasattr(os, "fchmod"):
                    os.fchmod(stream.fileno(), 0o600)
                stream.write(record["raw"])
                stream.flush()
                os.fsync(stream.fileno())
            manifest.append({"src": str(record["path"]), "bak": str(destination),
                             "sha256": record["sha"], "mode": stat.S_IMODE(record["info"].st_mode),
                             "uid": record["info"].st_uid, "gid": record["info"].st_gid})
        destination = folder / "manifest.json"
        fd = os.open(str(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            if hasattr(os, "fchmod"):
                os.fchmod(stream.fileno(), 0o600)
            stream.write(json.dumps({"files": manifest}, ensure_ascii=False, indent=2).encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        self._fsync_directory(folder)
        self._fsync_directory(self.backup_root)
        return str(folder)

    def _atomic_replace(self, path, raw, info, *, expected_sha=None,
                        expected_identity=None, on_replace=None):
        self._check_target(path)
        fd, name = tempfile.mkstemp(prefix="." + path.name + ".cfgp-", dir=str(path.parent))
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                # A CAP_CHOWN-only service may set the original owner, but
                # loses its owner right to chmod immediately after doing so.
                if hasattr(os, "fchmod"):
                    os.fchmod(stream.fileno(), stat.S_IMODE(info.st_mode))
                else:
                    os.chmod(str(temporary), stat.S_IMODE(info.st_mode))
                if hasattr(os, "fchown"):
                    os.fchown(stream.fileno(), info.st_uid, info.st_gid)
                stream.flush()
                os.fsync(stream.fileno())
                own_info = os.fstat(stream.fileno())
                own_identity = (own_info.st_dev, own_info.st_ino)
            current, current_info = self._read(path)
            if ((expected_sha is not None and _sha(current) != expected_sha) or
                    (expected_identity is not None and
                     (current_info.st_dev, current_info.st_ino) != expected_identity)):
                raise ConfigError("配置已被其他操作修改，未覆盖该文件，请重新预览", 409)
            os.replace(str(temporary), str(path))
            # Record the commit before readback/fsync: either can fail after
            # replace succeeded.  A failure before replace never enters the
            # rollback list, so an external update is not overwritten there.
            if on_replace is not None:
                on_replace(own_identity)
            self._fsync_directory(path.parent)
            if self._read(path)[0] != raw:
                raise OSError("configuration readback mismatch")
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def apply(self, payload, session_id):
        with self.lock:
            if (not isinstance(payload, dict) or set(payload) != {"plan_id"} or
                    not isinstance(payload.get("plan_id"), str)):
                raise ConfigError("应用请求只能包含预览计划编号")
            self._expire()
            plan = self._plans.get(payload["plan_id"])
            if not plan or plan["session"] != session_id:
                raise ConfigError("预览已失效或不属于当前会话，请重新预览", 409)
            # Consume once even if a conflict or I/O error subsequently occurs.
            del self._plans[payload["plan_id"]]
            records = plan["records"]
            dependencies = dict(plan.get("dependencies", {}))
            metadata = {"reuse_db_password": plan.get("reuse_db_password", False),
                        "secret_sync_source": plan.get("secret_sync_source")}
            self._check_secret_dependencies(dependencies)
            for record in records:
                current, info = self._read(record["path"])
                if _sha(current) != record["sha"]:
                    raise ConfigError("配置已被其他操作修改，请重新预览", 409)
                record["info"] = info
            todo = [record for record in records if record["new"] != record["raw"]]
            if not todo:
                return {"ok": True, "applied": 0, "written": [], "backup": None,
                        "results": copy.deepcopy(plan["results"]), "note": "没有需要改动的文件", **metadata}
            try:
                backup = self._private_backup(todo)
            except Exception:
                raise ConfigError("创建安全备份失败，未写入任何配置", 500) from None
            replaced = []
            try:
                for record in todo:
                    self._check_secret_dependencies(dependencies)
                    if _sha(self._read(record["path"])[0]) != record["sha"]:
                        raise ConfigError("配置已被其他操作修改，请重新预览", 409)
                    self._atomic_replace(
                        record["path"], record["new"], record["info"],
                        expected_sha=record["sha"],
                        on_replace=lambda identity, saved=record: replaced.append((saved, identity)))
                    if str(record["path"]) in dependencies:
                        dependencies[str(record["path"])] = _sha(record["new"])
                self._check_secret_dependencies(dependencies)
            except Exception as failure:
                rollback_ok = True
                for record, own_identity in reversed(replaced):
                    try:
                        self._atomic_replace(
                            record["path"], record["raw"], record["info"],
                            expected_sha=_sha(record["new"]), expected_identity=own_identity)
                    except Exception:
                        rollback_ok = False
                if not rollback_ok:
                    raise ConfigError("写入失败且部分文件因权限或外部变更未回滚；未覆盖检测到的外部修改，请联系管理员检查安全备份", 500) from None
                if isinstance(failure, ConfigError) and failure.status == 409:
                    raise failure from None
                raise ConfigError("写入失败，已回滚本次修改，请重新预览", 500) from None
            return {"ok": True, "applied": len(todo), "backup": backup,
                    "written": [{"path": str(record["path"]), "changed": record["changed"],
                                 "encoding": record["encoding"], "verified": True} for record in todo],
                    "results": copy.deepcopy(plan["results"]), **metadata}
