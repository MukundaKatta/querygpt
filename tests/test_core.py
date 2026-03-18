"""Tests for Querygpt."""
from src.core import Querygpt
def test_init(): assert Querygpt().get_stats()["ops"] == 0
def test_op(): c = Querygpt(); c.process(x=1); assert c.get_stats()["ops"] == 1
def test_multi(): c = Querygpt(); [c.process() for _ in range(5)]; assert c.get_stats()["ops"] == 5
def test_reset(): c = Querygpt(); c.process(); c.reset(); assert c.get_stats()["ops"] == 0
def test_service_name(): c = Querygpt(); r = c.process(); assert r["service"] == "querygpt"
