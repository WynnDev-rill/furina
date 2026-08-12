from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .config import HOME, PERF_STATE_PATH, Config, save_config


def find_llama_bench() -> Path | None:
    candidates = [
        HOME / "llama.cpp" / "build" / "bin" / "llama-bench",
        Path.home() / "llama.cpp" / "build" / "bin" / "llama-bench",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def cpu_summary() -> dict:
    cores = []
    for cpu in sorted(Path('/sys/devices/system/cpu').glob('cpu[0-9]*')):
        try:
            idx = int(cpu.name[3:])
        except Exception:
            continue
        freq = 0
        for name in ('cpuinfo_max_freq', 'scaling_max_freq'):
            path = cpu / 'cpufreq' / name
            try:
                freq = int(path.read_text().strip())
                if freq:
                    break
            except Exception:
                pass
        cores.append({'cpu': idx, 'max_khz': freq})
    return {'cores': cores, 'count': len(cores)}


def _mask_for(cores: list[dict], count: int) -> str:
    ranked = sorted(cores, key=lambda c: (int(c.get('max_khz') or 0), int(c.get('cpu') or 0)), reverse=True)
    picked = ranked[:max(1, min(count, len(ranked)))]
    value = 0
    for item in picked:
        value |= 1 << int(item['cpu'])
    return f"{value:x}"


def _bench(bench: Path, model: Path, threads: int, repetitions: int, *, cpu_mask: str = "") -> tuple[float, dict]:
    cmd = [
        str(bench), '-m', str(model), '-p', '128', '-n', '48', '-r', str(max(1, repetitions)),
        '-t', str(threads), '-o', 'json', '-fa', 'auto',
    ]
    if cpu_mask:
        cmd += ['-C', cpu_mask, '--cpu-strict', '1']
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=420)
    if proc.returncode != 0:
        raise RuntimeError('Benchmark gagal: ' + proc.stderr[-800:])
    try:
        rows = json.loads(proc.stdout)
    except Exception as exc:
        raise RuntimeError('Output llama-bench tidak dapat dibaca.') from exc
    generation = [r for r in rows if int(r.get('n_gen') or 0) > 0]
    if not generation:
        raise RuntimeError('Benchmark tidak menghasilkan metrik generation.')
    best = max(generation, key=lambda r: float(r.get('avg_ts') or 0.0))
    return float(best.get('avg_ts') or 0.0), best


def tune_threads(cfg: Config, *, repetitions: int = 1) -> dict:
    """Benchmark the real phone instead of assuming a big.LITTLE layout.

    First find the best thread count. If llama-bench supports CPU affinity and
    sysfs exposes per-core max frequencies, also test a high-performance-core
    mask. The mask is kept only when it is measurably faster, so devices with
    unusual schedulers are not penalized by a hard-coded Poco-specific guess.
    """
    bench = find_llama_bench()
    if not bench:
        raise RuntimeError('llama-bench belum tersedia. Update/build runtime final terlebih dahulu.')
    model = Path(cfg.model_path)
    if not model.is_file():
        raise RuntimeError('Model lokal belum tersedia.')

    summary = cpu_summary()
    cpu_count = max(1, (summary.get('count') or 1))
    candidates = sorted(set(x for x in (4, 5, 6, min(7, cpu_count), min(8, cpu_count)) if 1 <= x <= cpu_count))

    scored: list[dict] = []
    for threads in candidates:
        tps, _ = _bench(bench, model, threads, repetitions)
        scored.append({'threads': threads, 'cpu_mask': '', 'generation_tps': tps})
    best = max(scored, key=lambda r: r['generation_tps'])

    help_text = subprocess.run([str(bench), '--help'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=10).stdout
    cores = summary.get('cores') or []
    if '-C, --cpu-mask' in help_text and len(cores) >= 5 and any(int(c.get('max_khz') or 0) > 0 for c in cores):
        for count in sorted(set((min(5, len(cores)), min(6, len(cores))))):
            mask = _mask_for(cores, count)
            threads = min(int(best['threads']), count)
            try:
                tps, _ = _bench(bench, model, threads, repetitions, cpu_mask=mask)
                scored.append({'threads': threads, 'cpu_mask': mask, 'generation_tps': tps})
            except Exception:
                # Affinity is an optional optimization. A device/kernel that
                # rejects it simply keeps the scheduler-controlled baseline.
                pass

    winner = max(scored, key=lambda r: r['generation_tps'])
    # Require a real (>2%) win before overriding Android's scheduler.
    baseline = max((r for r in scored if not r['cpu_mask']), key=lambda r: r['generation_tps'])
    if winner['cpu_mask'] and winner['generation_tps'] < baseline['generation_tps'] * 1.02:
        winner = baseline

    cfg.threads = int(winner['threads'])
    cfg.cpu_mask = str(winner['cpu_mask'])
    cfg.cpu_strict = bool(cfg.cpu_mask)
    cfg.performance_tuned = True
    save_config(cfg)

    result = {
        'threads': cfg.threads,
        'cpu_mask': cfg.cpu_mask or None,
        'generation_tps': round(float(winner['generation_tps']), 2),
        'candidates': [{**r, 'generation_tps': round(float(r['generation_tps']), 2)} for r in scored],
        'cpu': summary,
    }
    PERF_STATE_PATH.write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result
