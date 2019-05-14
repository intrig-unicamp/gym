from collections import deque
from datetime import datetime, timedelta
from gym.common.info import Content


class Time(Content):
    def __init__(self):
        Content.__init__(self)
        self.timestamp = self.when_to_str(datetime.now())
        # self._keys = ['when', 'duration', 'repeat', 'every']

    def past_now(self, when):
        t_now = datetime.now()
        t = datetime.strptime(when, '%a, %d %b %Y %H:%M:%S')
        return t_now >= t

    def when_to_str(self, when):
        if isinstance(when, datetime):
            self.when = when.strftime("%a, %d %b %Y %H:%M:%S")
            return self.when
        return None

    def when_from_str(self, when):
        if isinstance(when, str):
            self.when = datetime.strptime(when, '%a, %d %b %Y %H:%M:%S')
            return self.when
        return None

    def now_after(self, hours=None, mins=None, secs=None):
        t_now = datetime.now()
        diff = timedelta(hours=hours, minutes=mins, seconds=secs)
        ahead = t_now + diff
        return ahead


class Scheduler:
    def __init__(self):
        self.queue = deque()
        self.waiting = {}
        self.tasks_tree = {}
        self.finished = {}

    def enqueue(self, entrypoint, tasks):
        entry_id = entrypoint.get('id')
        if entry_id not in self.tasks_tree:
            self.queue.append(entry_id)
            self.waiting[entry_id] = deque()
            self.tasks_tree[entry_id] = deque()
            self.finished[entry_id] = {}
            for task in tasks:
                (prefix, output) = task
                self.waiting[entry_id].append(task)
                self.tasks_tree[entry_id].append(output.get('id'))

    def get_next(self, entry_id, finished_task):
        if entry_id in self.tasks_tree:
            task_id = finished_task.get('id')
            if task_id in self.tasks_tree[entry_id]:
                self.finished[entry_id][task_id] = finished_task
                index_task = list(self.tasks_tree[entry_id]).index(task_id)
                if index_task <= len(self.tasks_tree[entry_id]):
                    next_index = index_task + 1
                    next_task = self.waiting[entry_id][next_index]
                    return next_task
        return None

    def is_finished(self, entry_id):
        if entry_id in self.tasks_tree:
            waiting_ids = self.tasks_tree[entry_id]
            finished_ids = self.finished[entry_id].keys()
            acks = all([ True if task_id in finished_ids else False for task_id in waiting_ids ])
            return acks
        return True

    def clear_batch(self, entry_id):
        if entry_id in self.tasks_tree:
            self.queue.remove(entry_id)
            del self.waiting[entry_id]
            del self.tasks_tree[entry_id]

    def has_entry(self, entrypoint_id):
        if entrypoint_id in self.tasks_tree:
            return True
        return False
