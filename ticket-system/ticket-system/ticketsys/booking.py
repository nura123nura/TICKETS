"""Билет брондау және сатып алу логикасы."""
from dataclasses import dataclass, field
from itertools import count


class BookingError(Exception):
    """Брондау қатесі (орын бос емес, іс-шара жоқ және т.б.)."""


@dataclass
class Event:
    event_id: int
    title: str
    seats: int
    price: float
    sold: set = field(default_factory=set)

    def free_seats(self) -> int:
        return self.seats - len(self.sold)


class TicketService:
    def __init__(self):
        self._events = {}
        self._ticket_ids = count(1)
        self._tickets = {}

    def add_event(self, event: Event) -> None:
        self._events[event.event_id] = event

    def buy(self, event_id: int, seat: int, buyer: str) -> dict:
        event = self._events.get(event_id)
        if event is None:
            raise BookingError("Іс-шара табылмады")
        if not 1 <= seat <= event.seats:
            raise BookingError("Орын нөмірі қате")
        if seat in event.sold:
            raise BookingError("Бұл орын бұрын сатылған")
        event.sold.add(seat)
        ticket = {"id": next(self._ticket_ids), "event": event_id,
                  "seat": seat, "buyer": buyer, "price": event.price}
        self._tickets[ticket["id"]] = ticket
        return ticket

    def refund(self, ticket_id: int) -> float:
        ticket = self._tickets.pop(ticket_id, None)
        if ticket is None:
            raise BookingError("Билет табылмады")
        self._events[ticket["event"]].sold.discard(ticket["seat"])
        return ticket["price"]
