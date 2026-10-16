import pytest
from mijia_ac.cli import load_config, ControlError

def test_missing_config(tmp_path):
    with pytest.raises(ControlError):
        load_config(tmp_path / "missing.toml")

# 以下所有值均为虚构 fixture。
BASE = '''device_id = "fixture-device"
profile = "fixture"
state_dir = "../fixture-state"
min_temperature = 16
max_temperature = 30
temperature_step = 0.5
'''

def config(tmp_path, extra=""):
    p = tmp_path / "fixture.toml"
    p.write_text(BASE + extra, encoding="utf-8")
    return load_config(p)

def test_relative_state(tmp_path):
    c = config(tmp_path)
    assert c.state_dir == (tmp_path / "../fixture-state").resolve()

@pytest.mark.parametrize("key,value", [
    ("timeout", "true"), ("timeout", "nan"), ("timeout", "inf"),
    ("timeout", "0"), ("timeout", "-1"), ("channel", '"lan"'),
    ("profile", '"../escape"'), ("device_id", '""'),
    ("temperature_step", "0"), ("temperature_step", "true"),
    ("min_temperature", "nan"), ("max_temperature", "15"),
])
def test_invalid_config(tmp_path, key, value):
    lines = [s for s in BASE.splitlines() if not s.startswith(key + " =")]
    p = tmp_path / "fixture.toml"
    p.write_text("\n".join(lines) + f"\n{key} = {value}\n", encoding="utf-8")
    with pytest.raises(ControlError):
        load_config(p)

@pytest.mark.parametrize("value", [True, "NaN", "Inf", "-Inf", "15", "30.5", "20.1", "x"])
def test_bad_temperature(tmp_path, value):
    with pytest.raises(ControlError):
        config(tmp_path).temperature(value)

def test_decimal_step(tmp_path):
    assert str(config(tmp_path).temperature("23.5")) == "23.5"

class FakeRunner:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def __call__(self, args, **kwargs):
        import subprocess, json
        self.calls.append((args, kwargs))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return subprocess.CompletedProcess(args, 0, json.dumps(reply), "secret-fixture-must-not-leak")


def state(on=True, temp=24, mode=2):
    return {"air-conditioner.on": on, "air-conditioner.target-temperature": temp,
            "air-conditioner.mode": mode, "fixture-secret": "must-not-leak"}


def test_status_safe_and_subprocess_contract(tmp_path):
    from mijia_ac.cli import Controller
    import sys
    runner = FakeRunner([state()])
    c = config(tmp_path)
    assert Controller(c, runner).status() == {"on": True, "temperature": 24, "mode": 2}
    args, kw = runner.calls[0]
    assert args[:6] == [sys.executable, '-m', 'mijia_ac.upstream', '--device-id', c.device_id, '--']
    assert args[args.index('--profile')+1] == 'fixture'
    assert args[args.index('--channel')+1] == 'cloud'
    assert args[args.index('--output')+1] == 'json'
    assert '--timeout' in args and args[-4:] == ['fixture-device', c.on_property, c.temperature_property, c.mode_property]
    assert kw['shell'] is False and kw['timeout'] == c.timeout
    assert kw['env']['MI_HOME_CONFIG_DIR'] == str(c.state_dir)

@pytest.mark.parametrize('reply', [{}, {'air-conditioner.on': 'false'}, state(temp=True)])
def test_invalid_readback(tmp_path, reply):
    from mijia_ac.cli import Controller
    with pytest.raises(ControlError):
        Controller(config(tmp_path), FakeRunner([reply])).status()

@pytest.mark.parametrize('command,value', [('set-temp','23.5'), ('power','off'), ('mode','heat')])
def test_preview_never_calls_runner(tmp_path, command, value):
    from mijia_ac.cli import Controller
    runner = FakeRunner([])
    result = Controller(config(tmp_path, 'mode_heat = 3\n'), runner).execute(command, value)
    assert result['preview'] is True
    assert runner.calls == []


def test_off_without_permission_refuses(tmp_path):
    from mijia_ac.cli import Controller
    runner = FakeRunner([state(on=False)])
    with pytest.raises(ControlError, match='allow-power-on'):
        Controller(config(tmp_path), runner).execute('set-temp', '23', apply=True)
    assert len(runner.calls) == 1


def test_authorized_power_on_sequence(tmp_path):
    from mijia_ac.cli import Controller
    runner = FakeRunner([state(on=False), {}, state(), {}, state(temp=23.5)])
    result = Controller(config(tmp_path), runner).execute('set-temp','23.5',apply=True,allow_power_on=True)
    assert result['temperature'] == 23.5 and result['on'] is True
    args = [a for a,k in runner.calls]
    assert ['get' if 'get' in a else 'set' for a in args] == ['get','set','get','set','get']
    assert args[1][-1] == 'air-conditioner.on=true'
    assert args[3][-1] == 'air-conditioner.target-temperature=23.5'
    assert all('--verify' in args[i] for i in (1,3))

@pytest.mark.parametrize('initial,after,permission,count', [
    (state(on=False), state(on=False), True, 3),
    (state(), state(temp=25), False, 3),
    (state(), state(on=False,temp=23), False, 3),
])
def test_set_mismatch_stops(tmp_path, initial, after, permission, count):
    from mijia_ac.cli import Controller
    runner = FakeRunner([initial, {}, after])
    with pytest.raises(ControlError, match='回读'):
        Controller(config(tmp_path),runner).execute('set-temp','23',apply=True,allow_power_on=permission)
    assert len(runner.calls) == count

@pytest.mark.parametrize('command,value,after', [('power','off',state(on=False)), ('mode','heat',state(mode=3)), ('mode','cool',state(mode=2))])
def test_power_and_mode_verify(tmp_path, command, value, after):
    from mijia_ac.cli import Controller
    runner = FakeRunner(([state()] if command == 'mode' else []) + [{}, after])
    Controller(config(tmp_path,'mode_cool = 2\nmode_heat = 3\n'),runner).execute(command,value,apply=True)
    assert len(runner.calls) == (3 if command == 'mode' else 2)
    assert '--verify' in runner.calls[-2][0]


def test_mode_mismatch(tmp_path):
    from mijia_ac.cli import Controller
    with pytest.raises(ControlError, match='回读'):
        Controller(config(tmp_path,'mode_heat = 3\n'),FakeRunner([state(),{},state()])).execute('mode','heat',apply=True)


def test_mode_requires_spec_enum(tmp_path):
    from mijia_ac.cli import Controller
    with pytest.raises(ControlError):
        Controller(config(tmp_path),FakeRunner([])).execute('mode','heat')


def test_cli_requires_config(capsys):
    from mijia_ac.cli import main
    with pytest.raises(SystemExit) as e:
        main(['status'])
    assert e.value.code != 0


def test_cli_preview_and_error(tmp_path, capsys):
    from mijia_ac.cli import main
    config(tmp_path)
    p = str(tmp_path/'fixture.toml')
    assert main(['--config',p,'set-temp','23']) == 0
    assert '"preview": true' in capsys.readouterr().out
    assert main(['--config',p,'set-temp','NaN']) != 0
    assert 'Traceback' not in capsys.readouterr().err


def test_installed_help():
    import subprocess, shutil
    executable = shutil.which('mijia-ac')
    # pytest 可由 venv Python 直接运行，不要求调用者修改 PATH。
    if executable is None:
        import sys
        from pathlib import Path
        executable = str(Path(sys.executable).parent / ('mijia-ac.exe' if sys.platform=='win32' else 'mijia-ac'))
    result = subprocess.run([executable, '--help'],capture_output=True,text=True,timeout=15,shell=False)
    assert result.returncode == 0 and 'set-temp' in result.stdout

@pytest.mark.parametrize('failure', ['timeout','cloud','invalid-json'])
def test_upstream_failure_safe(tmp_path, failure):
    import subprocess
    from mijia_ac.cli import Controller
    def runner(args, **kw):
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(args,kw['timeout'],output='fixture-sensitive')
        return subprocess.CompletedProcess(args, 7 if failure=='cloud' else 0,
                                           'fixture-sensitive', 'fixture-sensitive')
    with pytest.raises(ControlError) as e:
        Controller(config(tmp_path),runner).status()
    assert 'fixture-sensitive' not in str(e.value)

@pytest.mark.parametrize('value', ['23;echo bad','$(echo bad)','23\n24'])
def test_shell_input_rejected(tmp_path, value):
    from mijia_ac.cli import Controller
    runner = FakeRunner([])
    with pytest.raises(ControlError):
        Controller(config(tmp_path), runner).execute('set-temp',value,apply=True)
    assert not runner.calls


def test_repo_state_rejected(tmp_path):
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    p = tmp_path/'fixture.toml'
    p.write_text(BASE.replace('../fixture-state',repo.as_posix()),encoding='utf-8')
    with pytest.raises(ControlError):
        load_config(p)

@pytest.mark.parametrize('value',['1e1000000','-1e1000000'])
def test_extreme_numeric_input_safe(tmp_path,value):
    with pytest.raises(ControlError):
        config(tmp_path).temperature(value)


def test_mode_enums_cannot_alias(tmp_path):
    with pytest.raises(ControlError):
        config(tmp_path,'mode_cool = 2\nmode_heat = 2\n')


def test_temperature_config_keeps_decimal_precision(tmp_path):
    p=tmp_path/'fixture.toml'
    p.write_text(BASE.replace('temperature_step = 0.5','temperature_step = 0.10000000000000001'),encoding='utf-8')
    # 范围14不能被该步长整除；浮点舍入成0.1将错误接受。
    with pytest.raises(ControlError):
        load_config(p)


def test_installed_wheel_also_rejects_repo_state(tmp_path, monkeypatch):
    import mijia_ac.cli as cli
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    monkeypatch.setattr(cli,'__file__',str(tmp_path/'installed/mijia_ac/cli.py'))
    # 本项目真实配置未创建；复用现有无凭据配置示例并检查其目录边界。
    # 直接给 load_config 注入虚构 TOML，避免创建仓库中的真实配置文件。
    data=BASE.replace('../fixture-state','./fixture-state')
    original=Path.read_text
    def read(path, *args, **kw):
        if path == root/'config.fixture.toml':
            return data
        return original(path,*args,**kw)
    monkeypatch.setattr(Path,'read_text',read)
    with pytest.raises(ControlError):
        cli.load_config(root/'config.fixture.toml')

# 本次修复回归：全部为虚构 fixture。
def verbs(runner):
    return [('get' if 'get' in a else 'set', a[-1]) for a, _ in runner.calls]


def test_mode_off_without_permission_zero_writes(tmp_path):
    from mijia_ac.cli import Controller
    r = FakeRunner([state(on=False), {}, state(mode=3)])
    with pytest.raises(ControlError, match='allow-power-on'):
        Controller(config(tmp_path, 'mode_heat = 3\n'), r).execute('mode', 'heat', apply=True)
    assert [v for v, _ in verbs(r)] == ['get']


def test_mode_authorized_order(tmp_path):
    from mijia_ac.cli import Controller
    r = FakeRunner([state(on=False), {}, state(), {}, state(mode=3)])
    Controller(config(tmp_path, 'mode_heat = 3\n'), r).execute('mode', 'heat', apply=True, allow_power_on=True)
    assert [v for v, _ in verbs(r)] == ['get', 'set', 'get', 'set', 'get']
    assert verbs(r)[1][1] == 'air-conditioner.on=true'
    assert verbs(r)[3][1] == 'air-conditioner.mode=3'


def test_mode_correct_but_power_wrong(tmp_path):
    from mijia_ac.cli import Controller
    r = FakeRunner([state(), {}, state(on=False, mode=3)])
    with pytest.raises(ControlError, match='回读'):
        Controller(config(tmp_path, 'mode_heat = 3\n'), r).execute('mode', 'heat', apply=True)
    assert [v for v, _ in verbs(r)] == ['get', 'set', 'get']


@pytest.mark.parametrize('value', ['23.0000000000000000000000000001', '30.0000000000000000000000000001', '1e-1000000', '2' * 1000])
def test_precision_inputs_before_process(tmp_path, value):
    from mijia_ac.cli import Controller
    r = FakeRunner([])
    with pytest.raises(ControlError):
        Controller(config(tmp_path), r).execute('set-temp', value, apply=True)
    assert not r.calls


def test_precision_config_range(tmp_path):
    p = tmp_path/'fixture.toml'
    p.write_text(BASE.replace('max_temperature = 30', 'max_temperature = 30.0000000000000000000000000001'), encoding='utf-8')
    with pytest.raises(ControlError):
        load_config(p)


def test_exact_json_readback_mismatch(tmp_path):
    import subprocess
    from mijia_ac.cli import Controller
    r = FakeRunner([state(), {}, state()])
    def run(args, **kw):
        result = r(args, **kw)
        if len(r.calls) == 3:
            result.stdout = '{"air-conditioner.on":true,"air-conditioner.mode":2,"air-conditioner.target-temperature":23.000000000000001}'
        return result
    with pytest.raises(ControlError, match='回读'):
        Controller(config(tmp_path), run).execute('set-temp', '23', apply=True)
    assert len(r.calls) == 3


def test_external_config_noneditable_repo_state(tmp_path, monkeypatch):
    import mijia_ac.cli as cli
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(cli, '__file__', str(tmp_path/'installed/cli.py'))
    p = tmp_path/'fixture.toml'
    p.write_text(BASE.replace('../fixture-state', (root/'fixture-state').as_posix()), encoding='utf-8')
    with pytest.raises(ControlError):
        load_config(p)


def test_state_symlink_repo(tmp_path, monkeypatch):
    import mijia_ac.cli as cli
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    link = tmp_path/'fixture-link'
    try:
        link.symlink_to(root, target_is_directory=True)
    except OSError:
        pytest.skip('当前 Windows 无创建目录 symlink 权限；未执行链接用例')
    monkeypatch.setattr(cli, '__file__', str(tmp_path/'installed/cli.py'))
    p = tmp_path/'fixture.toml'
    p.write_text(BASE.replace('../fixture-state', link.as_posix()), encoding='utf-8')
    with pytest.raises(ControlError):
        load_config(p)


@pytest.mark.parametrize('failure', ['set-nonzero', 'get-timeout', 'temp-after-on'])
def test_failure_sequence_stops_and_redacts(tmp_path, failure):
    import subprocess
    from mijia_ac.cli import Controller
    r = FakeRunner([state(on=False), {}, state(), {}, state(temp=23)])
    limit = {'set-nonzero': 2, 'get-timeout': 3, 'temp-after-on': 4}[failure]
    def run(args, **kw):
        result = r(args, **kw)
        if len(r.calls) == limit:
            if failure == 'get-timeout':
                raise subprocess.TimeoutExpired(args, 1, output='fixture-sensitive')
            result.returncode = 7
            result.stdout = result.stderr = 'fixture-sensitive'
        return result
    with pytest.raises(ControlError) as error:
        Controller(config(tmp_path), run).execute('set-temp', '23', apply=True, allow_power_on=True)
    assert 'fixture-sensitive' not in str(error.value)
    assert [v for v, _ in verbs(r)] == ['get', 'set', 'get', 'set'][:limit]
    expected = [
        ['get', 'fixture-device', 'air-conditioner.on', 'air-conditioner.target-temperature', 'air-conditioner.mode'],
        ['set', 'fixture-device', 'air-conditioner.on=true'],
        ['get', 'fixture-device', 'air-conditioner.on', 'air-conditioner.target-temperature', 'air-conditioner.mode'],
        ['set', 'fixture-device', 'air-conditioner.target-temperature=23'],
    ]
    assert [a[a.index('get' if 'get' in a else 'set'):] for a, _ in r.calls] == expected[:limit]


@pytest.mark.parametrize('value', ['23', '23.0', '23.00', '23e0'])
@pytest.mark.parametrize('initially_on', [True, False])
def test_integer_temperature_real_upstream_parser(tmp_path, value, initially_on):
    from mi_home_cli.core.spec import Property, parse_value
    from mijia_ac.cli import Controller
    prop = Property(2, 3, 'target-temperature', '虚构温度', 'uint8',
                    ['read', 'write'], 'air-conditioner', value_range=[16, 30, 1])
    replies = ([state(), {}, state(temp=23)] if initially_on else
               [state(on=False), {}, state(), {}, state(temp=23)])
    fake = FakeRunner(replies)
    parsed = []

    def runner(args, **kwargs):
        if 'set' in args and args[-1].startswith(prop.full_name + '='):
            # 直接接入固定上游整数解析；原先 23.0/23.00 在这里真实失败。
            parsed.append(parse_value(prop, args[-1].split('=', 1)[1]))
        return fake(args, **kwargs)

    result = Controller(config(tmp_path), runner).execute(
        'set-temp', value, apply=True, allow_power_on=not initially_on)
    assert result['temperature'] == 23
    assert parsed == [23] and type(parsed[0]) is int
    assert verbs(fake) == ([('get', 'air-conditioner.mode'),
                            ('set', 'air-conditioner.target-temperature=23'),
                            ('get', 'air-conditioner.mode')] if initially_on else
                           [('get', 'air-conditioner.mode'), ('set', 'air-conditioner.on=true'),
                            ('get', 'air-conditioner.mode'), ('set', 'air-conditioner.target-temperature=23'),
                            ('get', 'air-conditioner.mode')])


def test_fractional_temperature_serialization_is_lossless(tmp_path):
    from dataclasses import replace
    from decimal import Decimal, localcontext
    from mijia_ac.cli import Controller
    value = '23.12345678901234567890123456789'
    c = replace(config(tmp_path), temperature_step=Decimal('1e-29'))
    fake = FakeRunner([state(), {}, state(temp=value)])
    with localcontext() as context:
        context.prec = 6
        Controller(c, fake).execute('set-temp', value, apply=True)
    assert fake.calls[1][0][-1] == 'air-conditioner.target-temperature=' + value
