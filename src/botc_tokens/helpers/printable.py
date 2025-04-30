"""Create printable sheets based on a script json file."""
# Standard Library
import math
from pathlib import Path

# Third Party
import svg
from wand.drawing import Color, Drawing
from wand.image import Image

# Application Specific


class Printable:
    """Create printable sheets based on a script json file."""
    def __init__(
            self,
            output_dir,
            page_width=2550,
            page_height=3300,
            basename="page",
            margin_horizontal=74,
            margin_vertical=74,
            bleed=12,  # 12px = 1mm @ 300dpi
            padding=0,
            diameter=None,
            close_packing=True,
            cutting=False
    ):
        """Create a new printable object.

        Args:
            output_dir (str|Path): The directory to save the pages to.
            page_width (int): The width of the page in pixels.
            page_height (int): The height of the page in pixels.
            basename (str): The base name to use for the pages.
            margin_horizontal (int): The margin (in pixels) between the left/right edge of the paper and the tokens.
            margin_vertical (int): The margin (in pixels) between the top/bottom of the paper and the tokens.
            padding (int): The padding (in pixels) between tokens.
            bleed (int): The bleed (in pixels) expected, which will be trimmed in the cutting file.
            diameter (int): The diameter (in pixels) to allocate per token. If unspecified, the first token's largest
                dimension will be used.
            close_packing (bool): Whether to use close packing of circles. If True, the tokens will be arranged in a
                hexagonal pattern. If False, the tokens will be arranged in a grid.
            cutting (bool): Whether to create cutting files.
        """
        # 8.5"x11" at 300dpi is 2550 x 3300px
        # Subtracting 74px from each side to account for printer margins leaves our default of 2402 x 3152px
        self.page_width = page_width - (margin_horizontal * 2)
        self.page_height = page_height - (margin_vertical * 2)
        self.page = None
        self.document = Image()
        self.document.resolution = (300, 300)
        self.current_x = 0
        self.current_y = 0
        self.next_row_should_be_inset = False
        self.output_dir = Path(output_dir)
        self.page_number = 1
        self.basename = basename
        self.margin_horizontal = margin_horizontal
        self.margin_vertical = margin_vertical
        self.padding = padding
        self.bleed = bleed
        self.diameter = diameter
        self.close_packing = close_packing
        self.partial_page_token_count = 0
        self.cutting = svg.SVG(width=self.page_width, height=self.page_height, elements=[]) if cutting else None
        self.cutting_pages = []

        self.save_page()  # Initializes the first page

    def save_page(self):
        """Save the current page and reset the state."""
        if not (self.current_x == 0 and self.current_y == 0):  # Only save if we added content
            # Add the margins in by creating a new image and compositing the current page onto it
            new_page = Image(
                width=self.page_width + (self.margin_horizontal * 2),
                height=self.page_height + (self.margin_vertical * 2)
            )
            new_page.composite(self.page, left=self.margin_horizontal, top=self.margin_vertical)

            # If we are cutting, add and alignment cross to the top left and bottom right corners
            if self.cutting is not None:
                cross_size = max(self.page_width, self.page_height) // 25
                cross_middle = cross_size // 2
                cross = Image(width=cross_size, height=cross_size)
                with Drawing() as draw:
                    draw.stroke_color = Color('black')
                    draw.stroke_width = cross_size // 10
                    draw.line((0, cross_middle), (cross_size, cross_middle))  # Horizontal line
                    draw.line((cross_middle, 0), (cross_middle, cross_size))  # Vertical line
                    draw(cross)
                new_page.composite(  # Top Left
                    cross,
                    left=self.margin_horizontal - cross_middle,
                    top=self.margin_vertical - cross_middle
                )
                new_page.composite(  # Bottom Right
                    cross,
                    left=self.margin_horizontal + self.page_width - cross_middle,
                    top=self.margin_vertical + self.page_height - cross_middle
                )
            # Replace the current page with the newly composited page
            self.page = new_page

            # Save the page to the document, reset our cursors, and increment the page number
            self.document.sequence.append(self.page)
            self.current_x, self.current_y = 0, 0
            self.partial_page_token_count = 0
            self.page_number += 1
            self.next_row_should_be_inset = False

            # Save and reset the cutting file if requested
            if self.cutting is not None:
                self.cutting_pages.append(self.cutting)
                self.cutting = svg.SVG(width=self.page_width, height=self.page_height, elements=[])

        self.page = Image(width=self.page_width, height=self.page_height)

    def write(self):
        """Write everything to disk."""
        # Save the last page if it has content
        if self.current_x != 0 or self.current_y != 0:
            self.save_page()
        # Save the full pdf
        if self.document.sequence:
            self.document.save(filename=self.output_dir / f"{self.basename}.pdf", adjoin=True)
        # Save the cutting files if requested
        if self.cutting is not None:
            cutting_folder = self.output_dir / "cutting"
            cutting_folder.mkdir(parents=True, exist_ok=True)
            for i, page in enumerate(self.cutting_pages):
                with open(cutting_folder / f"{self.basename}_cutting_page_{i + 1}.svg", "w") as f:
                    f.write(str(page))

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
            if token.width > self.diameter or token.height > self.diameter:
                token.resize(width=self.diameter, height=self.diameter)
            self.page.composite(token, left=int(self.current_x), top=int(self.current_y))
            # If we are cutting, add the token to the cutting file
            if self.cutting:
                cutting_radius = (self.diameter // 2) - self.bleed
                # Find the center x and y of the token
                cx = int(self.current_x + self.diameter // 2)
                cy = int(self.current_y + self.diameter // 2)
                token_cutline = svg.Circle(
                    cx=cx, cy=cy, r=cutting_radius,
                    stroke="black",
                    fill="transparent",
                    stroke_width=5,
                )
                self.cutting.elements.append(token_cutline)
            self.current_x += self.diameter + self.padding
            # Check bounds
            if self.current_x + self.diameter > self.page.width:
                if self.close_packing:
                    # When close packing circles, we alternate each row by half the diameter
                    self.current_x = 0 + (0 if self.next_row_should_be_inset else self.diameter * 0.5 + self.padding)
                    self.next_row_should_be_inset = not self.next_row_should_be_inset  # Toggle the row inset
                    # Due to close packing, we can't just use the token diameter to move the new y. Instead, we make a
                    # right-angle triangle with the hypotenuse connecting the center of the next circle to the center of
                    # the circle above it in the previous row. In order to prevent overlap, the triangle must have a
                    # base equal to the radius of the circle and a hypotenuse equal to the diameter (2r).
                    # Solving for height will give us the distance we need to move the new y value, and it comes out
                    # to be `radius * sqrt(3)`.
                    self.current_y += ((self.diameter // 2) * math.sqrt(3)) + self.padding
                else:
                    self.current_x = 0
                    self.current_y += self.diameter + self.padding

                # Check to see if we have reached the end of the page
                if self.current_y + self.diameter > self.page.height:
                    self.save_page()
