"""Custom exception classes for the API."""


class ProjectNotFoundError(Exception):
    """Raised when a project is not found."""

    def __init__(self, project_id: str):
        self.project_id = project_id
        super().__init__(f"Project with ID '{project_id}' not found")


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class FileTooLargeError(Exception):
    """Raised when an uploaded file exceeds the maximum size limit."""

    def __init__(self, file_size: int, max_size: int):
        self.file_size = file_size
        self.max_size = max_size
        super().__init__(
            f"File size ({file_size} bytes) exceeds maximum allowed size ({max_size} bytes)"
        )


class InvalidFileTypeError(Exception):
    """Raised when an uploaded file has an unsupported type."""

    def __init__(self, file_type: str, allowed_types: list[str]):
        self.file_type = file_type
        self.allowed_types = allowed_types
        super().__init__(
            f"File type '{file_type}' is not supported. "
            f"Allowed types: {', '.join(allowed_types)}"
        )


class FileNotFoundError(Exception):
    """Raised when a file is not found."""

    def __init__(self, file_id: str, project_id: str):
        self.file_id = file_id
        self.project_id = project_id
        super().__init__(f"File with ID '{file_id}' not found in project '{project_id}'")
