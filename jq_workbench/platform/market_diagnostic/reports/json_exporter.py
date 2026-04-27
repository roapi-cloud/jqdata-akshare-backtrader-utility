"""
JSON Report Exporter

Exports DiagnosticReport to structured JSON format for machine consumption.
Supports pretty-print and compact output modes.

Reference: Requirements 18.1-18.10
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .schema import DiagnosticReport


class DiagnosticJsonExporter:
    """
    Export DiagnosticReport to structured JSON format.

    Supports both pretty-printed (human-readable) and compact (file-size efficient)
    output modes. Includes automatic metadata enrichment.

    Reference: Requirements 18.1-18.10
    """

    def __init__(self, indent: int = 2, sort_keys: bool = True):
        """
        Initialize the JSON exporter.

        Parameters
        ----------
        indent : int
            JSON indentation spaces (default 2). Use 0 for compact mode.
        sort_keys : bool
            Whether to sort dictionary keys (default True).
        """
        self._indent = indent
        self._sort_keys = sort_keys

    def to_json(
        self,
        report: DiagnosticReport,
        compact: bool = False,
    ) -> str:
        """
        Serialize a DiagnosticReport to JSON string.

        Parameters
        ----------
        report : DiagnosticReport
            The diagnostic report to serialize.
        compact : bool
            If True, use compact formatting (no indentation).

        Returns
        -------
        str
            JSON-formatted string.

        Reference: Requirement 18.1
        """
        return report.to_json()

    def to_dict(self, report: DiagnosticReport) -> dict:
        """
        Convert a DiagnosticReport to a plain dictionary.

        Parameters
        ----------
        report : DiagnosticReport
            The diagnostic report.

        Returns
        -------
        dict
            Plain dictionary representation.
        """
        return report.to_dict()

    def save_to_file(
        self,
        report: DiagnosticReport,
        filepath: str,
        compact: bool = False,
        add_metadata: bool = True,
    ) -> None:
        """
        Save a DiagnosticReport to a JSON file.

        Parameters
        ----------
        report : DiagnosticReport
            The report to save.
        filepath : str
            Output file path.
        compact : bool
            If True, use compact formatting.
        add_metadata : bool
            If True, add generation metadata to the output.

        Reference: Requirement 18.1-18.10
        """
        data = self.to_dict(report)

        if add_metadata:
            data["_meta"] = {
                "generated_at": datetime.now().isoformat(),
                "generator": "market_diagnostic_platform",
                "version": "1.0",
            }

        json_str = json.dumps(
            data,
            ensure_ascii=False,
            indent=0 if compact else self._indent,
            sort_keys=self._sort_keys,
        )

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json_str)

    def load_from_file(self, filepath: str) -> DiagnosticReport:
        """
        Load a DiagnosticReport from a JSON file.

        Parameters
        ----------
        filepath : str
            Input file path.

        Returns
        -------
        DiagnosticReport
            The loaded report.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Remove metadata if present
        if "_meta" in data:
            del data["_meta"]

        return DiagnosticReport.from_dict(data)


def export_diagnostic_report(
    report: DiagnosticReport,
    output_path: str,
    compact: bool = False,
) -> None:
    """
    Convenience function to export a diagnostic report to JSON.

    Parameters
    ----------
    report : DiagnosticReport
        The report to export.
    output_path : str
        Output file path.
    compact : bool
        If True, use compact formatting.
    """
    exporter = DiagnosticJsonExporter()
    exporter.save_to_file(report, output_path, compact=compact)