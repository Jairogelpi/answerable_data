class PersistenceError(RuntimeError):
    pass


class RecordNotFound(PersistenceError):
    pass


class RecordAlreadyExists(PersistenceError):
    pass


class ConcurrencyConflict(PersistenceError):
    pass


class ImmutableRecordError(PersistenceError):
    pass
