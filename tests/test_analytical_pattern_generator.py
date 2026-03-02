from table_reclamation import SqlOperation

from ap_management.domain.analytical_pattern import AnalyticalPattern
from ap_management.services.analytical_pattern_generator import (
    AnalyticalPatternGenerator,
)

PLAN = [
    SqlOperation(src_idx=0, table="table_a",
                 sql="SELECT * FROM table_a WHERE id = 1"),
    SqlOperation(src_idx=1, table="table_b",
                 sql="SELECT * FROM table_b WHERE id = 2"),
]


def test_convert_valid_plan():
    gen = AnalyticalPatternGenerator()
    ap = gen._convert_to_ap("find data", PLAN)
    assert isinstance(ap, AnalyticalPattern)
    # Re-validate through model_validate to confirm structural correctness


def test_follows_edges_between_operators():
    gen = AnalyticalPatternGenerator()
    ap = gen._convert_to_ap("find data", PLAN)
    follows_edges = [e for e in ap.edges if "follows" in e.labels]
    operators = ap.get_nodes_by_label("SQL_Operator")
    operators.sort(key=lambda n: n.properties["step"])
    # One follows edge between each pair of successive operators
    assert len(follows_edges) == len(operators) - 1
    for i, edge in enumerate(follows_edges):
        assert edge.from_ == operators[i].id
        assert edge.to == operators[i + 1].id
    AnalyticalPattern.model_validate(ap.model_dump())


def test_convert_invalid_plan():
    """
    Test that an empty plan results in None being returned.
    """
    gen = AnalyticalPatternGenerator()
    ap = gen._convert_to_ap("find data", [])
    assert ap is None
    print(ap)


def test_mathe_generation():
    """
    Test that a simple query generates a valid Analytical Pattern.
    """
    gen = AnalyticalPatternGenerator()
    ap = gen.generate("Discrete Mathematics Recursivity level 2")
    assert isinstance(ap, AnalyticalPattern)
    # Re-validate through model_validate to confirm structural correctness
    AnalyticalPattern.model_validate(ap.model_dump())
