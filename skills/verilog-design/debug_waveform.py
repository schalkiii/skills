#!/usr/bin/env python3
"""
AI-Friendly Waveform Debug Tool for Verilog Simulation.
Parses VCD files and provides structured signal analysis — one universal --watch command.

Commands:
  --list-signals [--pattern <kw>]    列出 VCD 中所有信号
  --watch [sigs] --time <ps>         快照：在指定时间 dump 信号值
  --watch [sigs] --trigger <sig>     时间序列：在 trigger 上升沿追踪信号变化
  --watch [sigs] -n N                时间序列：在首信号每次变化时追踪，最多 N 次
  --watch                            空参数 → auto-discover 快照（仿真正结束时刻）

Snapshot examples:
  python3 debug_waveform.py --vcd waveform.vcd --watch result mode --time 95000 --json
  python3 debug_waveform.py --vcd waveform.vcd --watch  # auto-discover at simulation end

Time window examples:
  python3 debug_waveform.py --vcd waveform.vcd --watch valid result --time 97175000-97375000 --json

Time-series examples:
  python3 debug_waveform.py --vcd waveform.vcd --watch result mode --trigger valid -n 20
  python3 debug_waveform.py --vcd waveform.vcd --watch error  # track every change
"""

import json
import re
import sys
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any

SIGNAL_WIDTH_HINT = {
    'clk': 1, 'rst_n': 1, 'mode': 2, 'valid_in': 1, 'valid_out': 1,
    'result': 36, 'fp16_dot_result': 32, 'int16_dot_result': 36,
    'a': 256, 'b': 256, 'fp16_valid': 1, 'int16_valid': 1,
}

@dataclass
class SignalChange:
    time: int
    value: str

@dataclass
class VCDFile:
    signals: Dict[str, List[SignalChange]] = field(default_factory=dict)
    signal_widths: Dict[str, int] = field(default_factory=dict)
    signal_ids: Dict[str, str] = field(default_factory=dict)
    id_to_signal: Dict[str, str] = field(default_factory=dict)
    max_time: int = 0
    timescale: str = "ps"
    date: str = ""
    version: str = ""


@dataclass
class DebugResult:
    signal: str
    expected: str
    actual: str
    match: bool
    time_ns: float
    width: int


def parse_vcd(filepath: str) -> VCDFile:
    """Parse a VCD file into structured data."""
    vcd = VCDFile()
    current_time = 0
    stack = []
    signal_name_parts = []

    with open(filepath, 'r') as f:
        lines = f.readlines()

    for line in lines:
        line = line.rstrip('\n')

        if line.startswith('$date'):
            vcd.date = line[6:].strip()
        elif line.startswith('$timescale'):
            vcd.timescale = line[11:].strip().strip('$end').strip()
        elif line.startswith('$version'):
            vcd.version = line[8:].strip()
        elif line.startswith('$var'):
            parts = line.split()
            if len(parts) >= 4:
                var_type = parts[1]
                width = int(parts[2])
                id_code = parts[3]
                name = parts[4] if len(parts) > 4 else ""
                full_name = name

                if stack:
                    full_name = '.'.join(stack + [name])

                vcd.signal_ids[full_name] = id_code
                # 仅首次注册 id_to_signal，避免内部 scope 复用 ID 时覆盖顶层映射
                # Icarus 在多 scope 中为同一连线复用相同 VCD ID，保留第一个映射即可
                if id_code not in vcd.id_to_signal:
                    vcd.id_to_signal[id_code] = full_name
                vcd.signal_widths[full_name] = width
                vcd.signals[full_name] = []
        elif line.startswith('$scope'):
            parts = line.split()
            if len(parts) >= 3:
                stack.append(parts[2])
        elif line.startswith('$upscope'):
            if stack:
                stack.pop()
        elif line.startswith('$enddefinitions'):
            pass
        elif line.startswith('#'):
            current_time = int(line[1:])
            if current_time > vcd.max_time:
                vcd.max_time = current_time
        elif not line.startswith('$') and not line.startswith('b') and not line.startswith('r'):
            if line and line[0] in ('0', '1', 'x', 'z') and len(line) >= 2:
                value = line[0]
                id_code = line[1:].strip()
                if id_code and id_code in vcd.id_to_signal:
                    signal_name = vcd.id_to_signal[id_code]
                    vcd.signals[signal_name].append(SignalChange(current_time, value))
            elif line:
                first_char = line[0]
                rest = line[1:].strip()
                if first_char in ('0', '1', 'x', 'z') and rest:
                    id_code = rest
                    if id_code and id_code in vcd.id_to_signal:
                        signal_name = vcd.id_to_signal[id_code]
                        vcd.signals[signal_name].append(SignalChange(current_time, first_char))

        # 处理向量值（b/B 前缀），兼容单比特向量 (b0, b1) 和多比特向量 (b1010, bxxxxx)
        if line.startswith('b') or line.startswith('B'):
            m = re.match(r'[bB]([01xXzZ]+)\s+(\S+)', line)
            if m:
                value = m.group(1)
                id_code = m.group(2)
                if id_code in vcd.id_to_signal:
                    signal_name = vcd.id_to_signal[id_code]
                    vcd.signals[signal_name].append(SignalChange(current_time, value))

    return vcd


def get_value_at_time(vcd: VCDFile, signal: str, target_time: int) -> Optional[str]:
    """Get the value of a signal at a specific time (binary search)."""
    if signal not in vcd.signals:
        return None

    changes = vcd.signals[signal]
    if not changes:
        return None

    lo, hi = 0, len(changes) - 1
    result = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if changes[mid].time <= target_time:
            result = changes[mid].value
            lo = mid + 1
        else:
            hi = mid - 1

    return result


def value_to_hex(bin_str: str) -> str:
    """Convert binary string to hex."""
    if not bin_str or any(c not in '01' for c in bin_str):
        return bin_str
    val = int(bin_str, 2)
    width = (len(bin_str) + 3) // 4
    return f"0x{val:0{width}X}"


def format_signal_value(val: str, width: int = 0) -> Dict[str, Any]:
    """Format a signal value into {bin, hex, value} dict."""
    if val is None:
        return {'value': 'N/A'}
    if all(c in '01' for c in val) and len(val) > 1:
        return {'bin': val, 'hex': value_to_hex(val)}
    return {'value': val}


def list_available_signals(vcd: VCDFile, pattern: Optional[str] = None):
    """List all available signals, optionally filtered by pattern."""
    print(f"\nAvailable Signals ({len(vcd.signals)} total):")
    print("=" * 60)

    sorted_signals = sorted(vcd.signals.keys())
    for sig in sorted_signals:
        if pattern and pattern.lower() not in sig.lower():
            continue
        width = vcd.signal_widths.get(sig, '?')
        count = len(vcd.signals[sig])
        print(f"  {sig:<40} width={width:<3} changes={count}")
    print(f"\nTotal signals: {len(sorted_signals)}")
    print(f"Simulation time: {vcd.max_time} {vcd.timescale}")


def extract_port_values_at_time(vcd: VCDFile, time_ps: int, ports: List[str]) -> Dict[str, str]:
    """Extract values for a list of ports at a given time, in hex."""
    result = {}
    for port in ports:
        val = get_value_at_time(vcd, port, time_ps)
        if val is not None:
            width = vcd.signal_widths.get(port, len(val) if 'x' not in val and 'z' not in val else 0)
            if all(c in '01' for c in val) and len(val) > 1:
                result[port] = value_to_hex(val)
            else:
                result[port] = val
        else:
            result[port] = "N/A"
    return result


def find_signals_by_hint(vcd: VCDFile, hints: List[str]) -> List[str]:
    """用后缀/关键词在 VCD 信号中模糊匹配，返回匹配到的完整信号路径。
    按 hints 中的优先级排序返回，每个 hint 匹配一个最佳信号。
    优先选择后缀匹配 + 有变化的信号。
    """
    matched = []
    for hint in hints:
        candidates = []
        for sig in vcd.signals:
            if sig.endswith('.' + hint):
                candidates.append((0, len(vcd.signals[sig]), sig))
            elif hint in sig:
                candidates.append((1, len(vcd.signals[sig]), sig))
        # 排序：匹配精度优先(后缀>包含)，同精度下变化数多者优先
        candidates.sort(key=lambda x: (x[0], -x[1]))
        if candidates:
            matched.append(candidates[0][2])
    return matched


def resolve_signal(vcd: VCDFile, name: str) -> Optional[str]:
    """解析信号名：先精确匹配，再后缀/包含匹配。"""
    if name in vcd.signals:
        return name
    found = find_signals_by_hint(vcd, [name])
    return found[0] if found else None


# 调试关键信号提示词 — 用于 auto-discover 模式，按信号名后缀匹配，跨仿真器通用
# 此列表可由用户按项目定制。通用原则：覆盖系统端口 + FSM 状态 + 各级流水 valid + 关键中间值
# 自动发现信号提示列表 — 按常见流水线设计模式组织的通用信号名
# 工具使用后缀模糊匹配，不存在的信号会被静默跳过
DEBUG_HINTS = {
    'common': [
        'clk', 'rst_n', 'mode',
        'valid', 'valid_in', 'valid_out', 'o_valid',
        'result', 'idle', 'o_idle',
        'start', 'done', 'ready',
        'a', 'b', 'input', 'output',
    ],
    'mode_a': [
        'state_q', 'state',                    # FSM 状态
        's1_valid', 's2_valid', 's3_valid',    # 流水级 valid
        's4_valid', 's5_valid',
        'overflow', 'underflow',               # 异常标志
        'sum', 'acc', 'accum',                 # 累加中间值
        'norm', 'normalized',                  # 归一化
    ],
    'mode_b': [
        'state_q', 'state',                    # FSM 状态
        's1_valid', 's2_valid',                # 流水级 valid
        'sum', 'acc', 'accum',                 # 累加中间值
    ],
}


def auto_discover_signals(vcd: VCDFile, mode_hint: str = "01") -> List[str]:
    """根据模式自动发现所有关键调试信号。"""
    common = find_signals_by_hint(vcd, DEBUG_HINTS['common'])
    sub_hints = DEBUG_HINTS['mode_a'] if mode_hint == "01" else DEBUG_HINTS['mode_b']
    sub = find_signals_by_hint(vcd, sub_hints)
    return common + sub


def detect_mode_at_time(vcd: VCDFile, time_ps: int) -> str:
    """在指定时刻检测 mode 信号值，推断当前模式。"""
    mode_path = resolve_signal(vcd, 'mode')
    if not mode_path:
        return "01"
    val = get_value_at_time(vcd, mode_path, time_ps)
    if val and any(c not in '01' for c in val):
        # 非 pure binary (含 x, z) → 默认 mode 01
        return "01"
    if val == "10":
        return "10"
    return "01"  # default


def watch_signals(vcd: VCDFile, watch_list: List[str],
                  trigger: str = None, max_events: int = 10,
                  time_window: tuple = None) -> List[Dict[str, Any]]:
    """万能信号观测：三种模式。

    Args:
        vcd:          解析后的 VCD 文件对象
        watch_list:   要观测的信号名列表（支持简写）
        trigger:      触发信号名，仅在 trigger 上升沿输出
        max_events:   最多返回 N 个事件
        time_window:  (start, end) 时间窗口，仅输出窗口内的事件

    Returns:
        [{time_ps, time_ns, signals: {sig: {bin, hex}}}]
    """

    # 解析信号名
    resolved = {}
    for name in watch_list:
        full = resolve_signal(vcd, name)
        if full:
            resolved[name] = full
        else:
            print(f"Warning: signal '{name}' not found in VCD")

    if not resolved:
        return []

    # --- 时间序列模式（时间窗口为可选过滤条件）---
    events = []
    trigger_full = resolve_signal(vcd, trigger) if trigger else None
    if trigger and not trigger_full:
        print(f"Warning: trigger signal '{trigger}' not found in VCD")
        return events

    source_signal = trigger_full if trigger_full else list(resolved.values())[0]
    if source_signal not in vcd.signals:
        return events

    changes = vcd.signals[source_signal]
    prev_val = None

    for change in changes:
        # 时间窗口过滤: 跳过窗口外的事件
        if time_window:
            if change.time < time_window[0]:
                prev_val = change.value
                continue
            if change.time > time_window[1]:
                break  # 已超出窗口，后续不再考虑

        if trigger_full:
            if not (prev_val is not None and prev_val == '0' and change.value == '1'):
                prev_val = change.value
                continue
        else:
            if prev_val is None:
                prev_val = change.value
                continue

        watch_vals = {}
        for short_name, full_path in resolved.items():
            val = get_value_at_time(vcd, full_path, change.time)
            watch_vals[short_name] = format_signal_value(val)

        if watch_vals:
            events.append({
                'time_ps': change.time,
                'time_ns': change.time / 1000.0,
                'signals': watch_vals,
            })

        prev_val = change.value

    return events[-max_events:]


def print_snapshot(vcd: VCDFile, events: List[Dict], time_ps: int,
                   title: str = "Snapshot", extra_signals: List[str] = None):
    """打印快照输出（可读格式）。"""
    if not events:
        print("No data")
        return

    e = events[0]
    print(f"\n{'=' * 70}")
    print(f"  {title} at t={time_ps} ps ({time_ps/1000:.1f} ns)")
    print(f"{'=' * 70}")

    # 分组显示：common 端口 vs 模块内部
    common_keys = {'clk', 'rst_n', 'mode', 'valid_in', 'valid_out', 'result', 'idle', 'a', 'b'}
    internals = {}
    commons = {}

    for sig, sval in e['signals'].items():
        if sig in common_keys:
            commons[sig] = sval
        else:
            internals[sig] = sval

    if commons:
        print(f"\n--- System Ports ---")
        for sig, sval in commons.items():
            v = sval.get('hex', sval.get('value', 'N/A'))
            print(f"  {sig:<25} = {v}")

    if internals:
        print(f"\n--- Module Internals ---")
        for sig, sval in internals.items():
            v = sval.get('hex', sval.get('value', 'N/A'))
            print(f"  {sig:<25} = {v}")

    # 如果指定了额外信号（如 result timeline），也打印
    if extra_signals:
        print(f"\n--- Result Timeline ---")
        for item in extra_signals:
            print(item)


def print_timeseries(events: List[Dict], watch_list: List[str],
                     trigger: str = None, max_events: int = 10):
    """打印时间序列输出（可读格式）。"""
    if not events:
        print("No matching events found")
        return

    trigger_info = f"triggered by {trigger}" if trigger else f"on {watch_list[0]} changes"
    print(f"\n=== Signal Watch ({', '.join(watch_list)}) {trigger_info} ===")
    print(f"Found {len(events)} events (showing last {max_events}):")

    for i, e in enumerate(events):
        print(f"\n  [{i+1}] t={e['time_ns']:>10.1f}ns")
        for sig, sval in e['signals'].items():
            if 'hex' in sval:
                print(f"      {sig:<45} = {sval['hex']}  (bin: {sval['bin']})")
            else:
                print(f"      {sig:<45} = {sval.get('value', 'N/A')}")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='AI-Friendly Waveform Debug Tool — universal signal watch',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --vcd waveform.vcd --list-signals
  %(prog)s --vcd waveform.vcd --list-signals --pattern valid
  %(prog)s --vcd waveform.vcd --watch result,mode --time 9500 --json   # snapshot at 95ns
  %(prog)s --vcd waveform.vcd --watch --time 9500 --json               # auto-discover at 9500ps
  %(prog)s --vcd waveform.vcd --watch                                  # auto-discover at end time
  %(prog)s --vcd waveform.vcd --watch result,mode --trigger valid -n 20   # time-series
  %(prog)s --vcd waveform.vcd --watch error                            # track every change
  %(prog)s --vcd waveform.vcd --watch valid result --time 95000-97500  # time-windowed trace
  %(prog)s --vcd waveform.vcd --signals result,clk --time 9500 --json  # legacy probe
        """
    )

    parser.add_argument('--vcd', default='../../waveform.vcd',
                        help='Path to VCD waveform file')
    parser.add_argument('--signals', nargs='*', default=[],
                        help='Signal names to probe (legacy, space-separated)')
    parser.add_argument('--time', type=str, default=None,
                        help='Timestamp in ps, or time window as START-END (e.g., 95000-97500). '
                             'Single value: snapshot at that time. '
                             'Window: trace all changes within [START, END].')
    parser.add_argument('--list-signals', action='store_true',
                        help='List all available signals')
    parser.add_argument('--pattern', type=str, default=None,
                        help='Filter signals by name pattern (used with --list-signals)')
    parser.add_argument('--watch', nargs='*', default=None,
                        help='Signal names (space-separated) to watch. '
                             'With --time <ps> → snapshot at that time. '
                             'With --time START-END → time-windowed trace. '
                             'Without --time → time-series or free-running. '
                             'Use --watch alone (no signal list) for auto-discover.')
    parser.add_argument('--trigger', type=str, default=None,
                        help='Trigger signal: only report on rising edge (0→1). '
                             'Time-series mode only; ignored in snapshot mode.')
    parser.add_argument('-n', '--max-events', type=int, default=10,
                        help='Max events in time-series mode (default: 10)')
    parser.add_argument('--json', action='store_true',
                        help='Output results as JSON')

    args = parser.parse_args()

    vcd_path = Path(args.vcd)
    if not vcd_path.exists():
        for loc in ['waveform.vcd', '../waveform.vcd', '../../waveform.vcd',
                     'flow/sim/waveform.vcd', 'sim/waveform.vcd']:
            p = Path(loc)
            if p.exists():
                vcd_path = p
                break
        else:
            print(f"Error: VCD file not found at {args.vcd}")
            sys.exit(1)

    print(f"Parsing VCD: {vcd_path}")
    vcd = parse_vcd(str(vcd_path))
    print(f"Parsed: {len(vcd.signals)} signals, {vcd.max_time} {vcd.timescale} max time")

    # 解析 --time: 单时间点 "95000" 或时间窗口 "95000-97500"
    snap_time = None        # 单时间点快照
    time_window = None      # (start, end) 时间窗口
    if args.time is not None:
        time_str = args.time.strip()
        if '-' in time_str:
            parts = time_str.split('-')
            try:
                t_start, t_end = int(parts[0]), int(parts[1])
                time_window = (min(t_start, t_end), max(t_start, t_end))
            except ValueError:
                print(f"Error: invalid time window format '{time_str}', expected START-END")
                sys.exit(1)
        else:
            try:
                snap_time = int(time_str)
            except ValueError:
                print(f"Error: invalid time value '{time_str}'")
                sys.exit(1)

    # --- list-signals ---
    if args.list_signals:
        list_available_signals(vcd, args.pattern)
        return

    # --- watch mode (统一入口) ---
    if args.watch is not None:
        # --watch 无参数 → auto-discover；有参数 → 指定信号列表
        watch_list = args.watch  # nargs='*' 返回 list，如 ['valid', 'result']

        # 模式判定：
        #   snap_time  → 快照模式（单时间点 dump）
        #   time_window → 时间窗口模式（追踪窗口内所有变化）
        #   无 --time + 有 --trigger → 时间序列模式（trigger 边沿追踪）
        #   无 --time + 无 --trigger + 有信号 → 自由追踪模式

        if snap_time is not None:
            # === 快照模式 ===
            use_time = snap_time if snap_time else vcd.max_time

            if not watch_list:
                # auto-discover
                mode_bit = detect_mode_at_time(vcd, use_time)
                # mode_bit "01" → mode_a hints, "10" → mode_b hints
                mode_key = "mode_a" if mode_bit == "01" else "mode_b"
                all_hints = DEBUG_HINTS['common'] + DEBUG_HINTS[mode_key]
                resolved_override = {}
                for hint in all_hints:
                    full = resolve_signal(vcd, hint)
                    if full:
                        resolved_override[hint] = full
            else:
                resolved_override = {}
                for name in watch_list:
                    full = resolve_signal(vcd, name)
                    if full:
                        resolved_override[name] = full

            if not resolved_override:
                print("No signals to snapshot")
                return

            watch_vals = {}
            for short_name, full_path in resolved_override.items():
                val = get_value_at_time(vcd, full_path, use_time)
                watch_vals[short_name] = format_signal_value(val)

            events = [{
                'time_ps': use_time,
                'time_ns': use_time / 1000.0,
                'signals': watch_vals,
            }]

            if not args.json:
                extra = None
                if not args.watch:
                    extra_lines = []
                    for delta in [-360, -240, -120, 0]:
                        t = use_time + delta * 1000
                        if t < 0:
                            continue
                        result_sig = resolve_signal(vcd, 'result')
                        if result_sig:
                            r_val = get_value_at_time(vcd, result_sig, t)
                            if r_val and all(c in '01' for c in r_val):
                                extra_lines.append(f"  result[{t/1000:.0f}ns] = {value_to_hex(r_val)}")
                    if extra_lines:
                        extra = extra_lines
                print_snapshot(vcd, events, use_time,
                              title="Auto-discover Snapshot" if not args.watch else "Signal Snapshot",
                              extra_signals=extra)
            else:
                print(json.dumps(events, indent=2, default=str))

        elif time_window is not None:
            # === 时间窗口模式 ===
            events = watch_signals(vcd, watch_list, trigger=None,
                                   max_events=args.max_events,
                                   time_window=time_window)
            if not args.json:
                print(f"\nTime Window: {time_window[0]}ps - {time_window[1]}ps ({time_window[0]/1000:.0f}-{time_window[1]/1000:.0f}ns)")
                if not events:
                    print("  (no events in window)")
                else:
                    print_timeseries(events, watch_list, args.trigger, args.max_events)
            else:
                print(json.dumps(events, indent=2, default=str))

        else:
            # === 时间序列模式 / 自由追踪 ===
            events = watch_signals(vcd, watch_list, trigger=args.trigger,
                                   max_events=args.max_events)
            if not args.json:
                print_timeseries(events, watch_list, args.trigger, args.max_events)
            else:
                print(json.dumps(events, indent=2, default=str))
        return

    # --- legacy probe mode (--signals + --time) ---
    signal_list = list(args.signals) if args.signals else []
    if not signal_list:
        signal_list = find_signals_by_hint(vcd, ['clk', 'rst_n', 'mode', 'valid_in', 'valid_out', 'result'])

    probe_time = snap_time if snap_time else vcd.max_time
    print(f"\nSignal values at t={probe_time} ps ({probe_time/1000:.1f} ns):")
    print("=" * 60)

    results = {}
    for sig in signal_list:
        val = get_value_at_time(vcd, sig, probe_time)
        if val is not None:
            if all(c in '01' for c in val) and len(val) > 1:
                hex_val = value_to_hex(val)
                width = vcd.signal_widths.get(sig, len(val))
                decimal = int(val, 2) if width <= 64 and all(c in '01' for c in val) else None
                print(f"  {sig:<50} = bin={val}  hex={hex_val}" +
                      (f"  dec={decimal}" if decimal is not None else ""))
                results[sig] = {'binary': val, 'hex': hex_val,
                                'decimal': decimal, 'width': width}
            else:
                print(f"  {sig:<50} = {val}")
                results[sig] = {'value': val}
        else:
            print(f"  {sig:<50} = N/A")
            results[sig] = None

    if args.json:
        print(json.dumps(results, indent=2, default=str))


if __name__ == '__main__':
    main()