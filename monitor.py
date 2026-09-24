"""CLI: catalog, run, deliver. No summaries are pushed; notices are per source with cards."""
import argparse
import datetime as dt
import hashlib
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from everest.core import Store, catalog, now, read_json, run_lock, write_json
from everest.collect import collect
from everest.evidence import make_cards, write_report
from everest.delivery import deliver, destination
from everest.windy import metrics as windy_metrics

ROOT = Path(__file__).resolve().parent


def run(args, settings, sources, config, store, data):
    run_id = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:6]
    folder = data / 'runs' / run_id
    folder.mkdir(parents=True)
    selected = [s for s in sources['sources'] if s.get('enabled', True) and (not args.source or s['rule_id'] in args.source)]
    # interval_seconds sources belong to the fast channel; keep them out of the normal cadence.
    selected = [s for s in selected if args.source or not s.get('interval_seconds')]
    stamp = now()
    selected = [s for s in selected if args.all or store.due(s, stamp)]
    state = {'run_id': run_id, 'phase': 'running', 'total': len(selected), 'completed': 0, 'errors': 0, 'exit_code': None}
    write_json(folder / 'status.json', state)
    results = []
    by_id = {source['rule_id']: source for source in sources['sources']}
    def job(source):
        target = folder / source['rule_id']
        result = collect(source, sources.get('defaults', {}), settings, target, run_id)
        return result, target
    delivery_lock = None
    try:
        from threading import Lock
        delivery_lock = Lock()
        from everest.shadow_cep import evaluate as shadow_cep_evaluate
        from everest.shadow_dedup import evaluate as shadow_dedup_evaluate
        with ThreadPoolExecutor(max_workers=max(1, min(8, int(settings['workers'])))) as executor:
            futures = [executor.submit(job, s) for s in selected]
            for future in as_completed(futures):
                result, target = future.result()
                pair_trigger = False
                if result['source']['rule_id'] == 'weather-06':
                    metric = windy_metrics(result)
                    limits = settings.get('windy_pair', {})
                    active = ((metric['wind_kmh'] or 0) >= limits['wind_kmh_min']
                              or (metric['precipitation_mm'] or 0) >= limits['precipitation_mm_min'])
                    pair_trigger = store.paired_weather_trigger(
                        'weather-06', active, metric['temperature_c'], limits['temperature_drop_c_min'])
                    result['windy_metrics'] = metric
                    result['paired_nasa_trigger'] = pair_trigger
                    if pair_trigger:
                        result['relevance'] = 'in_scope'
                        result['event_status'] = 'candidate'
                # Shadow CEP observes only the four selected numeric streams.
                # It cannot alter original change detection, screenshots, or delivery.
                try:
                    result['shadow_cep'] = shadow_cep_evaluate(result['source'], result, data)
                except Exception as exc:
                    result['shadow_cep'] = {'scope': 'shadow_only', 'error': type(exc).__name__}
                try:
                    result['shadow_dedup'] = shadow_dedup_evaluate(result['source'], result, data)
                except Exception as exc:
                    result['shadow_dedup'] = {'scope': 'shadow_only', 'error': type(exc).__name__}
                # Browser screenshots are the expensive path. Create them only for a
                # relevant source whose normalized event content actually changed.
                if store.changed(result['source'], result) or pair_trigger:
                    if pair_trigger:
                        from everest.mapviews import capture_views
                        result['map_views'] = capture_views('weather-06', target, settings, settings['_root'])
                    try:
                        make_cards(result, target, settings)
                        result['card_hashes'] = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in result['cards']}
                    except Exception as exc:
                        result['card_error'] = type(exc).__name__
                target = target / 'result.json'
                store.record(result, target, 'all' if pair_trigger else args.notify, destination(config))
                if pair_trigger:
                    nasa_source = by_id[settings['windy_pair']['nasa_rule_id']]
                    nasa_target = folder / nasa_source['rule_id']
                    nasa = collect(nasa_source, sources.get('defaults', {}), settings, nasa_target, run_id)
                    # NASA is evidence paired to the Windy threshold event, not a standalone map refresh.
                    nasa['relevance'] = 'in_scope'
                    nasa['event_status'] = 'candidate'
                    try:
                        make_cards(nasa, nasa_target, settings)
                        nasa['card_hashes'] = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in nasa['cards']}
                    except Exception as exc:
                        nasa['card_error'] = type(exc).__name__
                    store.record(nasa, nasa_target / 'result.json', 'all', destination(config))
                    results.append(nasa)
                    state['total'] += 1
                    state['completed'] += 1
                results.append(result)
                state['completed'] += 1
                state['errors'] += int(result['result'] == 'unknown' or bool(result.get('card_error')))
                write_json(folder / 'status.json', state)
                print(f"[{state['completed']}/{len(selected)}] {result['source']['rule_id']} {result['result']} cards={len(result['cards'])}", flush=True)
                if args.send and settings.get('delivery_enabled', False):
                    with delivery_lock:
                        sub_stats = deliver(store, run_id, config, settings)
                        if 'delivery' not in state:
                            state['delivery'] = {'accepted': 0, 'blocked': 0, 'unconfirmed': 0}
                        for k, v in sub_stats.items():
                            state['delivery'][k] = state['delivery'].get(k, 0) + v
        results.sort(key=lambda r:r['source']['rule_id'])
        write_report(folder, results)
        state.update(phase='completed', exit_code=int(bool(state['errors']) or any(state.get('delivery',{}).get(k,0) for k in ('blocked','unconfirmed'))))
    except Exception as exc:
        state.update(phase='failed', error=type(exc).__name__, exit_code=1)
    write_json(folder / 'status.json', state)
    write_json(data / 'latest.json', {'run_id':run_id, 'report':str(folder/'index.html'), **state})
    print(json.dumps(state, ensure_ascii=False), flush=True)
    return state['exit_code']


def fast_run(args, settings, sources, config, store, data):
    """Fast channel: cheap HTTP polling for interval_seconds sources.

    No keyword filtering. A screenshot is captured only when the content changed,
    so a 3-second cadence stays affordable.
    """
    tick = float(settings.get('fast_tick_seconds', 3))
    fast_sources = [s for s in sources['sources'] if s.get('enabled', True) and s.get('interval_seconds')]
    if not fast_sources:
        print('No interval_seconds sources configured', flush=True)
        return 0
    print(f"Fast channel started: {len(fast_sources)} source(s), tick={tick}s", flush=True)
    while True:
        stamp = now()
        run_id = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:6]
        for source in fast_sources:
            if not store.due(source, stamp):
                continue
            folder = data / 'fast' / source['rule_id']
            folder.mkdir(parents=True, exist_ok=True)
            try:
                result = collect(source, sources.get('defaults', {}), settings, folder, run_id)
                is_change = store.changed(source, result)
                if is_change:
                    try:
                        make_cards(result, folder, settings)
                        result['card_hashes'] = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in result['cards']}
                    except Exception as exc:
                        result['card_error'] = type(exc).__name__
                    # Snapshot per run: an unchanged later poll must not clobber the
                    # evidence a pending notice still points at.
                    snapshot = folder / f'{run_id}-result.json'
                    store.record(result, snapshot, 'changed', destination(config))
                    print(f"[fast {stamp[11:19]}] {source['rule_id']} {result['result']} changed=True", flush=True)
                    if result.get('cards') and settings.get('delivery_enabled', False):
                        stats = deliver(store, run_id, config, settings)
                        print(f"[fast] delivered {stats}", flush=True)
                else:
                    store.record(result, folder / 'latest-result.json', 'none', destination(config))
                    print(f"[fast {stamp[11:19]}] {source['rule_id']} {result['result']} changed=False", flush=True)
            except Exception as exc:
                print(f"[fast] {source['rule_id']} error {type(exc).__name__}", flush=True)
        time.sleep(tick)


def main(argv=None):
    parser = argparse.ArgumentParser(description='珠峰逐来源采集、截图数据卡与逐条通知')
    parser.add_argument('--data-dir', type=Path, default=ROOT/'data')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('catalog')
    p = sub.add_parser('run')
    p.add_argument('--all', action='store_true', help='强制所有启用来源，不受轮询时间限制')
    p.add_argument('--source', action='append', help='仅指定 rule_id，可重复')
    p.add_argument('--notify', choices=['none','changed','all'], default='changed', help='逐来源入队条件；all 包含无匹配和失败来源')
    p.add_argument('--send', action='store_true', help='发送本轮已选择的逐来源图片消息')
    p = sub.add_parser('deliver')
    p.add_argument('--run-id', required=True)
    sub.add_parser('fast')
    args = parser.parse_args(argv)
    sources = catalog(ROOT/'config/sources.json')
    if args.command == 'catalog':
        for s in sources['sources']:
            print(f"{s['rule_id']}\t{s['category']}\t{s['name']}\t{s['url']}")
        print(f"{len(sources['sources'])} rules / {len({s['url'] for s in sources['sources']})} URLs")
        return 0
    if args.command == 'run' and args.source:
        unknown = set(args.source)-{s['rule_id'] for s in sources['sources']}
        if unknown: parser.error('Unknown rule_id: '+', '.join(sorted(unknown)))
    settings = read_json(ROOT/'config/runtime.json')
    settings['source_plans'] = read_json(ROOT/'config/acquisition.json')
    settings['_root'] = str(ROOT)
    if os.environ.get('EVEREST_BROWSER_CHANNEL'):
        settings['browser_channel'] = os.environ['EVEREST_BROWSER_CHANNEL']
    if os.environ.get('EVEREST_FONT'):
        settings['font'] = os.environ['EVEREST_FONT']
    if os.environ.get('HTTPS_PROXY'):
        settings['proxy'] = os.environ['HTTPS_PROXY']
    config_path = Path(os.environ.get('EVEREST_NOTIFY_FILE', str(ROOT/'config/notify.local.json')))
    config = read_json(config_path) if config_path.exists() else {}
    needs_channel = args.command in ('deliver', 'fast') or getattr(args, 'send', False)
    if needs_channel and not destination(config):
        parser.error('通知渠道尚未配置（Server 酱或微信公众平台）')
    if args.command == 'fast':
        # The fast channel runs continuously; it uses its own lock so the normal
        # cadence loop can still run. SQLite WAL keeps concurrent writes safe.
        store = Store(args.data_dir/'monitor.sqlite3')
        try:
            return fast_run(args, settings, sources, config, store, args.data_dir)
        finally:
            store.close()
    with run_lock(args.data_dir):
        store = Store(args.data_dir/'monitor.sqlite3')
        try:
            if args.command == 'run':
                return run(args, settings, sources, config, store, args.data_dir)
            stats = deliver(store, args.run_id, config, settings)
            print(stats)
            return int(bool(stats['blocked'] or stats['unconfirmed']))
        finally:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
