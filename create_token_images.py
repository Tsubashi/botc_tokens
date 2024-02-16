import json
import math
from pathlib import Path
import argparse
from rich import print
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.live import Live
from rich.console import Group
from wand.image import Image
from wand.drawing import Drawing
from wand.color import Color


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
        draw.font = "components/OpenSans-Regular.ttf"
        draw.font_size = font_size
        draw.fill_color = Color("#000000")
        line_text = text
        target_width = first_line_width
        largest_line_width = 0
        max_height = 0
        lines = []
        # Determine how many lines we need and how long each line needs to be.
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
        font_filepath = "components/OpenSans-Regular.ttf"
        color = "#FFFFFF"
    else:
        font_size = token_diameter * 0.1
        font_filepath = "components/Dumbledor 2 Regular.ttf"
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
        img.resize(width=width, height=height)
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


def main(args):
    """Use JSON to create a set of tokens."""
    json_files = Path(args.search_dir).rglob("*.json")
    roles = []
    print("[green]Finding Roles...[/]")
    for json_file in json_files:
        with open(json_file, "r") as f:
            data = json.load(f)
        # Rewrite the icon path to be relative to our working directory
        data['icon'] = str(json_file.parent / data.get('icon'))
        roles.append(data)
    print(f"[green]Creating tokens in {args.output_dir}...[/]", end="")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load the component images
    token_bg = Image(filename="components/TokenBG.png")
    reminder_bg = Image(filename="components/ReminderBG.png")
    leaves = [
        Image(filename="components/Leaf1.png"),
        Image(filename="components/Leaf2.png"),
        Image(filename="components/Leaf3.png"),
        Image(filename="components/Leaf4.png"),
        Image(filename="components/Leaf5.png"),
        Image(filename="components/Leaf6.png"),
        Image(filename="components/Leaf7.png"),
    ]
    left_leaf = Image(filename="components/LeafLeft.png")
    right_leaf = Image(filename="components/LeafRight.png")
    setup_flower = Image(filename="components/SetupFlower.png")

    # Create the tokens
    # Overall progress bar
    overall_progress = Progress(
        TimeElapsedColumn(), BarColumn(), TextColumn("{task.description}"), TimeRemainingColumn()
    )

    # Progress bars for single steps (will be hidden when step is done)
    step_progress = Progress(
        TextColumn("  |-"),
        TextColumn("[bold purple]{task.description}"),
        SpinnerColumn("simpleDots"),
    )

    # Group the progress bars
    progress_group = Group(overall_progress, step_progress)

    with Live(progress_group):
        output_path = Path(args.output_dir)
        overall_task = overall_progress.add_task("Creating Tokens...", total=len(roles))
        step_task = step_progress.add_task("Reading roles...")
        for role in roles:
            step_progress.update(step_task, description=f"Creating Token for: {role.get('name')}")
            # Make sure our target directory exists
            role_output_path = output_path / role['home_script'] / role['type']
            role_output_path.mkdir(parents=True, exist_ok=True)

            # Composite the various pieces of the token.
            token = token_bg.clone()
            icon = Image(filename=role['icon'])
            token_icon = icon.clone()
            token_icon.transform(resize=f"{token_bg.width*0.7}x{reminder_bg.height*0.7}^")
            # Determine where to place the icon
            icon_x = (token.width - token_icon.width) // 2
            icon_y = (token.height - token_icon.height + int(token.height*0.1)) // 2
            token.composite(token_icon, left=icon_x, top=icon_y)
            token_icon.close()

            # Check for modifiers
            if role.get('first_night'):
                token.composite(left_leaf, left=0, top=0)
            if role.get('other_nights'):
                token.composite(right_leaf, left=0, top=0)
            if role.get('affects_setup'):
                token.composite(setup_flower, left=0, top=0)

            # Check if we have reminders. If so, create them.
            reminder_icon = icon.clone()
            reminder_icon.transform(resize=f"{reminder_bg.width}x{reminder_bg.height}>")
            # Add leaves to the big token
            for leaf in leaves[:len(role['reminders'])]:
                token.composite(leaf, left=0, top=0)

            # Create the reminder tokens
            for reminder_text in role['reminders']:
                reminder_name = f"{role['name']}-Reminder-{reminder_text}"
                step_progress.update(step_task, description=f"Creating Token for: {role.get('name')}")
                reminder = reminder_bg.clone()
                reminder_icon_x = (reminder.width - reminder_icon.width) // 2
                reminder_icon_y = (reminder.height - reminder_icon.height - int(reminder.height*0.15)) // 2
                reminder.composite(reminder_icon, left=reminder_icon_x, top=reminder_icon_y)
                # Add the reminder text
                text_img = curved_text_to_image(reminder_text.title(), "reminder", reminder_icon.width)
                text_x = (reminder.width - text_img.width) // 2
                text_y = (reminder.height - text_img.height - int(reminder_icon.height*0.05))
                reminder.composite(text_img, left=text_x, top=text_y)
                text_img.close()

                # Resize to 307x307, since that will yield a 26mm token when printed at 300dpi
                reminder.resize(width=307, height=307)

                # Save the reminder token
                reminder_output_path = role_output_path / f"{reminder_name}.png"
                reminder.save(filename=reminder_output_path)
                reminder.close()
            reminder_icon.close()

            # Add ability text to the token
            step_progress.update(step_task, description=f"Creating Token for: {role.get('name')}")
            ability_text_img = fit_ability_text(
                text=role['ability'],
                font_size=int(token.height*0.04),
                first_line_width=int(token.width*.55),
                step=int(token.width*.08)
            )
            ability_text_x = (token.width - ability_text_img.width) // 2
            token.composite(ability_text_img, left=ability_text_x, top=int(token.height*0.15))
            ability_text_img.close()

            # Add the role name to the token
            text_img = curved_text_to_image(role['name'], "role", token.width)
            text_x = (token.width - text_img.width) // 2
            text_y = (token.height - text_img.height - int(token.height*0.15))
            token.composite(text_img, left=text_x, top=text_y)
            text_img.close()

            # Resize to 543x543, since that will yield a 46mm token when printed at 300dpi
            token.resize(width=543, height=543)

            # Save the token
            token_output_path = role_output_path / f"{role['name']}.png"
            token.save(filename=token_output_path)
            token.close()

            # Update the progress bar
            overall_progress.update(overall_task, advance=1)

    # Close the component images
    token_bg.close()
    reminder_bg.close()
    for leaf in leaves:
        leaf.close()
    left_leaf.close()
    right_leaf.close()
    setup_flower.close()

    print("[bold green]Done![/]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create token images to match json files in a directory tree.')
    parser.add_argument('search_dir', type=str, default="results", nargs="?",
                        help='The top level directory in which to begin the search.')
    parser.add_argument('output_dir', type=str, default='tokens', nargs="?",
                        help="Name of the directory in which to output the tokens. (Default: 'tokens')")
    args = parser.parse_args()
    main(args)
    print("--Done!--")
