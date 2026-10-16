"""显式配置的空调控制入口；默认只在本地预览。"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from fractions import Fraction
import re
import tomllib


class ControlError(Exception):
    """可向用户安全显示的固定错误。"""


def number(value):
    try:
        if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
            raise ValueError
        text = str(value)
        if len(text) > 128:
            raise ValueError
        result = Decimal(text)
        if (not result.is_finite() or len(result.as_tuple().digits) > 32
                or abs(result.as_tuple().exponent) > 32
                or result.copy_abs() > Decimal('1000000')):
            raise ValueError
        return result
    except (ValueError, InvalidOperation):
        raise ControlError("数值必须是有限数字，不能是布尔值") from None


@dataclass(frozen=True)
class Config:
    device_id: str
    profile: str
    state_dir: Path
    timeout: float
    min_temperature: Decimal
    max_temperature: Decimal
    temperature_step: Decimal
    on_property: str
    temperature_property: str
    mode_property: str
    mode_cool: object = None
    mode_heat: object = None

    def temperature(self, value):
        result = number(value)
        try:
            valid = (self.min_temperature <= result <= self.max_temperature and
                     ((Fraction(result) - Fraction(self.min_temperature)) / Fraction(self.temperature_step)).denominator == 1)
        except InvalidOperation:
            valid = False
        if not valid:
            raise ControlError("温度超出配置范围或不符合步长")
        return result


def load_config(path):
    try:
        path = Path(path).resolve()
        data = tomllib.loads(path.read_text(encoding="utf-8-sig"), parse_float=Decimal)
        device = data['device_id']
        profile = data['profile']
        state = data['state_dir']
        if not isinstance(device, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', device):
            raise ValueError
        if device == 'REPLACE_WITH_DEVICE_ID':
            raise ValueError
        if not isinstance(profile, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', profile):
            raise ValueError
        if not isinstance(state, str) or not state.strip():
            raise ValueError
        state = (path.parent / state).resolve()
        for parent in (*Path(__file__).resolve().parents, *path.parents, state, *state.parents):
            if (parent / 'UPSTREAM.json').is_file() and state.is_relative_to(parent):
                raise ValueError
        timeout = number(data.get('timeout', 20))
        low, high, step = [number(data[k]) for k in
                           ('min_temperature', 'max_temperature', 'temperature_step')]
        if not 0 < timeout <= 120 or not low < high or not 0 < Fraction(step) <= Fraction(high)-Fraction(low):
            raise ValueError
        if ((Fraction(high)-Fraction(low))/Fraction(step)).denominator != 1:
            raise ValueError
        props = [data.get(k, 'air-conditioner.' + v) for k, v in
                 [('on_property','on'), ('temperature_property','target-temperature'),
                  ('mode_property','mode')]]
        if any(not isinstance(p, str) or not re.fullmatch(r'[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*',p) for p in props):
            raise ValueError
        if data.get('channel', 'cloud') != 'cloud':
            raise ValueError
        modes = [data.get('mode_cool'), data.get('mode_heat')]
        if None not in modes and modes[0] == modes[1]:
            raise ValueError
        for mode in modes:
            if mode is not None and (isinstance(mode, bool) or not isinstance(mode, int) or abs(mode) > 1000000):
                raise ValueError
        return Config(device, profile, state, float(timeout), low, high, step, *props, *modes)
    except (OSError, ValueError, KeyError, TypeError, InvalidOperation, ControlError):
        raise ControlError("配置无效：检查必填项、外部状态目录、cloud、范围和有限正超时") from None

import json
import os
import subprocess
import sys


def configure_utf8_stdio():
    """第一方入口统一输出 UTF-8；保留内存捕获流的行为。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')


class Controller:
    def __init__(self, config, runner=subprocess.run):
        self.config = config
        self.runner = runner

    def call(self, arguments, *, read=False):
        c = self.config
        args = [sys.executable, '-m', 'mijia_ac.upstream', '--device-id', c.device_id, '--',
                '--profile', c.profile, '--channel', 'cloud', '--timeout', str(c.timeout),
                '--output', 'json', *arguments]
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith('MI_')
               and k.upper() not in ('PYTHONPATH', 'PYTHONHOME')}
        env['MI_HOME_CONFIG_DIR'] = str(c.state_dir)
        env['PYTHONUTF8'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'
        try:
            result = self.runner(args, shell=False, timeout=c.timeout, env=env,
                                 capture_output=True, text=True, encoding='utf-8')
        except subprocess.TimeoutExpired:
            raise ControlError('云端操作超时；停止，不自动重试写入') from None
        except (OSError, UnicodeError):
            raise ControlError('上游进程无法启动或返回无法解码') from None
        if result.returncode:
            raise ControlError('上游操作失败；原始输出已隐藏，请在本地诊断')
        if not read:
            return None
        try:
            if len(result.stdout) > 65536:
                raise ValueError
            data = json.loads(result.stdout, parse_float=Decimal)
            if not isinstance(data, dict):
                raise ValueError
            return data
        except (ValueError, TypeError):
            raise ControlError('上游状态不是有效的受控 JSON') from None

    def status(self):
        c = self.config
        data = self.call(['get', c.device_id, c.on_property, c.temperature_property,
                          c.mode_property], read=True)
        on = data.get(c.on_property)
        mode = data.get(c.mode_property)
        if type(on) is not bool or type(mode) is not int or abs(mode) > 1000000:
            raise ControlError('回读缺少有效 on/mode；核对型号属性')
        temp = number(data.get(c.temperature_property))
        return {'on': on, 'temperature': temp, 'mode': mode}

    def write(self, prop, value):
        self.call(['--verify', 'set', self.config.device_id, f'{prop}={value}'])

    def execute(self, command, value, *, apply=False, allow_power_on=False):
        c = self.config
        if command == 'set-temp':
            target = c.temperature(value)
            exact = Fraction(target)
            raw = str(exact.numerator) if exact.denominator == 1 else format(target, 'f')
            prop = c.temperature_property
        elif command == 'power' and value in ('on', 'off'):
            target = value == 'on'
            prop, raw = c.on_property, str(target).lower()
        elif command == 'mode' and value in ('cool', 'heat'):
            target = c.mode_cool if value == 'cool' else c.mode_heat
            if target is None:
                raise ControlError('模式枚举未配置，请先核对设备 spec；制热未物理实测')
            prop, raw = c.mode_property, str(target)
        else:
            raise ControlError('不支持的操作或值')
        if not apply:
            return {'preview': True, 'command': command, 'value': str(value),
                    'allow_power_on': allow_power_on,
                    'note': '本地计划；尚未读取设备，未写入；apply 后独立回读'}
        if command in ('set-temp', 'mode'):
            before = self.status()
            if not before['on']:
                if not allow_power_on:
                    raise ControlError('设备已关机；设温或模式操作需要显式 --allow-power-on，操作已停止')
                self.write(c.on_property, 'true')
                if self.status()['on'] is not True:
                    raise ControlError('开机回读不匹配；停止，未继续设温或模式操作；设备可能已改变')
        self.write(prop, raw)
        actual = self.status()
        if command == 'set-temp':
            matches = actual['on'] is True and number(actual['temperature']) == target
        elif command == 'power':
            matches = actual['on'] is target
        else:
            matches = actual['mode'] == target and actual['on'] is True
        if not matches:
            raise ControlError('写入后独立回读不匹配；停止，不盲目重写；设备可能已改变')
        return actual


def main(argv=None):
    import argparse
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description='米家空调双向设温；默认本地预览')
    parser.add_argument('--config', required=True, help='显式 TOML 配置路径')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status', help='读取受控状态字段（需要网络）')
    for name, choices in [('set-temp', None), ('power', ['on','off']), ('mode', ['cool','heat'])]:
        sub = commands.add_parser(name)
        sub.add_argument('value', choices=choices)
        sub.add_argument('--apply', action='store_true', help='授权实际写入')
        if name in ('set-temp', 'mode'):
            sub.add_argument('--allow-power-on', action='store_true', help='授权关机时先开机')
    args = parser.parse_args(argv)
    try:
        controller = Controller(load_config(args.config))
        result = (controller.status() if args.command == 'status' else
                  controller.execute(args.command, args.value, apply=args.apply,
                                     allow_power_on=getattr(args, 'allow_power_on', False)))
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, default=lambda x: format(x, 'f') if isinstance(x, Decimal) else str(x)))
        return 0
    except ControlError as error:
        print(f'错误：{error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('操作中断；设备可能已改变，请人工核对', file=sys.stderr)
        return 130
