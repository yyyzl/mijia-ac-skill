"""在每个受控子进程内绑定精确 DID，不改变固定上游源码。"""
import argparse
import sys

from .cli import configure_utf8_stdio


def main(argv=None):
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description='受控上游入口：仅允许指定的精确 DID')
    parser.add_argument('--device-id', required=True, help='配置指定的精确 DID')
    parser.add_argument('arguments', nargs=argparse.REMAINDER, help='-- 后的上游参数')
    args = parser.parse_args(argv)
    if not args.arguments or args.arguments[0] != '--':
        parser.error('必须以 -- 分隔上游参数')

    from mi_home_cli.core.registry import Registry
    from mi_home_cli.errors import AmbiguousReference, DeviceNotFound
    from mi_home_cli.cli.app import main as upstream_main

    def resolve(registry, ref, **filters):
        if ref != args.device_id:
            raise DeviceNotFound('受控入口拒绝非指定 DID')
        matches = [device for device in registry.devices if device.did == args.device_id]
        if len(matches) > 1:
            raise AmbiguousReference('指定 DID 不唯一；停止操作')
        if not matches or not any(device is matches[0] for device in registry.filter(**filters)):
            raise DeviceNotFound('过滤条件下不存在指定 DID；停止操作')
        return matches[0]

    previous_resolve, previous_argv = Registry.resolve, sys.argv
    try:
        Registry.resolve = resolve
        sys.argv = [previous_argv[0], *args.arguments[1:]]
        return upstream_main()
    finally:
        Registry.resolve, sys.argv = previous_resolve, previous_argv


if __name__ == '__main__':
    raise SystemExit(main())
