import json
from datetime import datetime
from typing import Any

from models.report import InterviewReport


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def export_report_json(report: InterviewReport, pretty: bool = True) -> str:
    """Export interview report as JSON string.

    Args:
        report: The interview report to export.
        pretty: Whether to format with indentation.

    Returns:
        JSON string representation of the report.
    """
    data = report.model_dump()

    # Convert enums to their values
    def convert_enums(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: convert_enums(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_enums(item) for item in obj]
        elif hasattr(obj, "value"):
            return obj.value
        return obj

    data = convert_enums(data)

    if pretty:
        return json.dumps(data, indent=2, cls=DateTimeEncoder)
    return json.dumps(data, cls=DateTimeEncoder)


def export_report_dict(report: InterviewReport) -> dict:
    """Export interview report as a dictionary.

    Args:
        report: The interview report to export.

    Returns:
        Dictionary representation of the report.
    """
    data = report.model_dump()

    # Convert datetime objects to ISO strings
    def convert_datetimes(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: convert_datetimes(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_datetimes(item) for item in obj]
        elif hasattr(obj, "value"):
            return obj.value
        return obj

    return convert_datetimes(data)
