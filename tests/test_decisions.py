import pytest
from forecastlab.decisions import capacity_plan, inventory_plan


@pytest.fixture
def rows():
    return [{'date':f'2025-01-0{i+1}', 'prediction':x, 'upper':x+10}
            for i, x in enumerate([80, 120, 150, 50, 100, 100, 100])]


def test_capacity_hand_calculation(rows):
    result = capacity_plan(rows, 100)
    assert result['overloaded_days'] == 2
    assert result['total_overflow'] == 70
    assert result['total_expected'] == 700
    assert result['extra_daily_capacity'] == 50


def test_capacity_multiplier_and_no_overflow(rows):
    assert capacity_plan(rows, 100, .5)['total_expected'] == 350
    assert capacity_plan(rows, 1000)['total_overflow'] == 0


def test_inventory_hand_calculation(rows):
    result = inventory_plan(rows, on_hand=100, on_order=50, lead_days=2, review_days=1, safety_stock=20)
    assert result['expected_protection_demand'] == 350
    assert result['target_stock'] == 370
    assert result['recommended_order'] == 220
    assert result['potential_shortfall_before_delivery'] == 100


def test_inventory_never_orders_negative_and_rejects_unknown_horizon(rows):
    assert inventory_plan(rows, 10000, 0, 2, 1, 0)['recommended_order'] == 0
    with pytest.raises(ValueError, match='horizon'):
        inventory_plan(rows, 0, 0, 7, 1, 0)
