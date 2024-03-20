"""Create printable sheets based on a script json file."""
# Standard Library
import math
from pathlib import Path

# Third Party
from wand.image import Image

# Application Specific


class Printable:
    """Create printable sheets based on a script json file."""
    def __init__(self, output_dir, page_width=2402, page_height=3152, basename="page", padding=0, diameter=None):
        """Create a new printable object.

        Args:
            output_dir (str|Path): The directory to save the pages to.
            page_width (int): The width of the page in pixels.
            page_height (int): The height of the page in pixels.
            basename (str): The base name to use for the pages.
            padding (int): The padding (in pixels) between tokens.
            diameter (int): The diameter (in pixels) to allocate per token. If unspecified, the first token's largest
                dimension will be used.
        """
        # 8.5"x11" at 300dpi is 2550 x 3300px
        # Subtracting 74px from each side to account for printer margins leaves our default of 2402 x 3152px
        self.page_width = page_width
        self.page_height = page_height
        self.page = None
        self.document = Image()
        self.current_x = 0
        self.current_y = 0
        self.next_row_should_be_inset = False
        self.output_dir = Path(output_dir)
        self.page_number = 1
        self.basename = basename
        self.padding = padding
        self.diameter = diameter

        self.save_page()  # Initializes the first page

    def save_page(self):
        """Save the current page and reset the state."""
        if not (self.current_x == 0 and self.current_y == 0):
            # Only save if we added content
            self.document.sequence.append(self.page)
            self.current_x, self.current_y = 0, 0
            self.page_number += 1
            self.next_row_should_be_inset = False
        self.page = Image(width=self.page_width, height=self.page_height, resolution=(300, 300))

    def write(self):
        """Write everything to disk."""
        # Save the last page if it has content
        if self.current_x != 0 or self.current_y != 0:
            self.save_page()
        if self.document.sequence:
            self.document.save(filename=self.output_dir / f"{self.basename}.pdf", adjoin=True)

    def close(self):
        """Close all Wand objects."""
        self.document.close()
        self.page.close()

    def add_token(self, token_file):
        """Add a token to the current page."""
        with Image(filename=token_file) as token:
            # Unless we have a fixed diameter, use the largest dimension of the first token as the diameter
            if self.diameter is None:
                self.diameter = token.width if token.width > token.height else token.height
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
