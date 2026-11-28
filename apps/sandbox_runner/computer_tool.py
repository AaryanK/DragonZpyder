from __future__ import annotations

import base64
import ctypes
import errno
import fnmatch
import hashlib
import ipaddress
import json
import os
import shutil
import selectors
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse


ROOT = Path('/workspace/work').resolve()
STATE = Path('/workspace/.operly').resolve()
PYTHON = '/opt/operly-py/bin/python'
MAX_STDIO = 2_000_000
MAX_FILE_BYTES = 5_000_000
MAX_ARTIFACT_BYTES = 20_000_000
MAX_DOWNLOAD_BYTES = 50_000_000
MAX_REDIRECTS = 6


def emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, separators=(',', ':'), sort_keys=True, default=str))


def load_args(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text('utf-8'))
    if not isinstance(data, dict):
        raise ValueError('tool arguments must be an object')
    return data


def session_meta() -> dict[str, Any]:
    try:
        value = json.loads(Path('/opt/dz-computer-public.json').read_text('utf-8'))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def network_policy() -> str:
    return str(session_meta().get('networkPolicy') or 'off')


def network_allowed() -> None:
    if network_policy() == 'off':
        raise PermissionError('network access is disabled for this Computer session')


def safe_path(raw: Any, default: str = '.') -> Path:
    value = str(raw if raw is not None else default).strip() or default
    if '\x00' in value or value.startswith('/'):
        raise ValueError('paths must be relative to the Computer workspace')
    lexical=Path(value)
    if '..' in lexical.parts:
        raise ValueError('parent traversal forbidden')
    candidate=ROOT
    for part in lexical.parts:
        candidate=candidate / part
        if candidate.is_symlink():
            raise ValueError('symlink paths are not permitted')
    resolved=candidate.resolve()
    if resolved != ROOT and ROOT not in resolved.parents:
        raise ValueError('path escaped the Computer workspace')
    return resolved


def rel(path: Path) -> str:
    value = path.resolve().relative_to(ROOT)
    return '.' if str(value) == '.' else str(value)


def bounded_text(value: bytes, limit: int = MAX_STDIO) -> tuple[str, bool]:
    truncated = len(value) > limit
    return value[:limit].decode('utf-8', 'replace'), truncated


def clean_env(extra: dict[str, Any] | None = None) -> dict[str, str]:
    env = {
        'PATH': os.getenv('PATH', '/usr/local/bin:/usr/bin:/bin'),
        'HOME': str(ROOT),
        'TMPDIR': str(STATE / 'tmp'),
        'LANG': 'C.UTF-8',
        'LC_ALL': 'C.UTF-8',
        'OPERLY_COMPUTER_NETWORK_POLICY': network_policy(),
    }
    (STATE / 'tmp').mkdir(parents=True, exist_ok=True)
    for key, value in (extra or {}).items():
        clean_key = str(key)[:120]
        upper = clean_key.upper()
        if clean_key.startswith('OPERLY_') or upper.endswith(('TOKEN', 'SECRET', 'PASSWORD', 'KEY')):
            continue
        env[clean_key] = str(value)[:8000]
    return env


def run_process(argv: list[str], *, cwd: Path, timeout: int, env: dict[str, str] | None = None) -> dict[str, Any]:
    # Never capture unbounded stdout/stderr in memory. Drain both pipes
    # concurrently, keep only a fixed preview, and kill the process group
    # on deadline (or after the leader exits with lingering child pipes).
    process = subprocess.Popen(argv,cwd=str(cwd),env=env or clean_env(),
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        start_new_session=True,bufsize=0)
    selector=selectors.DefaultSelector()
    captures={"stdout":bytearray(),"stderr":bytearray()}
    truncated={"stdout":False,"stderr":False}
    deadline=time.monotonic()+max(1,min(timeout,60))
    timed_out=False
    try:
        for name,stream in (("stdout",process.stdout),("stderr",process.stderr)):
            os.set_blocking(stream.fileno(),False)
            selector.register(stream,selectors.EVENT_READ,name)
        while selector.get_map() or process.poll() is None:
            remaining=deadline-time.monotonic()
            if remaining<=0:
                timed_out=True
                break
            if not selector.get_map():
                time.sleep(min(remaining,.02))
                continue
            for key,_ in selector.select(min(remaining,.1)):
                try:
                    chunk=os.read(key.fileobj.fileno(),65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buf=captures[key.data]
                available=MAX_STDIO-len(buf)
                buf.extend(chunk[:available])
                if len(chunk)>available:
                    truncated[key.data]=True
    finally:
        # The root runner additionally terminates any agent-owned processes
        # that escaped this process group before allowing another operation.
        try:
            os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:
            pass
        selector.close()
        for stream in (process.stdout,process.stderr):
            stream.close()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            timed_out=True
    return {
        "exit_code":None if timed_out else process.returncode,
        "timed_out":timed_out,
        "stdout":captures["stdout"].decode("utf-8","replace"),
        "stderr":captures["stderr"].decode("utf-8","replace"),
        "stdout_truncated":truncated["stdout"],
        "stderr_truncated":truncated["stderr"],
    }


def terminal_exec(args: dict[str, Any]) -> dict[str, Any]:
    command = str(args.get('command') or '')
    if not command:
        raise ValueError('command is required')
    cwd = safe_path(args.get('cwd'))
    timeout = max(1, min(int(args.get('timeout_seconds') or 120), 900))
    env = clean_env(dict(args.get('env') or {}))
    if bool(args.get('background')):
        process_id = hashlib.sha256(os.urandom(32)).hexdigest()[:24]
        process_dir = STATE / 'processes'
        process_dir.mkdir(parents=True, exist_ok=True)
        log_path = process_dir / f'{process_id}.log'
        log_handle = log_path.open('ab', buffering=0)
        process = subprocess.Popen(
            ['/bin/bash', '-lc', command],
            cwd=str(cwd),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        meta = {
            'process_id': process_id,
            'pid': process.pid,
            'command': command[:4000],
            'cwd': rel(cwd),
            'log_path': str(log_path),
            'started_at': time.time(),
        }
        (process_dir / f'{process_id}.json').write_text(json.dumps(meta), encoding='utf-8')
        return {'background': True, **meta}
    return {'background': False, **run_process(['/bin/bash', '-lc', command], cwd=cwd, timeout=timeout, env=env)}


def python_exec(args: dict[str, Any]) -> dict[str, Any]:
    code = str(args.get('code') or '')
    if not code:
        raise ValueError('code is required')
    cwd = safe_path(args.get('cwd'))
    timeout = max(1, min(int(args.get('timeout_seconds') or 120), 900))
    return run_process([PYTHON, '-c', code], cwd=cwd, timeout=timeout)


def files_list(args: dict[str, Any]) -> dict[str, Any]:
    target = safe_path(args.get('path'))
    if not target.exists():
        raise FileNotFoundError('path not found')
    limit = max(1, min(int(args.get('max_entries') or 500), 5000))
    recursive = bool(args.get('recursive'))
    paths = target.rglob('*') if target.is_dir() and recursive else target.iterdir() if target.is_dir() else [target]
    items = []
    for examined,path in enumerate(paths):
        if len(items)>=limit or examined>=20000:
            break
        try:
            path=safe_path(str(path.relative_to(ROOT)))
            stat=path.stat()
        except (OSError,ValueError):
            continue
        items.append({
            'path': rel(path),
            'type': 'directory' if path.is_dir() else 'file',
            'size_bytes': stat.st_size if path.is_file() else None,
            'modified_at': stat.st_mtime,
        })
    return {'path': rel(target), 'items': items, 'truncated': len(items) >= limit}


def files_read(args: dict[str, Any]) -> dict[str, Any]:
    target = safe_path(args.get('path'))
    if not target.is_file():
        raise FileNotFoundError('file not found')
    maximum = max(1, min(int(args.get('max_bytes') or 2_000_000), MAX_FILE_BYTES))
    with target.open('rb') as handle:
        raw=handle.read(maximum+1)
        size=os.fstat(handle.fileno()).st_size
    content,truncated=bounded_text(raw,maximum)
    return {'path':rel(target),'content':content,'size_bytes':size,'truncated':truncated or size>maximum}


def files_write(args: dict[str, Any]) -> dict[str, Any]:
    target = safe_path(args.get('path'))
    raw = str(args.get('content') or '').encode('utf-8')
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError('file write exceeds Computer limit')
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = 'ab' if bool(args.get('append')) else 'wb'
    with target.open(mode) as handle:
        handle.write(raw)
    return {'path': rel(target), 'size_bytes': target.stat().st_size}


def files_mkdir(args: dict[str, Any]) -> dict[str, Any]:
    target = safe_path(args.get('path'))
    target.mkdir(parents=True, exist_ok=True)
    return {'path': rel(target), 'created': True}


def files_remove(args: dict[str, Any]) -> dict[str, Any]:
    target = safe_path(args.get('path'))
    if target == ROOT:
        raise ValueError('cannot remove the Computer workspace root')
    if not target.exists():
        return {'path': rel(target), 'removed': False, 'missing': True}
    if target.is_dir():
        if any(target.iterdir()) and not bool(args.get('recursive')):
            raise ValueError('directory is not empty; recursive=true is required')
        shutil.rmtree(target)
    else:
        target.unlink()
    return {'path': rel(target), 'removed': True}


def files_move(args: dict[str, Any]) -> dict[str, Any]:
    source = safe_path(args.get('source'))
    destination = safe_path(args.get('destination'))
    if not source.exists():
        raise FileNotFoundError('source path not found')
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return {'source': rel(source), 'destination': rel(destination), 'moved': True}


def files_search(args: dict[str, Any]) -> dict[str, Any]:
    target = safe_path(args.get('path'))
    query = str(args.get('query') or '')
    if not query:
        raise ValueError('query is required')
    pattern = str(args.get('glob') or '*')
    limit = max(1, min(int(args.get('max_matches') or 200), 1000))
    matches: list[dict[str, Any]] = []
    candidates = target.rglob('*') if target.is_dir() else [target]
    needle = query.lower()
    for examined,path in enumerate(candidates):
        if len(matches)>=limit or examined>=20000:
            break
        try:
            path=safe_path(str(path.relative_to(ROOT)))
        except (OSError,ValueError):
            continue
        if not path.is_file() or not fnmatch.fnmatch(path.name, pattern):
            continue
        if needle in path.name.lower():
            matches.append({'path': rel(path), 'kind': 'filename'})
        try:
            if path.stat().st_size > 2_000_000:
                continue
            with path.open('rb') as handle:
                text=handle.read(2_000_001).decode('utf-8','replace')
        except OSError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if needle in line.lower():
                matches.append({'path': rel(path), 'kind': 'content', 'line': number, 'text': line[:1000]})
                if len(matches) >= limit:
                    break
    return {'query': query, 'matches': matches, 'truncated': len(matches) >= limit}


def process_list(_: dict[str, Any]) -> dict[str, Any]:
    process_dir = STATE / 'processes'
    process_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for meta_path in sorted(process_dir.glob('*.json')):
        try:
            meta = json.loads(meta_path.read_text('utf-8'))
            pid = int(meta.get('pid') or 0)
            running = False
            if pid > 0:
                try:
                    os.kill(pid, 0)
                    running = True
                except OSError:
                    pass
            items.append({**meta, 'state': 'running' if running else 'exited'})
        except Exception:
            continue
    return {'processes': items}


def process_kill(args: dict[str, Any]) -> dict[str, Any]:
    process_id = str(args.get('process_id') or '')
    meta_path = STATE / 'processes' / f'{process_id}.json'
    if not meta_path.is_file():
        raise FileNotFoundError('background process not found')
    meta = json.loads(meta_path.read_text('utf-8'))
    pid = int(meta.get('pid') or 0)
    sig = {'TERM': signal.SIGTERM, 'KILL': signal.SIGKILL, 'INT': signal.SIGINT}.get(str(args.get('signal') or 'TERM'), signal.SIGTERM)
    try:
        os.killpg(pid, sig)
        stopped = True
    except ProcessLookupError:
        stopped = False
    return {'process_id': process_id, 'pid': pid, 'stopped': stopped}


GIT_ALLOWED = {
    'status', 'diff', 'log', 'show', 'branch', 'checkout', 'switch', 'restore', 'add', 'commit',
    'init', 'clone', 'fetch', 'pull', 'rev-parse', 'ls-files', 'remote', 'tag', 'merge', 'rebase',
}
NETWORK_GIT = {'clone', 'fetch', 'pull'}


def git_tool(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    cwd = safe_path(args.get('cwd'))
    if tool == 'git.status':
        git_args = ['status', '--short', '--branch']
    elif tool == 'git.diff':
        git_args = ['diff']
        if bool(args.get('staged')):
            git_args.append('--cached')
        if args.get('path'):
            git_args.extend(['--', str(args['path'])])
    else:
        git_args = [str(v) for v in list(args.get('args') or [])]
        if not git_args:
            raise ValueError('git args are required')
        if git_args[0] not in GIT_ALLOWED:
            raise PermissionError(f'git subcommand is not enabled: {git_args[0]}')
        if git_args[0] in NETWORK_GIT:
            network_allowed()
    timeout = max(1, min(int(args.get('timeout_seconds') or 120), 900))
    return run_process(['git', *git_args], cwd=cwd, timeout=timeout)


def public_url(raw: str) -> str:
    parsed = urlparse(raw)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise ValueError('only public HTTP(S) URLs are allowed')
    host = parsed.hostname.lower()
    if host in {'localhost', 'localhost.localdomain'} or host.endswith('.local'):
        raise PermissionError('local/private network targets are blocked')
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(item[4][0])
        if (
            address.is_private or address.is_loopback or address.is_link_local or address.is_multicast
            or address.is_reserved or address.is_unspecified
        ):
            raise PermissionError('private/link-local network targets are blocked')
    return raw


def public_request(method: str, url: str, timeout: int = 30) -> Any:
    import requests
    network_allowed()
    current = public_url(url)
    session = requests.Session()
    request_method = method.upper()
    for redirect_count in range(MAX_REDIRECTS + 1):
        response = session.request(request_method, current, allow_redirects=False, timeout=timeout, headers={'User-Agent': 'Operly-Agent-Computer/2'})
        if response.status_code not in {301, 302, 303, 307, 308}:
            return response
        location = response.headers.get('location')
        if not location:
            return response
        if redirect_count >= MAX_REDIRECTS:
            raise ValueError('too many redirects')
        current = public_url(urljoin(response.url, location))
        if response.status_code == 303 and request_method != 'HEAD':
            request_method = 'GET'
    raise ValueError('too many redirects')


def web_fetch(args: dict[str, Any]) -> dict[str, Any]:
    method = str(args.get('method') or 'GET').upper()
    if method not in {'GET', 'HEAD'}:
        raise ValueError('method must be GET or HEAD')
    response = public_request(method, str(args.get('url') or ''), timeout=30)
    maximum = max(1, min(int(args.get('max_bytes') or 2_000_000), 5_000_000))
    raw = response.content
    content, truncated = bounded_text(raw, maximum)
    return {
        'url': response.url,
        'status_code': response.status_code,
        'content_type': response.headers.get('content-type'),
        'content': '' if method == 'HEAD' else content,
        'size_bytes': len(raw),
        'truncated': truncated,
    }


def web_download(args: dict[str, Any]) -> dict[str, Any]:
    response = public_request('GET', str(args.get('url') or ''), timeout=60)
    response.raise_for_status()
    maximum = max(1, min(int(args.get('max_bytes') or MAX_DOWNLOAD_BYTES), MAX_DOWNLOAD_BYTES))
    raw = response.content
    if len(raw) > maximum:
        raise ValueError('download exceeds Computer limit')
    target = safe_path(args.get('destination'))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return {'url': response.url, 'path': rel(target), 'size_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def browser_state_path() -> Path:
    path = STATE / 'browser'
    path.mkdir(parents=True, exist_ok=True)
    return path


def browser_current_url() -> str | None:
    path = browser_state_path() / 'url.txt'
    if not path.is_file():
        return None
    value = path.read_text('utf-8').strip()
    return value or None


def save_browser_url(value: str) -> None:
    (browser_state_path() / 'url.txt').write_text(value, encoding='utf-8')


def locator(page: Any, selector: str):
    raw = str(selector or '').strip()
    if not raw:
        raise ValueError('selector is required')
    if raw.startswith('text='):
        return page.get_by_text(raw[5:], exact=False).first
    if raw.startswith('role='):
        spec = raw[5:]
        if '[name=' in spec and spec.endswith(']'):
            role, name = spec.split('[name=', 1)
            return page.get_by_role(role, name=name[:-1]).first
        return page.get_by_role(spec).first
    return page.locator(raw).first


def with_browser(action):
    network_allowed()
    from playwright.sync_api import sync_playwright

    state_dir = browser_state_path()
    storage = state_dir / 'storage.json'
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox', '--disable-dev-shm-usage'])
        context_args: dict[str, Any] = {}
        if storage.is_file():
            context_args['storage_state'] = str(storage)
        context = browser.new_context(**context_args)

        def guard(route, request):
            try:
                parsed = urlparse(request.url)
                if parsed.scheme in {'data', 'blob', 'about'}:
                    route.continue_()
                    return
                public_url(request.url)
                route.continue_()
            except Exception:
                route.abort()

        context.route('**/*', guard)
        page = context.new_page()
        current = browser_current_url()
        if current:
            page.goto(public_url(current), wait_until='domcontentloaded', timeout=60_000)
        result = action(page, context)
        context.storage_state(path=str(storage))
        save_browser_url(page.url)
        context.close()
        browser.close()
        return result


def browser_tool(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool == 'browser.open':
        network_allowed()
        browser_state_path()
        return {'state': 'ready', 'url': browser_current_url() or 'about:blank', 'engine': 'chromium-playwright'}
    if tool == 'browser.close':
        shutil.rmtree(browser_state_path(), ignore_errors=True)
        return {'state': 'closed'}

    def action(page, context):
        if tool == 'browser.navigate':
            url = public_url(str(args.get('url') or ''))
            wait_until = str(args.get('wait_until') or 'domcontentloaded')
            timeout = max(1, min(int(args.get('timeout_seconds') or 60), 900)) * 1000
            response = page.goto(url, wait_until=wait_until, timeout=timeout)
            return {'url': page.url, 'title': page.title(), 'status_code': response.status if response else None}
        if tool == 'browser.snapshot':
            maximum = max(1000, min(int(args.get('max_chars') or 40000), 100000))
            data = page.evaluate("""() => {
                const clean = s => String(s || '').replace(/\\s+/g,' ').trim();
                const items = [...document.querySelectorAll('a,button,input,textarea,select,[role]')].slice(0,500).map((el,i) => ({
                    index:i, tag:el.tagName.toLowerCase(), role:el.getAttribute('role') || '',
                    text:clean(el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').slice(0,300),
                    id:el.id || '', name:el.getAttribute('name') || '', href:el.getAttribute('href') || ''
                }));
                return {title:document.title,url:location.href,text:clean(document.body?.innerText || ''),interactive:items};
            }""")
            text = str(data.get('text') or '')
            data['text'] = text[:maximum]
            data['truncated'] = len(text) > maximum
            return data
        if tool == 'browser.click':
            locator(page, str(args.get('selector') or '')).click(timeout=max(1, min(int(args.get('timeout_seconds') or 30), 900)) * 1000)
            return {'url': page.url, 'title': page.title(), 'clicked': True}
        if tool == 'browser.type':
            loc = locator(page, str(args.get('selector') or ''))
            loc.fill(str(args.get('text') or ''), timeout=max(1, min(int(args.get('timeout_seconds') or 30), 900)) * 1000)
            if bool(args.get('press_enter')):
                loc.press('Enter')
            return {'url': page.url, 'typed': True}
        if tool == 'browser.press':
            key = str(args.get('key') or '')
            if args.get('selector'):
                locator(page, str(args.get('selector'))).press(key)
            else:
                page.keyboard.press(key)
            return {'url': page.url, 'pressed': key}
        if tool == 'browser.evaluate':
            expression = str(args.get('expression') or '')
            return {'url': page.url, 'value': page.evaluate(expression)}
        if tool == 'browser.screenshot':
            target = safe_path(args.get('path') or 'screenshots/page.png')
            if target.suffix.lower() != '.png':
                target = target.with_suffix('.png')
            target.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(target), full_page=bool(args.get('full_page', True)))
            return {'url': page.url, 'path': rel(target), 'size_bytes': target.stat().st_size}
        raise ValueError(f'unknown browser tool: {tool}')

    return with_browser(action)


def artifact_import(args: dict[str, Any]) -> dict[str, Any]:
    target = safe_path(args.get('path'))
    raw = base64.b64decode(str(args.get('content_base64') or ''), validate=True)
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise ValueError('artifact exceeds Computer import limit')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return {'path': rel(target), 'size_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'content_type': args.get('content_type')}


def artifact_export(args: dict[str, Any]) -> dict[str, Any]:
    target = safe_path(args.get('path'))
    if not target.is_file():
        raise FileNotFoundError('artifact file not found')
    maximum = max(1, min(int(args.get('max_bytes') or MAX_ARTIFACT_BYTES), MAX_ARTIFACT_BYTES))
    with target.open('rb') as handle:
        if os.fstat(handle.fileno()).st_size>maximum:
            raise ValueError('artifact exceeds Computer export limit')
        raw=handle.read(maximum+1)
    if len(raw) > maximum:
        raise ValueError('artifact exceeds Computer export limit')
    return {'path': rel(target), 'size_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'content_base64': base64.b64encode(raw).decode('ascii')}


def environment_info(_: dict[str, Any]) -> dict[str, Any]:
    commands = ['python3', 'node', 'npm', 'git', 'rg', 'jq', 'curl', 'wget', 'chromium', 'ffmpeg', 'docker']
    return {
        'workspace': str(ROOT),
        'python': sys.version.split()[0],
        'network_policy': network_policy(),
        'commands': {name: shutil.which(name) for name in commands},
        'profile': session_meta().get('profile'),
    }


def dispatch(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool == 'terminal.exec':
        return terminal_exec(args)
    if tool == 'python.exec':
        return python_exec(args)
    if tool == 'files.list':
        return files_list(args)
    if tool == 'files.read':
        return files_read(args)
    if tool == 'files.write':
        return files_write(args)
    if tool == 'files.mkdir':
        return files_mkdir(args)
    if tool == 'files.remove':
        return files_remove(args)
    if tool == 'files.move':
        return files_move(args)
    if tool == 'files.search':
        return files_search(args)
    if tool == 'process.list':
        return process_list(args)
    if tool == 'process.kill':
        return process_kill(args)
    if tool in {'git.status', 'git.diff', 'git.exec'}:
        return git_tool(tool, args)
    if tool == 'web.fetch':
        return web_fetch(args)
    if tool == 'web.download':
        return web_download(args)
    if tool.startswith('browser.'):
        return browser_tool(tool, args)
    if tool == 'artifact.import':
        return artifact_import(args)
    if tool == 'artifact.export':
        return artifact_export(args)
    if tool == 'environment.info':
        return environment_info(args)
    raise ValueError(f'unknown Computer tool: {tool}')



# Installed by a root-owned helper running as the scoped unprivileged UID.
# libseccomp's default native architecture filter rejects other ABI calls.
# Deny the network syscall family (including UNIX sockets), descriptor
# retrieval and io_uring, which could otherwise bypass individual checks.
# The irreversible no_new_privs/filter state is inherited across fork/exec.
_OFFLINE_SYSCALLS = (
    "socket", "socketpair", "connect", "bind", "listen", "accept", "accept4",
    "sendto", "sendmsg", "sendmmsg", "recvfrom", "recvmsg", "recvmmsg",
    "getsockopt", "setsockopt", "getsockname", "getpeername", "shutdown",
    "io_uring_setup", "io_uring_enter", "io_uring_register", "pidfd_getfd",
    "ptrace", "process_vm_readv", "process_vm_writev", "bpf",
    "unshare", "setns",
)
class OfflinePolicyError(RuntimeError):
    def __init__(self, code: int):
        super().__init__('Offline isolation not established')
        self.code = code


def install_offline_filter() -> None:
    # Close inherited descriptors other than stdin/stdout/stderr (the runner
    # supplies /dev/null and a root-owned output file). Failure is fatal.
    for name in os.listdir("/proc/self/fd"):
        fd = int(name)
        if fd > 2:
            try:
                os.close(fd)
            except OSError as error:
                if error.errno != errno.EBADF:
                    raise
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                           ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        raise OfflinePolicyError(91)
    try:
        lib = ctypes.CDLL("libseccomp.so.2")
    except OSError:
        raise OfflinePolicyError(92) from None
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_attr_set.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
    lib.seccomp_attr_set.restype = ctypes.c_int
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                     ctypes.c_int, ctypes.c_uint]
    lib.seccomp_rule_add.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.restype = None
    ctx = lib.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
    if not ctx:
        raise OfflinePolicyError(93)
    try:
        if lib.seccomp_attr_set(ctx, 2, 0x80000000) != 0:  # ACT_BADARCH: kill process
            raise OfflinePolicyError(94)
        for name in _OFFLINE_SYSCALLS:
            nr = lib.seccomp_syscall_resolve_name(name.encode("ascii"))
            # A negative pseudo-number denotes a non-native syscall. All
            # modern native syscall names above must resolve except accept
            # on architectures that implement accept4 only.
            if nr < 0:
                if name == "accept":
                    continue
                raise OfflinePolicyError(95)
            if lib.seccomp_rule_add(ctx, 0x00050000 | errno.EPERM, nr, 0) != 0:
                raise OfflinePolicyError(96)
        if lib.seccomp_load(ctx) != 0:
            raise OfflinePolicyError(97)
    finally:
        lib.seccomp_release(ctx)
    if libc.prctl(39, 0, 0, 0, 0) != 1:  # PR_GET_NO_NEW_PRIVS
        raise OfflinePolicyError(98)


def offline_probe() -> None:
    # Test direct socket creation and an exec'ed descendant. No traffic is sent.
    snippet = """import errno,socket
for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
    try:
        s=socket.socket(family,socket.SOCK_STREAM)
    except OSError as e:
        assert e.errno==errno.EPERM, e.errno
    else:
        s.close()
        raise RuntimeError("socket unexpectedly allowed")
try:
    a,b=socket.socketpair()
except OSError as e:
    assert e.errno==errno.EPERM, e.errno
else:
    a.close(); b.close()
    raise RuntimeError("socketpair unexpectedly allowed")
"""
    try:
        exec(compile(snippet, "<offline-probe>", "exec"), {})
    except Exception:
        raise OfflinePolicyError(99) from None
    child = subprocess.run([sys.executable, "-I", "-c", snippet],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=5, check=False)
    if child.returncode != 0:
        raise OfflinePolicyError(100)


def main() -> int:
    # Run this before reading any caller-controlled arguments or dispatching
    # a command; there is no unfiltered fallback path in scoped v2.
    try:
        if network_policy() != "off":
            raise RuntimeError("Offline policy required")
        install_offline_filter()
        if sys.argv[1:] == ["--offline-probe"]:
            offline_probe()
            print("DZ_OFFLINE_KERNEL_PROBE_PASS")
            return 0
    except Exception as error:
        # Only fixed numerical diagnostic codes are exposed, never exception text.
        emit({"ok":False,"error":"Offline isolation not established","error_type":"IsolationError"})
        if sys.argv[1:] == ["--offline-probe"]:
            return error.code if isinstance(error, OfflinePolicyError) else 90
        return 2
    if len(sys.argv) != 3:
        emit({'ok': False, 'error': 'usage: computer_tool.py TOOL REQUEST_JSON'})
        return 2
    tool, request_path = sys.argv[1], sys.argv[2]
    try:
        ROOT.mkdir(parents=True, exist_ok=True)
        STATE.mkdir(parents=True, exist_ok=True)
        result = dispatch(tool, load_args(request_path))
        emit({'ok': True, 'result': result})
        return 0
    except Exception as error:
        emit({'ok': False, 'error': str(error), 'error_type': type(error).__name__})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
