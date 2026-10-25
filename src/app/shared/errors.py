class AcademicPlatformError(Exception):
    """Base exception for all domain and platform errors."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class UserNotFoundError(AcademicPlatformError):
    def __init__(self, message: str = "User not found") -> None:
        super().__init__(message, code="USER_NOT_FOUND")


class ServiceNotFoundError(AcademicPlatformError):
    def __init__(self, message: str = "Service or offer not found") -> None:
        super().__init__(message, code="SERVICE_NOT_FOUND")


class ServiceNotPublishedError(AcademicPlatformError):
    def __init__(self, message: str = "This service is not currently available for purchase") -> None:
        super().__init__(message, code="SERVICE_NOT_PUBLISHED")


class OrderInvalidStateError(AcademicPlatformError):
    def __init__(self, message: str = "Order transition is invalid") -> None:
        super().__init__(message, code="ORDER_INVALID_STATE")


class PaymentVerificationError(AcademicPlatformError):
    def __init__(self, message: str = "Payment verification failed") -> None:
        super().__init__(message, code="PAYMENT_VERIFICATION_FAILED")


class InsufficientEntitlementError(AcademicPlatformError):
    def __init__(self, message: str = "You do not have an active subscription or entitlement for this service") -> None:
        super().__init__(message, code="INSUFFICIENT_ENTITLEMENT")


class AcademicIntegrityViolationError(AcademicPlatformError):
    def __init__(self, message: str = "This request violates academic integrity policy") -> None:
        super().__init__(message, code="ACADEMIC_INTEGRITY_VIOLATION")


class IdempotencyConflictError(AcademicPlatformError):
    def __init__(self, message: str = "This operation has already been processed") -> None:
        super().__init__(message, code="IDEMPOTENCY_CONFLICT")
