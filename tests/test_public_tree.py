"""公开树检查器的所有构造内容均为 fixture。"""
from pathlib import Path
import hashlib
import json
import importlib.util
import pytest

ROOT = Path(__file__).resolve().parents[1]


def checker():
    spec = importlib.util.spec_from_file_location('public_check', ROOT/'tools/check_public_tree.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.mark.parametrize('name', [
    'auth.json', 'nested/token.json', '.env', 'state/devices.json',
    '.venv/file.py', 'reports/result.txt', 'config.toml',
    'mijia-ac-private/notes.txt', 'debug.log', 'account.local.json', 'state.sqlite',
])
def test_reject_sensitive_names(tmp_path, name):
    p=tmp_path/name
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text('fixture',encoding='utf-8')
    assert checker().inspect_paths(tmp_path,[name])


def test_reject_private_path_and_device_binding(tmp_path):
    p=tmp_path/'bad.toml'
    # 故意构造的虚构用户路径，不来自当前机器。
    p.write_text('state_dir = "C:/'+ 'Users/fixture-user/state"\ndevice_' + 'id = "123456789012"',encoding='utf-8')
    assert checker().inspect_paths(tmp_path,['bad.toml'])


def test_legitimate_vendor_auth_code_allowed():
    assert not checker().inspect_paths(ROOT,['vendor/mi-home-cli/src/mi_home_cli/cli/auth.py'])


def test_vendor_manifest():
    manifest=json.loads((ROOT/'UPSTREAM.json').read_text(encoding='utf-8'))
    base=ROOT/manifest['source_path']
    actual={p.relative_to(base).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in base.rglob('*') if p.is_file()}
    assert actual == manifest['files']
    assert manifest['commit'] == 'c1a42765a7ad5f53ce5cd9296b877a26671f1f5f'
    assert 'slightc' in (base/'LICENSE').read_text(encoding='utf-8')


def test_actual_public_tree():
    module=checker()
    assert not module.inspect_paths(ROOT,module.candidate_paths(ROOT))


def test_vendor_bytes_lf_and_attributes():
    assert (ROOT/'.gitattributes').is_file()
    assert 'vendor/** -text' in (ROOT/'.gitattributes').read_text()
    manifest = json.loads((ROOT/'UPSTREAM.json').read_text())
    assert all(b'\r\n' not in (ROOT/manifest['source_path']/n).read_bytes() for n in manifest['files'])


@pytest.fixture
def fixture_repo():
    import os, tempfile, subprocess
    scratch = Path(os.environ.get('LOCALAPPDATA', tempfile.gettempdir()))/'hermes/cache/scratch'
    scratch.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='mijia-public-fixture-', dir=scratch))
    subprocess.run(['git','init','-q',str(root)], check=True, capture_output=True)
    def git(*args, data=None):
        return subprocess.run(['git',*args], cwd=root, input=data, capture_output=True, check=True).stdout
    return root, git


def test_staged_secret_clean_worktree(fixture_repo):
    root, git = fixture_repo
    p = root/'example.py'
    # 显式虚构 secret，仅测试扫描；不是可用授权。
    p.write_text('access_to' + 'ken = "fixture-unapproved-secret-123456"\n')
    git('add','example.py')
    p.write_text('# cleaned fixture\n')
    issues = checker().inspect_candidates(root)
    assert any('凭据' in reason for _, reason in issues)
    assert any('暂存' in reason for _, reason in issues)


def test_staged_symlink_rejected(fixture_repo):
    root, git = fixture_repo
    oid = git('hash-object','-w','--stdin', data=b'fixture-target').decode().strip()
    git('update-index','--add','--cacheinfo',f'120000,{oid},link.txt')
    (root/'link.txt').write_text('ordinary fixture worktree')
    assert any('模式' in reason for _, reason in checker().inspect_candidates(root))


def test_untracked_candidate_checked(fixture_repo):
    root, _ = fixture_repo
    (root/'new.py').write_text('device_' + 'id = "fixture-unapproved-device"')
    assert checker().inspect_candidates(root)


def test_index_vendor_mismatch(fixture_repo):
    root, git = fixture_repo
    (root/'vendor').mkdir()
    (root/'vendor/file.txt').write_bytes(b'official fixture\n')
    manifest = {'source_path':'vendor', 'files':{'file.txt':hashlib.sha256(b'official fixture\n').hexdigest()}}
    (root/'UPSTREAM.json').write_text(json.dumps(manifest))
    git('add','.')
    (root/'vendor/file.txt').write_bytes(b'changed fixture\n')
    assert checker().verify_vendor(root, index=True)
    assert not checker().verify_vendor(root)
    assert checker().inspect_candidates(root)


def test_fixture_word_not_file_exemption(tmp_path):
    (tmp_path/'tests').mkdir()
    p = tmp_path/'tests/test_fixture.py'
    p.write_text('# fixture\ndevice_' + 'id = "fixture-unapproved-device"\naccess_to' + 'ken = "fixture-unapproved-secret-123456"')
    issues = checker().inspect_paths(tmp_path,['tests/test_fixture.py'])
    assert any('设备' in r for _, r in issues)
    assert any('凭据' in r for _, r in issues)


def test_vendor_directory_not_blanket_exempt(tmp_path):
    p=tmp_path/'vendor/mi-home-cli/unreviewed.py'
    p.parent.mkdir(parents=True)
    p.write_text('access_to' + 'ken = "fixture-unapproved-secret-123456"')
    assert checker().inspect_paths(tmp_path,['vendor/mi-home-cli/unreviewed.py'])


def test_git_canonical_text_not_false_drift(fixture_repo):
    root, git = fixture_repo
    (root/'.gitattributes').write_bytes(b'* text=auto eol=lf\nvendor/** -text\n')
    (root/'fixture.txt').write_bytes(b'fictional fixture\n')
    git('add','.')
    (root/'fixture.txt').write_bytes(b'fictional fixture\r\n')
    assert not checker().inspect_candidates(root)
