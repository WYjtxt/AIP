"""Host CPU admission and independent logical accelerator protection. Pure policy."""
import math
import json

DEFAULTS = dict(sample_seconds=5, sample_gap_seconds=12, stale_seconds=20,
                trigger_seconds=30, recovery_seconds=60, reservation_seconds=35,
                cpu_warning=50, cpu_warning_recovery=40, cpu_limit=85, cpu_recovery=75,
                card_limit=70, card_recovery=60, pair_limit=60, pair_recovery=50,
                cpu_budget_limit=75, cpu_task_reserve=5,
                memory_limit=90, memory_recovery=80)


def percentage(value):
    try:
        if isinstance(value, bool):
            return None
        value = float(str(value).strip().rstrip('%'))
        return value if math.isfinite(value) and 0 <= value <= 100 else None
    except (ValueError, TypeError):
        return None


def policy_config(overrides=None):
    policy = dict(DEFAULTS)
    for key, value in (overrides or {}).items():
        if key not in policy or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Invalid admission policy: ' + str(key))
        policy[key] = value
    if 'cpu_budget_limit' not in (overrides or {}):
        policy['cpu_budget_limit'] = min(75, policy['cpu_recovery'])
    for key in ('cpu', 'card', 'pair', 'memory'):
        if not 0 < policy[key + '_recovery'] < policy[key + '_limit'] <= 100:
            raise ValueError('Recovery threshold must be below limit')
    if not 0 <= policy['cpu_warning_recovery'] < policy['cpu_warning'] < policy['cpu_limit']:
        raise ValueError('Invalid CPU warning threshold')
    if not 1 <= policy['cpu_task_reserve'] <= policy['cpu_budget_limit'] <= policy['cpu_limit']:
        raise ValueError('CPU budget must cover one task and stay below host limit')
    if not (1 <= policy['sample_seconds'] <= 10 and policy['sample_seconds'] < policy['sample_gap_seconds'] <= policy['stale_seconds'] <= 60):
        raise ValueError('Invalid sampling interval')
    if not (10 <= policy['trigger_seconds'] <= 300 and 10 <= policy['recovery_seconds'] <= 600 and 5 <= policy['reservation_seconds'] <= 120):
        raise ValueError('Invalid observation duration')
    return policy


def warmup_seconds(policy):
    # Cover at least one full freshness window plus a new collector tick.
    return int(max(policy['reservation_seconds'], policy['stale_seconds'] + policy['sample_seconds']))


def budget(cpu, units, policy, reserved=0):
    cpu = percentage(cpu)
    if cpu is None or type(units) is not int or units < 1:
        return {'allowed': False, 'projected_cpu': None, 'reason': '主机 CPU 或任务数量无效，暂停新增部署'}
    cost = units * policy['cpu_task_reserve']
    projected = cpu + reserved + cost
    allowed = cpu < policy['cpu_limit'] and projected <= policy['cpu_budget_limit']
    return {'allowed': allowed, 'projected_cpu': projected, 'reserved_cpu': reserved,
            'request_cpu': cost, 'units': units, 'estimate_source': 'configured_reserve',
            'reason': '' if allowed else '主机 CPU 预算不足：当前 {:.1f}% + 预留 {:.1f} + 本次 {:.1f} 个百分点，超过预算上限 {}%'.format(cpu, reserved, cost, policy['cpu_budget_limit'])}


def gate(previous, high, low, token, sampled_at, now, policy):
    state = dict(previous or {})
    valid = token is not None and sampled_at is not None and -2 <= now - sampled_at <= policy['stale_seconds']
    if not valid:
        state.pop('high_since', None)
        state.pop('low_since', None)
        return state
    if token == state.get('token'):
        if not high:
            state.pop('high_since', None)
        if not low:
            state.pop('low_since', None)
        return state  # Cached observations never advance a duration.
    last = state.get('sampled_at')
    if last is None or sampled_at <= last or sampled_at - last > policy['sample_gap_seconds']:
        state.pop('high_since', None)
        state.pop('low_since', None)
    state.update(token=token, sampled_at=sampled_at)
    if high:
        state.pop('low_since', None)
        state.setdefault('high_since', sampled_at)
        if sampled_at - state['high_since'] >= policy['trigger_seconds']:
            state['blocked'] = True
    else:
        state.pop('high_since', None)
    if state.get('blocked') and low:
        state.setdefault('low_since', sampled_at)
        if sampled_at - state['low_since'] >= policy['recovery_seconds']:
            state['blocked'] = False
            state.pop('low_since', None)
    elif not low:
        state.pop('low_since', None)
    return state


def advance(previous, sample, now, policy=None):
    policy = policy or policy_config()
    state = dict(previous or {})
    fingerprint = json.dumps(policy, sort_keys=True)
    changed = state.get('policy_fingerprint') not in (None, fingerprint)
    def previous_gate(value):
        value = dict(value or {})
        if changed:
            value.pop('high_since', None)
            value.pop('low_since', None)
        return value
    state['policy_fingerprint'] = fingerprint
    # Old all-card and preferred-device-zero decisions are deliberately retired.
    state.pop('pair_gate', None)
    state.pop('primary_recovery', None)
    cpu, cpu_at = percentage(sample.get('cpu')), sample.get('cpu_at')
    for name, limit, recovery in [('cpu_gate', 'cpu_limit', 'cpu_recovery'),
                                  ('warning_gate', 'cpu_warning', 'cpu_warning_recovery')]:
        state[name] = gate(previous_gate(state.get(name)), cpu is not None and cpu >= policy[limit],
                           cpu is not None and cpu < policy[recovery],
                           sample.get('cpu_token') if cpu is not None else None, cpu_at, now, policy)
    old_cards = state.get('cards', {})
    cards = {}
    for raw in sample.get('cards', []):
        card = dict(raw)
        old = old_cards.get(str(card['id']), {})
        for metric, gate_name, prefix in [('util', 'gate', 'card'), ('memory', 'memory_gate', 'memory')]:
            card[metric] = percentage(card.get(metric))
            value = card[metric]
            card[gate_name] = gate(previous_gate(old.get(gate_name)),
                                   value is not None and value >= policy[prefix + '_limit'],
                                   value is not None and value < policy[prefix + '_recovery'],
                                   card.get('token') if value is not None else None,
                                   card.get('sampled_at'), now, policy)
        cards[str(card['id'])] = card
    state.update(cards=cards, cpu=cpu, cpu_at=cpu_at, updated_at=now, strategy='host_chip_budget_v2')
    return state


def view(state, now, policy=None, pending=False):
    policy = policy or policy_config()
    state = state or {}
    cpu = state.get('cpu')
    cpu_fresh = cpu is not None and state.get('cpu_at') is not None and -2 <= now - state['cpu_at'] <= policy['stale_seconds']
    estimate = budget(cpu, 1, policy)
    result = {'cpu': cpu, 'cpu_warning': bool(cpu_fresh and state.get('warning_gate', {}).get('blocked')),
              'cards': {}, 'strategy': 'host_chip_budget_v2', 'cpu_budget': estimate,
              'chip_count': len(state.get('cards', {}))}
    for key, card in state.get('cards', {}).items():
        reason = ''
        fresh = card.get('util') is not None and card.get('sampled_at') is not None and -2 <= now - card['sampled_at'] <= policy['stale_seconds']
        if not cpu_fresh or not fresh:
            reason = '状态未知或采集数据已过期，暂停新增部署'
        elif state.get('cpu_gate', {}).get('blocked') or cpu >= policy['cpu_limit']:
            reason = '主机 CPU 达到保护阈值 {}%，暂停新增部署'.format(policy['cpu_limit'])
        elif not estimate['allowed']:
            reason = estimate['reason']
        elif card.get('gate', {}).get('blocked') or card['util'] >= policy['card_limit']:
            reason = '该计算芯片利用率达到 {}%，请选择其他可用芯片'.format(policy['card_limit'])
        elif card.get('memory') is None:
            reason = '计算芯片内存状态未知，暂停向该芯片新增部署'
        elif card.get('memory_gate', {}).get('blocked') or card['memory'] >= policy['memory_limit']:
            reason = '该计算芯片内存达到 {}%，请选择其他可用芯片'.format(policy['memory_limit'])
        elif pending:
            reason = '新增部署后的负载观察中，请稍后重试'
        result['cards'][key] = {'disabled': bool(reason), 'reason': reason,
            'primary_return_ready': False, 'utilization': card.get('util'),
            'memory_utilization': card.get('memory'), 'sampled_at': card.get('sampled_at'),
            'dev_id': card.get('dev_id'), 'target': card.get('target'),
            'physical_board_id': None, 'topology_status': 'physical_board_unreported',
            'board_temperature': card.get('board_temperature'), 'chip_temperature': card.get('chip_temperature'),
            'health_status': 'unreported', 'media_metrics_status': 'unreported',
            'state': 'unknown' if not cpu_fresh or not fresh or card.get('memory') is None else 'blocked' if reason else 'available'}
    result['available_chip_count'] = sum(not card['disabled'] for card in result['cards'].values())
    return result
