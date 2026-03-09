"""
Image Generator - Static chart image generation for RAMViewer

Generates PNG image files and CSV data files from collected variable data.
"""

import csv
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for image generation

import matplotlib.pyplot as plt


# Default colors for up to 8 variables
DEFAULT_COLORS = [
    '#1f77b4',  # blue
    '#ff7f0e',  # orange
    '#2ca02c',  # green
    '#d62728',  # red
    '#9467bd',  # purple
    '#8c564b',  # brown
    '#e377c2',  # pink
    '#7f7f7f',  # gray
]

# Temp directory for generated images
TEMP_DIR = 'ramgs_tmp_imgs'

# Maximum filename length
MAX_FILENAME_LENGTH = 200


def generate_image(
    timestamps: List[float],
    data: Dict[str, List[float]],
    var_names: List[str],
    output_dir: Optional[str] = None
) -> Tuple[str, str]:
    """
    Generate a static PNG chart image and CSV data file from collected data.

    Args:
        timestamps: List of relative timestamps (seconds from start)
        data: Dict mapping variable names to their value lists
        var_names: List of variable names (for ordering and legend)
        output_dir: Output directory (default: ramgs_tmp_imgs in cwd)

    Returns:
        Tuple of (image_path, csv_path)
    """
    if output_dir is None:
        output_dir = os.path.join(os.getcwd(), TEMP_DIR)

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Generate filename (without extension)
    base_filename = _generate_base_filename(var_names)
    image_filepath = os.path.join(output_dir, base_filename + '.png')
    csv_filepath = os.path.join(output_dir, base_filename + '.csv')

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot each variable
    for i, name in enumerate(var_names):
        color = DEFAULT_COLORS[i % len(DEFAULT_COLORS)]
        values = data.get(name, [])
        if values and timestamps:
            ax.plot(timestamps[:len(values)], values, label=name, color=color, linewidth=1.5)

    # Configure axes
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Value')
    ax.legend(loc='upper left')
    ax.grid(True, linestyle='--', alpha=0.7)

    # Set title
    title = ', '.join(var_names)
    if len(title) > 60:
        title = title[:57] + '...'
    ax.set_title(f'RAMViewer: {title}')

    # Auto-scale Y axis with 10% padding
    if timestamps and any(data.get(name, []) for name in var_names):
        all_values = []
        for name in var_names:
            all_values.extend(data.get(name, []))
        if all_values:
            y_min, y_max = min(all_values), max(all_values)
            y_range = y_max - y_min
            if y_range == 0:
                y_range = 1.0
            padding = y_range * 0.1
            ax.set_ylim(y_min - padding, y_max + padding)

    # Save image
    plt.tight_layout()
    plt.savefig(image_filepath, dpi=100, format='png')
    plt.close(fig)

    # Generate CSV file
    _generate_csv(csv_filepath, timestamps, data, var_names)

    return image_filepath, csv_filepath


def _generate_csv(
    filepath: str,
    timestamps: List[float],
    data: Dict[str, List[float]],
    var_names: List[str]
) -> None:
    """
    Generate a CSV data file from collected data.

    Args:
        filepath: Output CSV file path
        timestamps: List of relative timestamps (seconds from start)
        data: Dict mapping variable names to their value lists
        var_names: List of variable names (for column ordering)
    """
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        # Write header
        writer.writerow(['timestamp'] + var_names)
        # Write data rows
        for i, ts in enumerate(timestamps):
            row = [f'{ts:.3f}']
            for name in var_names:
                values = data.get(name, [])
                if i < len(values):
                    row.append(values[i])
                else:
                    row.append('')
            writer.writerow(row)


def _generate_base_filename(var_names: List[str]) -> str:
    """
    Generate a unique base filename (without extension) with variable names and timestamp.

    Format: image_<varnames>_YYYYMMDD_HHMMSS_fff
    """
    now = datetime.now()
    timestamp = now.strftime('%Y%m%d_%H%M%S') + f'_{now.microsecond // 1000:03d}'

    # Clean variable names for filename (replace dots with underscores)
    clean_names = [name.replace('.', '_').replace('[', '_').replace(']', '') for name in var_names]
    varnames_part = '_'.join(clean_names)

    # Base filename without varnames
    prefix = 'image_'
    suffix = f'_{timestamp}'

    # Calculate max length for varnames part (reserve space for longest extension .csv or .png)
    max_varnames_len = MAX_FILENAME_LENGTH - len(prefix) - len(suffix) - 4 - 4  # 4 for "_etc", 4 for ".png"

    if len(varnames_part) > max_varnames_len:
        # Truncate and add _etc
        varnames_part = varnames_part[:max_varnames_len] + '_etc'

    return f'image_{varnames_part}_{timestamp}'
