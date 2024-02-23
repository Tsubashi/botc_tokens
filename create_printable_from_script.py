import argparse
from pathlib import Path
from rich.progress import Progress, TimeElapsedColumn, BarColumn, TextColumn, TimeRemainingColumn, SpinnerColumn, Live, Group
import json
from wand.image import Image
from rich import print


def main(args):
    """Create printable sheets based on a script json file."""
    # Find all the token images
    token_files = Path(args.token_dir).rglob("*.png")
    role_images = []
    reminder_images = []
    print("[green]Finding Token Images...[/]")
    for img_file in token_files:
        if "Reminder" in img_file.name:
            reminder_images.append(img_file)
        else:
            role_images.append(img_file)

    # Read the script json file
    print(f"[green]Reading {args.script_json}...[/]")
    with open(args.script_json, "r") as f:
        script = json.load(f)

    # Create the printable sheets
    print(f"[green]Creating sheets in {args.output_dir}...[/]", end="")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

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
        overall_progress.add_task("Creating Sheets", total=2)
        step_task = step_progress.add_task("Adding roles")
        role_page = Printable(output_dir, "roles")
        reminder_page = Printable(output_dir, "reminders")
        for role in script:
            if isinstance(role, dict):
                continue  # Skip metadata
            role_name = role.lower().replace("_", " ").strip()
            step_progress.update(step_task, description=f"Adding {role_name.title()}")
            # See if we have tokens for this role
            role_file = next((t for t in role_images if role_name in t.name.lower().replace("'","")), None)
            reminder_files = (t for t in reminder_images if t.name.lower().replace("'","").startswith(role_name))
            if not role_file:
                print(f"[yellow]No token found for {role_name}[/]")
                continue
            role_page.add_token(role_file)
            for reminder in reminder_files:
                reminder_page.add_token(reminder)

        # Save the last pages
        step_progress.update(step_task, description=f"Saving pages")
        role_page.save_page()
        reminder_page.save_page()


class Printable:
    """Create printable sheets based on a script json file."""
    def __init__(self, output_dir, basename="page"):
        # 8.5"x11" at 300dpi is 2550 x 3300px
        # Subtracting 74px from each side to account for printer margins leaves 2402 x 3152px
        self.page = Image(width=2402, height=3152, resolution=(300, 300))
        self.current_x = 0
        self.current_y = 0
        self.next_row_should_be_inset = False
        self.output_dir = Path(output_dir)
        self.page_number = 1
        self.basename = basename

    def save_page(self):
        """Save the current page and reset the state."""
        # Don't save a blank sheet
        if self.current_x == 0 and self.current_y == 0:
            return
        self.page.save(filename=self.output_dir / f"{self.basename}_{self.page_number}.pdf")
        self.page.close()
        self.page = Image(width=4952, height=6452, resolution=(600, 600))
        self.current_x, self.current_y = 0, 0

    def add_token(self, token_file):
        """Add a token to the current page."""
        with Image(filename=token_file) as token:
            self.page.composite(token, left=int(self.current_x), top=int(self.current_y))
            self.current_x += token.width * 1.6
            # Check bounds
            if self.current_x + token.width > self.page.width:
                self.current_x = 0 + (0 if self.next_row_should_be_inset else token.width * 0.8)
                self.next_row_should_be_inset = not self.next_row_should_be_inset  # Toggle the row inset
                self.current_y += token.height // 2 + token.height * 0.2
                if self.current_y + token.height > self.page.height:
                    self.save_page()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create printable sheets based on a script json file.')
    parser.add_argument('script_json', type=str,
                        help='the json file containing the script info.')
    parser.add_argument('--token-dir', type=str, default='tokens',
                        help="Name of the directory in which to find the token images. (Default: 'tokens')")
    parser.add_argument('-o', '--output-dir', type=str, default='printables',
                        help="Name of the directory in which to output the sheets. (Default: 'printables')")
    args = parser.parse_args()
    main(args)
    print("--Done!--")