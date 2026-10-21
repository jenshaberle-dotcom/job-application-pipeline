"""Advisory progress contract. Never used as permission to replay or release."""
import json
import os
import threading
import time


class WorkloadProgress:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.started = time.time()
        self.last_progress = self.started
        self.completed = 0
        self.errors = 0

    def publish(self, phase, current, *, changed=False):
        with self.lock:
            now = time.time()
            if changed:
                self.last_progress = now
            value = dict(schema_version="rcc.workload.progress.v1", phase=phase,
                current=current[:160], completed=self.completed, errors=self.errors,
                started_at=self.started, updated_at=now, last_progress_at=self.last_progress)
            try:
                temporary = self.path.with_suffix('.tmp')
                temporary.write_text(json.dumps(value), encoding='utf-8')
                os.replace(temporary, self.path)
            except OSError:
                pass  # Telemetry loss must never change business execution semantics.

    def begin(self, key):
        stop = threading.Event()
        self.publish("WORKING", key, changed=True)
        def beat():
            while not stop.wait(5):
                self.publish("WORKING", key)
        thread = threading.Thread(target=beat, daemon=True)
        thread.start()
        return stop, thread

    def end(self, key, worker, failed=False):
        stop, thread = worker
        stop.set()
        thread.join(timeout=1)
        if failed:
            self.errors += 1
        else:
            self.completed += 1
        self.publish("STEP_FAILED" if failed else "STEP_COMPLETED", key, changed=True)
