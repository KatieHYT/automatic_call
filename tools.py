import queue

class QueueStream:
    def __init__(self):
        self.q = queue.Queue(maxsize=-1)

    def read(self, chunk: int) -> bytes:
        return self.q.get()

    def write(self, chunk: bytes):
        self.q.put(chunk)
