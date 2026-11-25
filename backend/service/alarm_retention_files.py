"""Strict local media resolution; URLs are never fetched and directories never removed."""
import ast
import json
import os
import stat
from pathlib import Path
from urllib.parse import unquote, urlsplit

MEDIA_FIELDS = ('res_image', 'res_video', 'warning_video', 'carousel_images_list', 'ori_images_list')
MEDIA_EXTENSIONS = frozenset(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.mp4', '.avi', '.mov', '.mkv'))


def _strings(value, depth=0):
    if depth > 8:
        return
    if isinstance(value, str):
        if value and len(value) <= 4096:
            yield value
    elif isinstance(value, (list, tuple)):
        for item in value[:10000]:
            yield from _strings(item, depth + 1)
    elif isinstance(value, dict):
        for item in list(value.values())[:10000]:
            yield from _strings(item, depth + 1)


def media_references(row):
    """Callbacks historically use both JSON and Python list representations."""
    for field in MEDIA_FIELDS:
        value = row.get(field)
        if isinstance(value, str) and value.lstrip().startswith(('[', '(', '{')):
            if len(value) > 2 * 1024 * 1024:
                continue
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                try:
                    value = ast.literal_eval(value)
                except (ValueError, SyntaxError, MemoryError, RecursionError):
                    continue
        yield from _strings(value)


class MediaResolver:
    def __init__(self, config):
        self.mappings = []
        self.roots = []
        self.root_signatures = {}
        for mapping in config.get('media_mappings', []):
            root = self._root(mapping.get('root'))
            parsed = urlsplit(str(mapping.get('url_prefix', '')))
            if (root is None or parsed.scheme not in ('http', 'https') or not parsed.hostname
                    or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or not parsed.path.endswith('/')):
                raise ValueError('invalid media mapping')
            self.mappings.append((parsed.scheme, parsed.netloc.lower(), unquote(parsed.path), root))
            if root not in self.roots:
                self.roots.append(root)
        for value in config.get('local_roots', []):
            root = self._root(value)
            if root is None:
                raise ValueError('invalid media root')
            if root not in self.roots:
                self.roots.append(root)
        for root in self.roots:
            info = root.stat()
            self.root_signatures[str(root)] = (info.st_dev, info.st_ino)

    @staticmethod
    def _root(value):
        if not isinstance(value, str) or not value or '\x00' in value:
            return None
        root = Path(value)
        # Broad filesystem, data, application and temporary roots are never allowed.
        if (not root.is_absolute() or len(root.parts) < 3 or '..' in root.parts
                or root.is_symlink() or not root.is_dir()):
            return None
        resolved = root.resolve()
        if resolved != root:
            return None
        return root

    def _candidate(self, root, relative):
        if '\x00' in relative or (os.name == 'posix' and '\\' in relative):
            return None
        parts = Path(relative).parts
        if not parts or Path(relative).is_absolute() or '..' in parts:
            return None
        candidate = root.joinpath(*parts)
        if candidate.suffix.lower() not in MEDIA_EXTENSIONS:
            return None
        try:
            candidate.relative_to(root)
            # Fail closed on any symlink, including a nonexistent leaf under a linked parent.
            for part in (candidate, *candidate.parents):
                if part == root:
                    break
                if part.is_symlink():
                    return None
        except (ValueError, OSError):
            return None
        return str(candidate)

    def resolve(self, value):
        if not isinstance(value, str):
            return None
        if Path(value).is_absolute():
            candidate = Path(value)
            for root in self.roots:
                try:
                    return self._candidate(root, str(candidate.relative_to(root)))
                except ValueError:
                    pass
            return None
        try:
            # Historical alarm rows contain literal # in media filenames. The
            # existing list API already emits these as %23; preserve that meaning.
            parsed = urlsplit(value.replace('#', '%23'))
        except ValueError:
            return None
        if parsed.scheme in ('http', 'https'):
            if parsed.username or parsed.password:
                return None
            path = unquote(parsed.path)
            if '\\' in path:
                return None
            for scheme, authority, prefix, root in self.mappings:
                if scheme == parsed.scheme and authority == parsed.netloc.lower() and path.startswith(prefix):
                    return self._candidate(root, path[len(prefix):])
            return None
        return None

    def fingerprint(self, path):
        if self.resolve(path) != path:
            return None
        try:
            info = os.stat(path, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                return None
            return info.st_size, info.st_mtime_ns
        except OSError:
            return None

    def unlink(self, path, size, mtime_ns, cutoff_timestamp):
        """Return outcome and bytes freed; Linux walks parent directories without following links."""
        if self.resolve(path) != path:
            return 'unmanaged', 0
        root = None
        for possible in self.roots:
            try:
                Path(path).relative_to(possible)
                root = possible
                break
            except ValueError:
                pass
        if root is None:
            return 'unmanaged', 0
        descriptors = []
        try:
            parts = Path(path).relative_to(root).parts
            if os.name == 'posix' and hasattr(os, 'O_NOFOLLOW'):
                current = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                descriptors.append(current)
                root_info = os.fstat(current)
                if (root_info.st_dev, root_info.st_ino) != self.root_signatures[str(root)]:
                    return 'changed', 0
                for part in parts[:-1]:
                    current = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
                    descriptors.append(current)
                info = os.stat(parts[-1], dir_fd=current, follow_symlinks=False)
            else:
                current = None
                info = os.stat(path, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                return 'changed', 0
            if info.st_mtime >= cutoff_timestamp:
                return 'recent', 0
            if size is None or mtime_ns is None or (info.st_size, info.st_mtime_ns) != (size, mtime_ns):
                return 'changed', 0
            if current is None:
                os.unlink(path)
            else:
                os.unlink(parts[-1], dir_fd=current)
            return 'deleted', info.st_size if info.st_nlink == 1 else 0
        except FileNotFoundError:
            return 'missing', 0
        except OSError:
            return 'error', 0
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
