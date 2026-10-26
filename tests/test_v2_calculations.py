"""Exercise the v2 calculation and import functions without rendering Streamlit."""
import ast
import io
import math
from pathlib import Path
from types import SimpleNamespace
import pandas as pd
import pytest

@pytest.fixture
def core():
    names = {'CATEGORIES', 'CAT_KEYS', 'CAT_LABEL', 'CAT_BUCKET', 'CSV_KEYWORDS'}
    functions = {'compute', 'project_growth', 'match_category', 'import_csv'}
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'app.py').read_text())
    nodes = [n for n in tree.body if
             (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets))
             or (isinstance(n, ast.FunctionDef) and n.name in functions)]
    scope = {'math': math, 'pd': pd, 'st': SimpleNamespace(session_state={})}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'app_core', 'exec'), scope)
    return scope

def test_budget_arithmetic(core):
    expenses = dict.fromkeys(core['CAT_KEYS'], 0.0)
    expenses.update(housing=900, food=400, transport=200, utilities=150, insurance=100,
                    healthcare=50, entertainment=150, other=50)
    result = core['compute'](8000, 1500, 3000, expenses, 10000)
    assert result['total'] == 2000
    assert result['remaining'] == 6000 and result['unassigned'] == 4500
    assert result['months_to_goal'] == 5

def test_zero_budget_and_unfunded_goal(core):
    result = core['compute'](0, 0, 0, dict.fromkeys(core['CAT_KEYS'], 0), 1000)
    assert result['months_to_goal'] is None
    assert result['expense_ratio'] == 0

def test_zero_return_projection(core):
    growth = core['project_growth'](100, 1000, 0, 2)
    assert list(growth['balance']) == [1000, 2200, 3400]

def test_csv_monthly_average(core):
    state = core['st'].session_state
    state['csv_file'] = io.StringIO('category,amount,month\nRent,900,2026-09\nRent,1100,2026-10\nNetflix,40,2026-09\n')
    core['import_csv']()
    assert state['exp_housing'] == 1000 and state['exp_entertainment'] == 20
    assert state['csv_msg'][0] == 'success'
