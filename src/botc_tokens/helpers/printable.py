"""Create printable sheets based on a script json file."""
import math
from pathlib import Path

from wand.image import Image


class Printable:
    """Create printable sheets based on a script json file."""
    def __init__(self, output_dir, basename="page", padding=0, diameter=319):
        """Create a new printable object."""
        # 8.5"x11" at 300dpi is 2550 x 3300px
        # Subtracting 74px from each side to account for printer margins leaves 2402 x 3152px
        self.page = Image(width=2402, height=3152, resolution=(300, 300))
        self.current_x = 0
        self.current_y = 0
        self.next_row_should_be_inset = False
        self.output_dir = Path(output_dir)
        self.page_number = 1
        self.basename = basename
        self.padding = padding
        self.diameter = diameter

    def save_page(self):
        """Save the current page and reset the state."""
        # Don't save a blank sheet
        if self.current_x == 0 and self.current_y == 0:
            return
        self.page.save(filename=self.output_dir / f"{self.basename}_{self.page_number}.pdf")
        self.page.close()

        # Reset the state
        self.page = Image(width=2402, height=3152, resolution=(300, 300))
        self.current_x, self.current_y = 0, 0
        self.page_number += 1
        self.next_row_should_be_inset = False

    def add_token(self, token_file):
        """Add a token to the current page."""
        with Image(filename=token_file) as token:
            self.page.composite(token, left=int(self.current_x), top=int(self.current_y))
            if token.width > self.diameter or token.height > self.diameter:
                token.resize(width=self.diameter, height=self.diameter)
            self.current_x += self.diameter + self.padding
            # Check bounds
            if self.current_x + self.diameter > self.page.width:
                # When close packing circles, we alternate each row by half the diameter
                self.current_x = 0 + (0 if self.next_row_should_be_inset else self.diameter * 0.5 + self.padding)
                self.next_row_should_be_inset = not self.next_row_should_be_inset  # Toggle the row inset
                # Because we are using close packing, the centers of each circle make a triangle with a base equal to
                # the radius of the circle and a hypotenuse equal to the diameter. Solving for height leaves us with
                # the radius * sqrt(3)
                self.current_y += ((self.diameter // 2) * math.sqrt(3)) + self.padding
                if self.current_y + self.diameter > self.page.height:
                    self.save_page()
