from wand.image import Image
from wand.drawing import Drawing
from wand.color import Color
import math


def fit_ability_text(text, font_size, first_line_width, step):
    """Take an ability text and fit it to a given width.

    Args:
        text (str): The text to be displayed.
        font_size (int): The size of the font to be used.
        first_line_width (int): The width of the first line of text.
        step (int): The amount to increase the line width by each time.
    """
    img = Image(width=1, height=1, resolution=(600, 600))
    with Drawing() as draw:
        # Assign font details
        draw.font = "components/OpenSans-Light.ttf"
        draw.font_size = font_size / 0.9  # We will manipulate the font size in the loop, so start slightly larger
        draw.fill_color = Color("#000000")
        # Determine how many lines we need and how long each line needs to be.
        # Since we never want more than 4 lines, we'll add a loop checking if we have exceeded that, and then just
        # start the line counter above that limit so that we run at least once.
        original_text = text
        lines = [1,2,3,4,5]
        while len(lines) > 4:
            text = original_text
            line_text = text
            lines = []
            target_width = first_line_width
            largest_line_width = 0
            max_height = 0
            draw.font_size = draw.font_size * 0.9
            while len(text) > 0:
                metrics = draw.get_font_metrics(img, line_text)
                while metrics.text_width > target_width:
                    line_text = " ".join(line_text.split(" ")[:-1])
                    metrics = draw.get_font_metrics(img, line_text)
                # Now that we have a line that fits, update all our tracking variables
                largest_line_width = max(largest_line_width, metrics.text_width)
                max_height = max_height + metrics.text_height
                target_width = target_width + step
                lines.append(line_text)
                # Remove the line we just added from the text, and set up line_text for the next line
                text = text[len(line_text):]
                line_text = text
        # Actually draw the text
        current_y = 0
        img.resize(width=int(largest_line_width), height=int(max_height*1.2))  # Add a little padding
        for line_text in lines:
            metrics = draw.get_font_metrics(img, line_text)
            current_x = int(((largest_line_width - metrics.text_width) / 2))
            current_y = int(current_y + metrics.text_height)
            draw.text(current_x, current_y, line_text)
        draw(img)
        img.virtual_pixel = 'transparent'
    return img


def curved_text_to_image(text, token_type, token_diameter):
    """Change a text string into an image with curved text.
    Args:
        text (str): The text to be displayed.
        token_type (str): The type of text to be displayed. Either "reminder" or "role".
        token_diameter (int): The width of the token. This is used to determine the amount of curvature.
    """
    token_diameter = int(token_diameter-(token_diameter*0.1))  # Reduce the diameter by 10% to give a little padding
    if token_type == "reminder":
        font_size = token_diameter * 0.15
        font_filepath = "../../../components/OpenSans-Regular.ttf"
        color = "#FFFFFF"
    else:
        font_size = token_diameter * 0.1
        font_filepath = "../../../components/Dumbledor 2 Regular.ttf"
        color = "#000000"
        text = text.upper()

    img = Image(width=1, height=1, resolution=(600, 600))
    with Drawing() as draw:
        # Assign font details
        draw.font = font_filepath
        draw.font_size = font_size
        draw.fill_color = Color(color)
        # Get size of text
        height, width = 0, math.inf
        # Downsize the text until it fits within the token
        while True:
            metrics = draw.get_font_metrics(img, text)
            height, width = int(metrics.text_height), int(metrics.text_width)
            if width > 2 * token_diameter*0.8:
                draw.font_size = draw.font_size * 0.9
            else:
                break

        # Resize the image
        img.resize(width=width, height=int(height*1.2))
        # Draw the text
        draw.text(0, height, text)
        draw(img)
        img.virtual_pixel = 'transparent'
        # Curve the text
        # The curve angle can be found by treating the text width as a chord length and the token width as the diameter
        # By bisecting this chord we can create a right triangle and solve for the angle.
        # If the text width is greater than the token width, the angle will be greater than 180 degrees.
        additional_curve = 0
        if width > token_diameter:
            width = width - token_diameter
            additional_curve = 180
        curve_degree = round(math.degrees(2 * math.asin((width / 2) / (token_diameter / 2)))) + additional_curve
        # rotate it 180 degrees since we want it to curve down, then distort and rotate back 180 degrees
        img.rotate(180)
        img.distort('arc', (curve_degree, 180))
    return img