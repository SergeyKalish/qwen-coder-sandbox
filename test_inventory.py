"""Tests for inventory.py - pytest tests for the 3 bugs and general functionality."""
import pytest
from inventory import Warehouse


class TestShipBug:
    """Test for bug #1: ship() with qty=0 should raise ValueError."""

    def test_ship_zero_qty_raises_error(self):
        """Shipping zero quantity should raise an error."""
        wh = Warehouse()
        wh.add("item1", 10)
        with pytest.raises(ValueError):
            wh.ship("item1", 0)

    def test_ship_negative_qty_raises_error(self):
        """Shipping negative quantity should raise an error."""
        wh = Warehouse()
        wh.add("item1", 10)
        with pytest.raises(ValueError):
            wh.ship("item1", -5)


class TestAvailableBug:
    """Test for bug #2: available() should return stock - reserved, not stock + reserved."""

    def test_available_with_reservation(self):
        """Available quantity should be stock minus reserved."""
        wh = Warehouse()
        wh.add("item1", 10)
        wh.reserve("item1", 3)
        # stock=7, reserved=3, available should be 7, not 10
        assert wh.available("item1") == 7

    def test_available_no_reservation(self):
        """Available quantity equals stock when nothing is reserved."""
        wh = Warehouse()
        wh.add("item1", 10)
        assert wh.available("item1") == 10

    def test_available_fully_reserved(self):
        """Available quantity should be 0 when all stock is reserved."""
        wh = Warehouse()
        wh.add("item1", 10)
        wh.reserve("item1", 10)
        assert wh.available("item1") == 0


class TestCancelReserveBug:
    """Test for bug #3: cancel_reserve() with qty=0 should not modify stock."""

    def test_cancel_reserve_zero_qty(self):
        """Cancelling zero reservation should not change stock."""
        wh = Warehouse()
        wh.add("item1", 10)
        initial_stock = wh.stock.get("item1", 0)
        wh.cancel_reserve("item1", 0)  # Should not affect anything
        assert wh.stock["item1"] == initial_stock

    def test_cancel_reserve_normal(self):
        """Normal cancel_reserve should work correctly."""
        wh = Warehouse()
        wh.add("item1", 10)
        wh.reserve("item1", 5)
        assert wh.stock["item1"] == 5
        wh.cancel_reserve("item1", 3)
        assert wh.stock["item1"] == 8
        assert wh.reserved["item1"] == 2


class TestGeneralFunctionality:
    """General tests for warehouse functionality."""

    def test_add_positive_qty(self):
        """Adding positive quantity should work."""
        wh = Warehouse()
        wh.add("item1", 5)
        assert wh.stock["item1"] == 5

    def test_add_negative_qty_raises_error(self):
        """Adding negative quantity should raise ValueError."""
        wh = Warehouse()
        with pytest.raises(ValueError):
            wh.add("item1", -5)

    def test_reserve_insufficient_stock(self):
        """Reserving more than available should return False."""
        wh = Warehouse()
        wh.add("item1", 5)
        result = wh.reserve("item1", 10)
        assert result is False
        assert wh.stock["item1"] == 5  # Stock unchanged

    def test_reserve_and_ship(self):
        """Full workflow: add, reserve, ship."""
        wh = Warehouse()
        wh.add("item1", 20)
        wh.reserve("item1", 5)
        assert wh.stock["item1"] == 15
        assert wh.reserved["item1"] == 5
        wh.ship("item1", 10)
        assert wh.stock["item1"] == 5

    def test_multiple_skus(self):
        """Warehouse should handle multiple SKUs independently."""
        wh = Warehouse()
        wh.add("item1", 10)
        wh.add("item2", 20)
        wh.reserve("item1", 3)
        assert wh.available("item1") == 7
        assert wh.available("item2") == 20
