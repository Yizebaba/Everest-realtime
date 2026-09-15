"""CLI: catalog, run, deliver. No summaries are pushed; notices are per source with cards."""
import argparse
import datetime as dt
import hashlib
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from everest.core import Store, catalog, now, read_json, run_lock, write_json
from everest.collect import collect
from everest.evidence import make_cards, write_report
from everest.delivery import deliver, destination

ROOT = Path(__file__).resolve().parent


def run(args, settings, sources, config, store, data):
    run_id = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:6]
    folder = data / 'runs' / run_id
    folder.mkdir(parents=True)
    selected = [s for s in sources['sources'] if s.get('enabled', True) and (not args.source or s['rule_id'] in args.source)]
    stamp = now()
    selected = [s for s in selected if args.all or store.due(s, stamp)]
    state = {'run_id': run_id, 'phase': 'running', 'total': len(selected), 'completed': 0, 'errors': 0, 'exit_code': None}
    write_json(folder / 'status.json', state)
    results = []
    def job(source):
        target = folder / source['rule_id']
        result = collect(source, sources.get('defaults', {}), settings, target, run_id)
        try:
            make_cards(result, target, settings)
            result['card_hashes'] = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in result['cards']}
        except Exception as exc:
            result['card_error'] = type(exc).__name__
        return result
    try:
        with ThreadPoolExecutor(max_workers=max(1, min(8, int(settings['workers'])))) as executor:
            futures = [executor.submit(job, s) for s in selected]
            for future in as_completed(futures):
                result = future.result()
                target = folder / result['source']['rule_id'] / 'result.json'
                store.record(result, target, args.notify, destination(config))
                results.append(result)
                state['completed'] += 1
                state['errors'] += int(result['result'] == 'unknown' or not result.get('cards'))
                write_json(folder / 'status.json', state)
                print(f"[{state['completed']}/{len(selected)}] {result['source']['rule_id']} {result['result']} cards={len(result['cards'])}", flush=True)
        results.sort(key=lambda r:r['source']['rule_id'])
        write_report(folder, results)
        if args.send:
            state['delivery'] = deliver(store, run_id, config, settings)
        state.update(phase='completed', exit_code=int(bool(state['errors']) or any(state.get('delivery',{}).get(k,0) for k in ('blocked','unconfirmed'))))
    except Exception as exc:
        state.update(phase='failed', error=type(exc).__name__, exit_code=1)
    write_json(folder / 'status.json', state)
    write_json(data / 'latest.json', {'run_id':run_id, 'report':str(folder/'index.html'), **state})
    print(json.dumps(state, ensure_ascii=False), flush=True)
    return state['exit_code']


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
    if (args.command == 'deliver' or args.send) and not destination(config):
        parser.error('Server 酱尚未配置')
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
