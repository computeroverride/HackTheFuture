import time


class EntryButton:
    """
    Entry zone button.

    Function:
    - Reads DI2 button.
    - When pressed, generates a unique product ID.
    """

    def __init__(self, adam, settings):
        self.adam = adam
        self.settings = settings

        self.last_button_state = False
        self.product_counter = 0

    def read_button(self) -> bool:
        return self.adam.read_di(self.settings.di2_address)

    def get_product_id_if_pressed(self):
        current_state = self.read_button()

        product_id = None

        # Rising edge detection:
        # only create ID when button changes from OFF to ON.
        if current_state and not self.last_button_state:
            self.product_counter += 1

            timestamp = int(time.time())

            product_id = (
                f"P{self.product_counter:04d}-"
                f"{timestamp}"
            )

        self.last_button_state = current_state

        return product_id