from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

class CustomAPIException(APIException):
    """
    Custom API exception allowing complete control over:
    - status_code: The HTTP status code to return (e.g., 400, 401, 403, 422).
    - message: The top-level 'message' string.
    - errors: Any custom structure (array, dict, string, or None).
    """
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "An error occurred processing your request."
    default_code = "bad_request"

    def __init__(self, message=None, status_code=None, errors=None):
        if status_code is not None:
            self.status_code = status_code
        
        self.detail = message if message is not None else self.default_detail
        # Complete control: Bind whatever error data structure the developer passes
        self.errors = errors
        super().__init__(detail=self.detail)


def custom_exception_handler(exc, context):
    """
    Catches all API exceptions and raw Python/Database exceptions,
    formatting them into a highly clean, uniform, camelCase error envelope.
    """
    # Let DRF process standard API exceptions first
    response = exception_handler(exc, context)

    # Base unhandled 500 Server Error structure
    error_payload = {
        "success": False,
        "message": "An unexpected error occurred on the server.",
        "errors": None
    }

    if response is not None:
        # Scenario A: Developer threw a CustomAPIException (Full Control over 'errors')
        if isinstance(exc, CustomAPIException):
            error_payload["message"] = str(exc.detail)
            error_payload["errors"] = exc.errors

        # Scenario B: Standard DRF Validation Errors (400 Bad Request)
        elif response.status_code == status.HTTP_400_BAD_REQUEST:
            error_payload["message"] = "Input validation failed."
            error_payload["errors"] = response.data

        # Scenario C: Other standard DRF exceptions (401, 403, 404, etc.)
        else:
            if isinstance(response.data, dict) and "detail" in response.data:
                error_payload["message"] = response.data["detail"]
                error_payload["errors"] = None
            else:
                error_payload["message"] = "An API exception occurred."
                error_payload["errors"] = response.data

        response.data = error_payload
        return response

    else:
        # Scenario D: Raw Python exceptions or DB crashes (500)
        return Response(error_payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
