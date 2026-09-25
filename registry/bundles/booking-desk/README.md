# booking-desk

Takes table reservations for one restaurant. Availability comes from the
restaurant's own settings (opening hours per weekday, closed dates, slot length,
bookings per slot, largest party), never from the model. Bookings are stored in
a per-tenant ledger that no other tenant can see.

- `check_availability(date, party_size)`: accepts `YYYY-MM-DD`, `today`, `tomorrow` or a weekday
  name, in the restaurant's time zone. Past times and full slots are excluded.
- `book_table(...)`: re-checks availability, and is idempotent per contact and slot.
  Returns a `BK-XXXXXX` reference.
- `cancel_booking(reference, contact)`: the contact must match the booking.

`require_tool = "check_availability"`: the agent may not answer before it has looked at
real availability.

```bash
plnt install booking-desk --tenant luigis \
  --config business_name="Luigi's" --config handoff_contact=+39-06-555-0100 \
  --config timezone=Europe/Rome --config hours_fri="12:00-15:00, 19:00-23:00"
```
