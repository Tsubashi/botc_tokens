"""Helper functions for progress bars."""
from rich.progress import BarColumn, Group, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn


def setup_progress_group():
    """Prepare the progress bars group."""
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
    return progress_group, overall_progress, step_progress
