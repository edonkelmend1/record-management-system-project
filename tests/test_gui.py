import unittest

from record_management_system.gui import form_fields_for
from record_management_system.records import AIRLINE, CLIENT, FLIGHT


class GuiTests(unittest.TestCase):
    def test_form_fields_for_client_excludes_generated_fields(self):
        fields = form_fields_for(CLIENT)

        self.assertIn("Name", fields)
        self.assertNotIn("ID", fields)
        self.assertNotIn("Type", fields)

    def test_form_fields_for_airline(self):
        self.assertEqual(form_fields_for(AIRLINE), ["Company Name"])

    def test_form_fields_for_flight(self):
        self.assertEqual(
            form_fields_for(FLIGHT),
            ["Client_ID", "Airline_ID", "Date", "Start City", "End City"],
        )


if __name__ == "__main__":
    unittest.main()

