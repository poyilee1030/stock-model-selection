from stock_model_selection.domain.errors import DomainError, MissingDerivationVersionError


class DataCenterError(DomainError):
    pass


class ResponseSchemaError(DataCenterError):
    pass


class MissingDerivationError(MissingDerivationVersionError, ResponseSchemaError):
    pass


class MissingProvenanceError(ResponseSchemaError):
    pass


class PitViolationError(DataCenterError):
    pass


class RequestLimitError(DataCenterError):
    pass


class DataCenterRequestError(DataCenterError):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


class BadRequestError(DataCenterRequestError):
    pass


class UnauthorizedError(DataCenterRequestError):
    pass


class NotFoundError(DataCenterRequestError):
    pass
