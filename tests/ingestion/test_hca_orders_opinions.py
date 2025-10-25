import sys
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.graph.models import NodeType
from src.ingestion.hca import crawl_year


def test_crawl_year_extracts_orders_and_opinions():
    html_text = dedent(
        """
        <ul>
            <li>
                <a href="case.pdf">Smith v Jones [2020] HCA 1</a>
                Catchwords: Civil procedure
                Legislation: Sample Act 2000 (Cth)
            </li>
        </ul>
        """
    )

    pdf_text = dedent(
        """
        IN THE HIGH COURT OF AUSTRALIA
        Smith v Jones
        [2020] HCA 1

        FINAL ORDERS
        1. Appeal allowed.
        2. The respondent is to pay the appellant's costs.

        Cases cited:
        Follows: Example v Example [2010] FCA 3

        Legislation cited:
        Sample Act 2000 (Cth)

        Kiefel CJ concurring.
        Keane J concurring.
        Gordon J dissenting.
        """
    )

    nodes, edges = crawl_year(
        html_text=html_text,
        pdfs={"[2020] HCA 1": pdf_text.encode("utf-8")},
        panel_size=3,
    )

    case_nodes = [n for n in nodes if n["type"] == NodeType.CASE.value]
    assert case_nodes, "expected at least one case node"
    case_node = next(n for n in case_nodes if n["id"] == "[2020] HCA 1")

    assert case_node["final_orders"] == [
        "Appeal allowed.",
        "The respondent is to pay the appellant's costs.",
    ]
    assert case_node["panel_opinions"] == [
        {"judge": "Kiefel CJ", "opinion": "concurring"},
        {"judge": "Keane J", "opinion": "concurring"},
        {"judge": "Gordon J", "opinion": "dissenting"},
    ]

    simple_nodes = [n for n in nodes if n.get("type") == "case" and n["id"] == "[2020] HCA 1"]
    assert simple_nodes, "expected helper node for the case"
    assert simple_nodes[0]["final_orders"] == case_node["final_orders"]
    assert simple_nodes[0]["panel_opinions"] == case_node["panel_opinions"]

