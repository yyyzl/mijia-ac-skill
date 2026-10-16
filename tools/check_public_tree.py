"""检查 git 已跟踪及未忽略的拟发布文件；不读取凭据文件内容。"""
from pathlib import Path, PurePosixPath
import hashlib
import json
import re
import subprocess
import sys


# 固定上游文档的示例绑定值仅按官方 blob 的 SHA256 放行；修改即失效。
UPSTREAM_EXAMPLES = {'vendor/mi-home-cli/docs/camera-stream.md': '48450136c17d17446796a95bebe1d2e00b4a8cfb9270235bb4883d2690b06e04'}


def candidate_paths(root):
    result = subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z'],
                            cwd=root, capture_output=True, timeout=15, shell=False)
    if result.returncode:
        raise ValueError('无法枚举 git 发布候选树')
    return sorted(set(result.stdout.decode('utf-8').split('\0')) - {''})


def inspect_paths(root, paths, blobs=None):
    root = Path(root).resolve()
    problems = []
    private = re.compile(r'(?i)(?:[a-z]:[/\\]+us' + r'ers[/\\]+[^/\\\s"\']+|(?<![A-Za-z0-9_/])/(?:home|Us' + r'ers)/[^/\s"\']+)')
    for name in paths:
        rel = PurePosixPath(name.replace('\\','/'))
        parts = [s.lower() for s in rel.parts]
        base = parts[-1] if parts else ''
        forbidden = (rel.is_absolute() or '..' in parts or
                     any(s in {'.git','.venv','venv','__pycache__','.pytest_cache','reports','state'}
                         or s.endswith('-state') for s in parts) or
                     base in {'auth.json','devices.json','config.toml'} or
                     base.startswith(('.env','credentials','config.local.')) or
                     base.endswith(('.local.toml','.pem','.key','.pyc')) or
                     ('token' in base and base.endswith('.json')))
        if forbidden:
            problems.append((name,'禁止发布的本地文件'))
            continue
        path = root / rel
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            problems.append((name,'拒绝链接或越界路径'))
            continue
        try:
            content = (blobs[name] if blobs is not None else path.read_bytes()).decode('utf-8-sig')
        except (OSError, UnicodeError):
            problems.append((name,'无法审查文本文件'))
            continue
        if private.search(content):
            problems.append((name,'检测到私人用户目录'))
        # 上游认证实现是合法源码；不把字段名 token 误判为凭据。
        upstream_example = (UPSTREAM_EXAMPLES.get(str(rel)) == hashlib.sha256(content.encode('utf-8')).hexdigest())
        for match in re.finditer(r'(?i)["\']?(?:device_id|did)["\']?\s*[:=]\s*["\']([^"\'\n]+)["\']', content):
            if not upstream_example and match.group(1) not in {'REPLACE_WITH_DEVICE_ID', 'fixture-device'}:
                problems.append((name,'检测到设备绑定值'))
        if re.search(r'(?i)["\']?(?:token|access_token|refresh_token|client_secret)["\']?\s*[:=]\s*["\'][^"\'\n]+["\']',content):
            problems.append((name,'检测到疑似凭据值'))
        if ('-----BEGIN ' + 'PRIVATE KEY-----') in content:
            problems.append((name,'检测到私钥'))
    return problems


def git(root, *args):
    result = subprocess.run(['git', *args], cwd=root, capture_output=True, timeout=15, shell=False)
    if result.returncode:
        raise ValueError('无法读取 Git 发布快照')
    return result.stdout


def index_entries(root):
    entries = {}
    for row in git(root, 'ls-files', '--stage', '-z').split(b'\0'):
        if not row:
            continue
        header, name = row.split(b'\t', 1)
        mode, oid, stage = header.decode().split()
        if stage != '0':
            raise ValueError('暂存区存在未解决冲突')
        entries[name.decode('utf-8')] = (mode, oid)
    return entries


def inspect_candidates(root):
    root = Path(root)
    entries = index_entries(root)
    issues = []
    blobs = {}
    for name, (mode, oid) in entries.items():
        if mode not in ('100644', '100755'):
            issues.append((name, '拒绝暂存文件模式（链接或 gitlink）'))
            continue
        blobs[name] = git(root, 'cat-file', 'blob', oid)
        path = root/name
        # 一般文本按 Git attributes 的规范字节比较；vendor -text 仍逐字节比较。
        if (path.is_symlink() or not path.is_file() or
                git(root, 'hash-object', '--path=' + name, '--', name).decode().strip() != oid):
            issues.append((name, '暂存快照与工作树不同；请审查后重新暂存'))
    issues.extend(inspect_paths(root, list(blobs), blobs))
    issues.extend(inspect_paths(root, [p for p in candidate_paths(root) if p not in entries]))
    return issues


def verify_vendor(root, *, index=False):
    root = Path(root)
    if index:
        entries = index_entries(root)
        def read(name):
            mode, oid = entries[name]
            if mode not in ('100644', '100755'):
                raise ValueError('vendor 暂存模式无效')
            return git(root, 'cat-file', 'blob', oid)
        manifest = json.loads(read('UPSTREAM.json'))
        prefix = manifest['source_path'] + '/'
        actual = {n[len(prefix):]: hashlib.sha256(read(n)).hexdigest()
                  for n in entries if n.startswith(prefix)}
    else:
        manifest = json.loads((root/'UPSTREAM.json').read_text(encoding='utf-8'))
        base = root/manifest['source_path']
        actual = {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in base.rglob('*') if p.is_file()}
    return actual == manifest['files']


def main():
    root = Path(__file__).resolve().parents[1]
    try:
        paths = candidate_paths(root)
        issues = inspect_candidates(root)
        if not verify_vendor(root) or not verify_vendor(root, index=True):
            issues.append(('vendor/mi-home-cli','SHA256 清单不匹配'))
        for path, reason in issues:
            print(f'{path}: {reason}', file=sys.stderr)
        if issues:
            return 1
        print(f'公开树检查通过：{len(paths)} 个候选文件；vendor SHA256 完整')
        return 0
    except (ValueError, KeyError, OSError, subprocess.TimeoutExpired):
        print('公开检查失败：无法完整检查候选树',file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
