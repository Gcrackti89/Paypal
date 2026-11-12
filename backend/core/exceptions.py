from fastapi import HTTPException, status


class AppException(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "APP_ERROR"):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found", status_code=404, code="NOT_FOUND")


class AuthenticationError(AppException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401, code="AUTHENTICATION_FAILED")


class AuthorizationError(AppException):
    def __init__(self, message: str = "Not authorized"):
        super().__init__(message, status_code=403, code="FORBIDDEN")


class PayPalError(AppException):
    def __init__(self, message: str = "PayPal operation failed", status_code: int = 502):
        super().__init__(message, status_code=status_code, code="PAYPAL_ERROR")


class PayPalNotConfiguredError(AppException):
    def __init__(self):
        super().__init__(
            "PayPal Sandbox is not configured. Please add credentials in Settings.",
            status_code=503,
            code="PAYPAL_NOT_CONFIGURED",
        )


class AINotConfiguredError(AppException):
    def __init__(self):
        super().__init__(
            "AI provider is not configured. Please add OpenAI API key in Settings.",
            status_code=503,
            code="AI_NOT_CONFIGURED",
        )


class ValidationError(AppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=422, code="VALIDATION_ERROR")


class ApprovalError(AppException):
    def __init__(self, message: str = "Approval required or expired"):
        super().__init__(message, status_code=409, code="APPROVAL_ERROR")


class DuplicateError(AppException):
    def __init__(self, message: str = "Duplicate request"):
        super().__init__(message, status_code=409, code="DUPLICATE_ERROR")


class RateLimitError(AppException):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, status_code=429, code="RATE_LIMIT")
