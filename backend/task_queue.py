from concurrent.futures import ThreadPoolExecutor

EXECUTOR = ThreadPoolExecutor(max_workers=2)

def enqueue(fn, *args, **kwargs):
    return EXECUTOR.submit(fn, *args, **kwargs)
