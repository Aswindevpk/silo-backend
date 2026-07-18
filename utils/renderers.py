from rest_framework.renderers import JSONRenderer

class CustomJSONRenderer(JSONRenderer):
    """
    Custom renderer to ensure all success responses follow the uniform architecture:
    {
        "success": true,
        "message": "...",
        "data": ...
    }
    """
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get('response') if renderer_context else None
        
        # If response has an exception, it's handled by custom_exception_handler
        # The exception handler already formats it as success: false, message, errors
        if response and response.exception:
            return super().render(data, accepted_media_type, renderer_context)

        # For success responses, format them uniformly if not already formatted
        if isinstance(data, dict) and 'success' in data and 'message' in data:
            # View explicitly returned the correct envelope
            pass
        else:
            # Wrap the raw data
            message = "Request was successful."
            if isinstance(data, dict) and "message" in data:
                message = data.pop("message")
            elif isinstance(data, dict) and "Message" in data:
                message = data.pop("Message")
                
            # If view passed "data" inside dict
            if isinstance(data, dict) and "data" in data and len(data) == 1:
                data = data["data"]

            data = {
                "success": True,
                "message": message,
                "data": data
            }

        return super().render(data, accepted_media_type, renderer_context)
