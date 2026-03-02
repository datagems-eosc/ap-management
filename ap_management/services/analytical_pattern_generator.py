import logging
from pathlib import Path
from typing import List
from uuid import uuid4

from table_reclamation import AccessPlanner, SqlOperation

from ap_management.domain.analytical_pattern import AnalyticalPattern

logger = logging.getLogger(__name__)


class AnalyticalPatternGenerator:

    def generate(self, query: str) -> AnalyticalPattern:
        """
        Generate an Analytical Pattern based on the given query string.
        Argument:
            query: A natural language description of the analytical pattern to generate.
        Returns:
            An AnalyticalPattern object representing the generated pattern.
        """
        root_dir = Path(__file__).parent.parent.parent
        # TODO: Generalize the demo beyond mathe
        mathe_dir = root_dir / "assets" / "mathe"
        plan = AccessPlanner(tables_path=mathe_dir).generate_plan(query)
        if not plan or len(plan) == 0:
            raise ValueError("No SQL plan generated for the given query.")

        return self._convert_to_ap(query, plan)

    def _convert_to_ap(self, query: str, plan: List[SqlOperation]) -> AnalyticalPattern | None:
        """
        Convert a SQL plan into an Analytical Pattern object.
        Arguments:
            query: The original natural language query.
            plan: A list of SqlOperation objects representing the SQL plan.
        Returns:
            An AnalyticalPattern object representing the generated pattern.
        """
        if not plan:
            logger.warning("Received an empty SQL plan. Returning None.")
            return None

        ap_id = str(uuid4())
        nodes = []
        edges = []

        # Root Analytical_Pattern node
        nodes.append({
            "id": ap_id,
            "labels": ["Analytical_Pattern"],
            "properties": {
                "name": query,
                "description": query,
                "process": "query",
            },
        })

        operator_ids: List[str] = []
        for step, operation in enumerate(plan, start=1):
            logger.info(f"Generated operation: {operation}")

            operator_id = str(uuid4())
            input_id = str(uuid4())
            output_id = str(uuid4())

            # SQL Operator node
            nodes.append({
                "id": operator_id,
                "labels": ["Operator", "SQL_Operator"],
                "properties": {
                    "command": "query",
                    "queryType": "SELECT",
                    "query": operation.sql,
                    "step": step,
                    "type": "SQL Query",
                },
            })

            # Input dataset node (the source table)
            nodes.append({
                "id": input_id,
                "labels": ["cr:FileObject", "RelationalDatabase"],
                "properties": {
                    "name": operation.table,
                },
            })

            # Output dataset node
            nodes.append({
                "id": output_id,
                "labels": ["sc:Dataset"],
            })

            # AP --consist_of--> Operator
            edges.append({
                "from": ap_id,
                "labels": ["consist_of"],
                "to": operator_id,
            })

            # Operator --input--> InputDataset
            edges.append({
                "from": operator_id,
                "labels": ["input"],
                "to": input_id,
            })

            # Operator --output--> OutputDataset
            edges.append({
                "from": operator_id,
                "labels": ["output"],
                "to": output_id,
            })

            # Previous operator --follows--> current operator
            if step > 1:
                edges.append({
                    "from": operator_ids[step - 2],
                    "labels": ["follows"],
                    "to": operator_id,
                })

            operator_ids.append(operator_id)

        return AnalyticalPattern(nodes=nodes, edges=edges)
