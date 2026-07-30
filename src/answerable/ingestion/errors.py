class IngestionError(RuntimeError):
    pass


class UnsupportedFormat(IngestionError):
    pass


class InvalidSource(IngestionError):
    pass
