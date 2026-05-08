from typing import Any, Sequence
from parsimonious import Grammar, NodeVisitor
from parsimonious.nodes import Node
from json import dumps
import pytest


class MyVisitor(NodeVisitor):
    def __init__(self) -> None:
        self.race_results = []

    def generic_visit(self, node: Node, visited_children: Sequence[Any]):
        return None
    
    def visit_heat_race_result_points(self, node: Node, visited_children: Sequence[Any]):
        placement, bib_number, name, year, school, seed, score, heat_num, points = (
            node.children
        )
    
        return dict(
            placement=placement.text,
            bib_number=bib_number.text,
            name=name.text,
            year=year.text,
            school=school.text,
            seed=seed.text,
            score=score.text,
            heat_num=heat_num.text,
            points=points.text,
        )
    
    def visit_heat_race_result_no_points(self, node: Node, visited_children: Sequence[Any]):
        placement, bib_number, name, year, school, seed, score, heat_num = (
            node.children
        )
    
        return dict(
            placement=placement.text,
            bib_number=bib_number.text,
            name=name.text,
            year=year.text,
            school=school.text,
            seed=seed.text,
            score=score.text,
            heat_num=heat_num.text,
            points=None,
        )

    def visit_non_heat_race_result_points(self, node: Node, visited_children: Sequence[Any]):
        placement, bib_number, name, year, school, seed, score, points = (
            node.children
        )
        return dict(
            placement=placement.text,
            bib_number=bib_number.text,
            name=name.text,
            year=year.text,
            school=school.text,
            seed=seed.text,
            score=score.text,
            nh_points=points.text,
        )

grammar = Grammar(
    r"""
        race         = race_results
        race_results = finals? race_result* ~r"[^$]*?\n"
        race_result  = (heat_race_result / non_heat_race_result) ws "\n"

        heat_race_result           = (heat_race_result_points / heat_race_result_no_points)
        heat_race_result_points    = placement bib_number name year school seed score heat_num points
        heat_race_result_no_points = placement bib_number name year school seed score heat_num

        non_heat_race_result           = (non_heat_race_result_points / non_heat_race_result_no_points)
        non_heat_race_result_points    = placement bib_number name year school seed score nh_points
        non_heat_race_result_no_points = placement bib_number name year school seed score

        finals = "Finals\n"

        placement   = value{3} space
        bib_number  = value{6} space
        name        = value{18} space
        year        = value{2} space
        school      = value{30} space
        seed        = ""
        score       = value{8} space
        heat_num    = value{3} space
        points      = value{5} space
        nh_points   = value{6} space
        value       = ~r"."
        space       = " "
        ws          = ~r"[ ]*"
    """
)


@pytest.fixture
def visitor():
    return MyVisitor()


def test_heat_race_result(visitor: MyVisitor):
    text = """  1 #  310 Duhaney, Talia      5 SFA                               33.65   7  10   """
    tree = grammar.default("heat_race_result").parse(text)
    print(tree)

def test_heat_race_result_no_points(visitor: MyVisitor):
    text = """ 11 #  296 Echezona, Ijeoma    5 Sacred Heart - H                  42.94   8 """
    tree = grammar.default("heat_race_result").parse(text)
    print(tree)


def test_non_heat_race_result():
    text = """  1 #  482 Curmi, Phoebe       3 Joseph YORK                       33.09   10   """
    tree = grammar.default("non_heat_race_result").parse(text)
    print(tree)


def test_non_heat_race_result_no_points(visitor: MyVisitor):
    text = (
        """  9 #  572 Vincent, Morgan     1 John Paul                       4:35.90 """
    )
    tree = grammar.default("non_heat_race_result").parse(text)
    print(tree)

def test_race_results(race_results: str, visitor: MyVisitor):
    tree = grammar.default("race_results").parse(race_results)
    print(tree)


def test_race(race_results: str, visitor: MyVisitor):
    tree = grammar.default("race").parse(race_results)
    visitor.visit(tree)
    print()
    print(dumps(visitor.race_results, indent=2))



@pytest.fixture
def race_results():
    return """Finals
  1 #  575 Horowitz, Ava       2 John Paul                         16.01   7  10   
  2 #  354 Daiga, Astrid       1 SMSG                              16.55   5   8   
  3 #  481 Brennan, Abigail    2 Joseph YORK                       16.57   7   6   
  4 #    2 Duffell, Jenny      K Annunciation                      16.61   7   5   
  5 #  576 Offurum, Olanma     2 John Paul                         16.78   6   4   
  6 #  466 Martin, Philippa    2 Joseph Bxvill                     17.29   5   3   
  7 #  415 Tajong, Alexa       1 BARN                              17.59   4   2   
  8 #  414 Rooney, Kailyn      1 BARN                              17.69   4   1   
  9 #  359 Matesic, Valentin   2 SMSG                              17.77   7 
 10 #  626 DiMiceli, Valenti   2 Annunciation                      18.07   7 
 11 #   10 Dellamedaglia, Am   2 Annunciation                      18.11   6 
 12 #  625 Donnelly, Molly     2 Annunciation                      18.36   7 
 13 #  291 Echezona, Amara     2 Sacred Heart - H                  18.54   6 
 14 #    9 Delaney, Eleanor    2 Annunciation                      18.71   7 
 15 #  236 Cassanova, Ryleig   1 OL Grace                          18.85   2 
 16 #  365 Taylor, Adelaide    2 SMSG                              18.88   3 
 17 #  334 Wade, Olivia        2 SFDC                              19.01   6 
 18 #   11 Dellamedaglia, Ol   2 Annunciation                      19.02   6 
 19 #  515 Salvatico, Eliana   1 Patrick                           19.26   4 
 20 #  573 Castiglia, Aspen    2 John Paul                         19.48   6 
 21 #  480 Alcide, Alicia      1 Joseph YORK                       19.58   2 
 22 #  514 Salvatico, Angeli   1 Patrick                           19.62   2 
 23 #  355 Peralta, Angelina   1 SMSG                              19.82   5 
 24 #  513 Johnson, Valerie    1 Patrick                           19.86   4 
 25 #  364 Taylor, Aine        2 SMSG                              20.08   6 
 26 #  516 Thomley, Annabell   1 Patrick                           20.32   4 
 27 #  437 Charles, Josie      1 Benedict                          20.46   1 
 28 #  333 Williams, Alessan   1 SFDC                              20.62   1 
 29 #  571 Torres, Carla       K John Paul                         20.96   1 
 30 #    5 Passarinho, Sophi   K Annunciation                      21.25   2 
 31 #  438 Capezullo, Camila   2 Benedict                          21.31   6 
 32 #  572 Vincent, Morgan     1 John Paul                         21.55   2 
 33 #  235 Anderson, Brooke    1 OL Grace                          21.85   2 
 34 #  237 Ford, Tinsley       1 OL Grace                          21.86   2 
 35 #  360 Purce, Mary Elza    2 SMSG                              21.94   7 
 36 #   83 Martin, Molly       1 IHM                               22.12   5 
 37 #  356 Sanchez, Ximena     1 SMSG                              22.16   4 
 38 #  233 Willis, Kali       PK OL Grace                          22.29   1 
 39 #  461 Collingham, Sophi  PK Joseph Bxvill                     22.30   1 
 40 #  434 Hines, Jenna        K Benedict                          22.52   5 
 41 #  413 Jankovic, Abigail   1 BARN                              22.72   4 
 42 #  621 Belair, Matilda     1 CYO Unattached                    23.38   2 
 43 #   82 Baltazar, Ava       1 IHM                               23.89   5 
 44 #  241 Rodriguez, Ellie    2 OL Grace                          24.04   3 
 45 #  412 Fernandez, Isabel   1 BARN                              24.06   4 
 
"""


@pytest.fixture
def race() -> str:
    return """"""
