"""第二轮精确 DID 回归；仅真实上游对象的虚构内存数据。"""
import contextlib
import io
import json
import runpy
import subprocess
import sys

import pytest
from mi_home_cli.core.registry import Device, Registry
from mi_home_cli.errors import MiCliError
from mijia_ac.cli import Controller, ControlError
from test_control import config, state


class RegistryRunner:
    """不启动进程；执行 Controller 实际选择的入口与真实解析方法。"""

    def __init__(self, monkeypatch, registry):
        self.registry = registry
        self.writes = []
        self.calls = []
        import mi_home_cli.cli.app as app
        monkeypatch.setattr(app, 'main', self.upstream)

    def upstream(self):
        args = sys.argv[1:]
        verb = 'get' if 'get' in args else 'set'
        ref = args[args.index(verb) + 1]
        device = self.registry.resolve(ref, home_id='fixture-home')
        if verb == 'set':
            self.writes.append(device.did)
        print(json.dumps(state(on=False)))

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        previous = sys.argv
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                sys.argv = [args[2], *args[3:]]
                if args[1] == '-c':
                    exec(args[2], {'__name__': '__main__'})
                else:
                    runpy.run_module(args[2], run_name='__main__')
        except MiCliError:
            return subprocess.CompletedProcess(args, 1, 'fixture-sensitive', 'fixture-sensitive')
        except SystemExit as error:
            if error.code not in (None, 0):
                raise
        finally:
            sys.argv = previous
        return subprocess.CompletedProcess(args, 0, output.getvalue(), '')


def registry(*devices):
    result = Registry({})
    result.devices = list(devices)
    return result


def device(did='fixture-device', **overrides):
    values = dict(name='fixture-neutral', model='fixture-neutral-model', urn='fixture-urn',
                  online=True, home_id='fixture-home', room_name='fixture-room')
    values.update(overrides)
    return Device(did, **values)


@pytest.mark.parametrize('fields', [
    {'name': 'fixture-device'}, {'alias': 'fixture-device'},
    {'name': 'prefix-fixture-device-suffix'}, {'model': 'prefix-fixture-device-suffix'},
])
@pytest.mark.parametrize('command,value', [('power', 'off'), ('status', None),
                                          ('set-temp', '23'), ('mode', 'heat')])
def test_controlled_entry_blocks_real_upstream_fallback(tmp_path, monkeypatch, fields, command, value):
    other = device('fixture-other-device', **fields)
    r = registry(other)
    # 独立证明固定上游确实会回退；不 mock resolve 的结果。
    assert r.resolve('fixture-device', home_id='fixture-home') is other
    runner = RegistryRunner(monkeypatch, r)
    with pytest.raises(ControlError) as error:
        controller = Controller(config(tmp_path, 'mode_heat = 3\n'), runner)
        if command == 'status':
            controller.status()
        else:
            controller.execute(command, value, apply=True, allow_power_on=True)
    assert 'fixture-sensitive' not in str(error.value)
    assert not runner.writes
    assert len(runner.calls) == 1
    assert r.resolve('fixture-device', home_id='fixture-home') is other


def test_controlled_entry_exact_did_works(tmp_path, monkeypatch):
    runner = RegistryRunner(monkeypatch, registry(device()))
    result = Controller(config(tmp_path), runner).execute('power', 'off', apply=True)
    assert result['on'] is False
    assert runner.writes == ['fixture-device']
    assert len(runner.calls) == 2


@pytest.mark.parametrize('devices', [
    [], [device(home_id='fixture-other-home')], [device(), device()],
])
def test_controlled_entry_missing_filtered_duplicate_refuses(tmp_path, monkeypatch, devices):
    runner = RegistryRunner(monkeypatch, registry(*devices))
    with pytest.raises(ControlError):
        Controller(config(tmp_path), runner).execute('power', 'off', apply=True)
    assert not runner.writes


def test_each_process_rebinds_after_registry_changes(tmp_path, monkeypatch):
    r = registry(device())
    runner = RegistryRunner(monkeypatch, r)

    def changing_runner(args, **kwargs):
        if runner.calls:
            r.devices = [device('fixture-other-device', name='fixture-device')]
        return runner(args, **kwargs)

    with pytest.raises(ControlError):
        Controller(config(tmp_path), changing_runner).execute('power', 'off', apply=True)
    assert runner.writes == ['fixture-device']
    assert len(runner.calls) == 2


@pytest.mark.parametrize('ref', ['fixture-other-device', ' fixture-device ', 'FIXTURE-DEVICE',
                              'fixture-room/fixture-device'])
def test_entry_rejects_ref_other_than_bound_did(monkeypatch, ref):
    from mijia_ac.upstream import main
    from mi_home_cli.errors import DeviceNotFound
    import mi_home_cli.cli.app as app
    r = registry(device(), device('fixture-other-device'))

    def upstream():
        with pytest.raises(DeviceNotFound):
            r.resolve(ref)

    monkeypatch.setattr(app, 'main', upstream)
    main(['--device-id', 'fixture-device', '--', '--help'])


@pytest.mark.parametrize('arguments', [[], ['--device-id', 'fixture-device', '--', '--help']])
def test_entry_help_without_account(arguments):
    result = subprocess.run([sys.executable, '-m', 'mijia_ac.upstream', *(arguments or ['--help'])],
                            capture_output=True, text=True, timeout=15, shell=False)
    assert result.returncode == 0
    assert '--device-id' in result.stdout if not arguments else '--profile' in result.stdout


def test_real_upstream_objects_match_fixed_vendor_bytes():
    import hashlib
    import inspect
    from pathlib import Path
    from mi_home_cli.core.spec import Property, parse_value
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'UPSTREAM.json').read_text(encoding='utf-8'))
    for obj, relative in [(Registry, 'core/registry.py'), (Device, 'core/registry.py'),
                          (Property, 'core/spec.py'), (parse_value, 'core/spec.py')]:
        digest = hashlib.sha256(Path(inspect.getfile(obj)).read_bytes()).hexdigest()
        assert digest == manifest['files']['src/mi_home_cli/' + relative]
