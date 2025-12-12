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
