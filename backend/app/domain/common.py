"""Shared contract primitives. No secrets are stored in this module."""
import hashlib
import hmac
import json
import re


class DomainError(Exception):
    def __init__(self, status, code, details=None, message=None):
        self.status = status
        self.code = code
        self.details = details or {}
        self.message = message or code.replace('_', ' ').capitalize()
        super().__init__(self.message)

    def body(self):
        return {'error': {'code': self.code, 'message': self.message, 'details': self.details}}


def invalid(*fields):
    raise DomainError(400, 'VALIDATION_ERROR', {'fields': list(fields)})


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,64}', value) is not None


def integer(value, low=None, high=None):
    return type(value) is int and (low is None or value >= low) and (high is None or value <= high)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def signer(salt):
    """Inject the startup environment value or Abdullah's shared signing function."""
    if not isinstance(salt, str) or not salt:
        raise ValueError('DAY1_SALT must be supplied at startup')

    def sign(record_id, payload):
        return hmac.new(salt.encode('utf-8'), (record_id + '|' + canonical(payload)).encode('utf-8'),
                        hashlib.sha256).hexdigest()
    return sign


TIE_BREAKS = ['h2h_points', 'h2h_diff', 'overall_diff', 'scored', 'fair_play', 'draw_lots']


def tie_order(value):
    if not isinstance(value, list) or any(not isinstance(x, str) or x not in TIE_BREAKS for x in value):
        invalid('tie_break_order')
    if len(value) != len(set(value)):
        invalid('tie_break_order')
    return [x for x in value if x != 'draw_lots'] + ['draw_lots']
