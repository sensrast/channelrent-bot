import time
from collections import defaultdict, deque

_buckets = defaultdict(lambda: deque(maxlen=10))

def allow(user_id, max_per_sec=2):
    now = time.time()
    dq = _buckets[user_id]
    while dq and now - dq[0] > 1.0:
        dq.popleft()
    if len(dq) >= max_per_sec:
        return False
    dq.append(now)
    return True
