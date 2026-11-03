import unittest

from ticketsys import BookingError, Event, TicketService


class TicketServiceTest(unittest.TestCase):
    def setUp(self):
        self.svc = TicketService()
        self.svc.add_event(Event(1, "Концерт", seats=3, price=5000.0))

    def test_buy_ok(self):
        t = self.svc.buy(1, 2, "Айгерім")
        self.assertEqual(t["seat"], 2)
        self.assertEqual(self.svc._events[1].free_seats(), 2)

    def test_double_buy_fails(self):
        self.svc.buy(1, 1, "А")
        with self.assertRaises(BookingError):
            self.svc.buy(1, 1, "Б")

    def test_bad_seat(self):
        with self.assertRaises(BookingError):
            self.svc.buy(1, 99, "А")

    def test_unknown_event(self):
        with self.assertRaises(BookingError):
            self.svc.buy(7, 1, "А")

    def test_refund_frees_seat(self):
        t = self.svc.buy(1, 3, "А")
        self.assertEqual(self.svc.refund(t["id"]), 5000.0)
        self.assertEqual(self.svc._events[1].free_seats(), 3)


if __name__ == "__main__":
    unittest.main()
