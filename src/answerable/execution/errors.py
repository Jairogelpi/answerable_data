class ExecutionError(RuntimeError):
    pass


class UnsafeQuery(ExecutionError):
    pass


class RetryableExecutionError(ExecutionError):
    pass


class ExecutionTimedOut(ExecutionError):
    pass


class ExecutionCancelled(ExecutionError):
    pass


class IdempotencyConflict(ExecutionError):
    pass


class UnsafePython(ExecutionError):
    pass
