"""
Performance Log Analyzer for VisionPilot-XR
Parses log files and generates analysis graphs.
"""

import os
import re
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from collections import Counter


def parse_log_file(log_path: str) -> dict:
    """
    Parse a performance log file and extract all data.

    Returns:
        dict with keys:
            - 'frames': list of dicts with per-frame data
            - 'system': list of dicts with system metrics
            - 'summary': dict with summary statistics
    """
    if not os.path.exists(log_path):
        raise FileNotFoundError(f"Log file not found: {log_path}")

    with open(log_path, 'r', encoding='utf-8') as f:
        content = f.read()

    result = {
        'frames': [],
        'system': [],
        'summary': {},
        'log_file': log_path
    }

    # -------------------------
    # RAW DATA PARSING (robust)
    # -------------------------
    # Find the RAW DATA block first
    if 'RAW DATA' in content:
        raw_block = content.split('RAW DATA', 1)[1]
        # Split into lines and find the header line that starts with 'Frame'
        lines_all = raw_block.splitlines()
        header_idx = None
        for idx, line in enumerate(lines_all):
            if re.match(r'^\s*Frame\b', line):
                header_idx = idx
                break

        if header_idx is not None:
            # Collect lines after header until a line of === (separator) or end
            data_lines = []
            for line in lines_all[header_idx+1:]:
                if re.match(r'^\s*=+\s*$', line):
                    break
                # skip divider lines like '----' or empty lines
                if re.match(r'^\s*-{2,}\s*$', line) or line.strip() == '':
                    continue
                data_lines.append(line)

            # Parse each data line by splitting on '|' and stripping
            def float_or_none(s: str):
                if s is None:
                    return None
                s = s.strip()
                if s == '' or s in ('--', '-', '—', 'N/A', 'NA'):
                    return None
                # remove any non-numeric trailing characters (e.g., 'MB', '%')
                s_clean = re.sub(r'[,%\s]+', '', s)
                # remove unit suffixes like 'MB' or '%'
                s_clean = re.sub(r'[a-zA-Z%]+$', '', s_clean)
                try:
                    return float(s_clean)
                except Exception:
                    return None

            # Build header mapping to allow robust column lookup by name
            header_line = lines_all[header_idx]
            header_cols = [h.strip() for h in header_line.split('|')]
            # Normalized lowercase keys for lookup (preserve original indices)
            col_index = {h.strip().lower(): i for i, h in enumerate(header_cols)}

            for line in data_lines:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) < 7:
                    continue
                try:
                    # Helper to get part by header name with optional fallback index
                    def part_by_name(name, fallback=None):
                        idx = col_index.get(name.lower())
                        if idx is not None and idx < len(parts):
                            return parts[idx]
                        if fallback is not None and fallback < len(parts):
                            return parts[fallback]
                        return ''

                    # Try to read common columns by header name (robust across variations)
                    frame_raw = part_by_name('frame', 0)
                    try:
                        frame = int(frame_raw)
                    except Exception:
                        frame = None

                    total_ms = float_or_none(part_by_name('total', 1))
                    red_ms = float_or_none(part_by_name('red', 2))
                    canny_ms = float_or_none(part_by_name('canny', 3))
                    ellipse_ms = float_or_none(part_by_name('ellipse', 4))
                    read_sign_ms = float_or_none(part_by_name('readsign', 5))

                    # detections may be labeled 'detections' or be at index 6
                    det_raw = part_by_name('detections', 6)
                    detections = int(det_raw) if det_raw.isdigit() else 0

                    detected_speed = float_or_none(part_by_name('speed', 7))
                    weather = part_by_name('weather', 8) if part_by_name('weather', 8) not in ('', '--') else None

                    # Prefer explicit 'fps' column if present in header, otherwise try fallback positions
                    fps = float_or_none(part_by_name('fps'))
                    cpu = float_or_none(part_by_name('cpu'))

                    # GPU may be named 'gpu' or 'gpu_mb' -- try both
                    gpu = None
                    gpu_mb = None
                    gpu_raw_val = part_by_name('gpu')
                    if gpu_raw_val == '' and 'gpu_mb' in col_index:
                        gpu_raw_val = part_by_name('gpu_mb')
                    gpu_raw = float_or_none(gpu_raw_val)
                    if gpu_raw is not None:
                        if gpu_raw > 100:
                            gpu_mb = gpu_raw
                        else:
                            gpu = gpu_raw

                    # If fps/cpu/gpu still missing, fallback to older positional parsing to preserve backward compatibility
                    if fps is None and len(parts) >= 10:
                        # old layouts: try to read fps at index 9 or 7 depending on length
                        if len(parts) >= 12:
                            try:
                                fps = float_or_none(parts[9])
                                cpu = float_or_none(parts[10]) if cpu is None else cpu
                                gpu_raw_fb = float_or_none(parts[11]) if gpu is None and gpu_mb is None else None
                                if gpu_raw_fb is not None:
                                    if gpu_raw_fb > 100:
                                        gpu_mb = gpu_raw_fb
                                    else:
                                        gpu = gpu_raw_fb
                            except Exception:
                                pass
                        elif len(parts) == 11:
                            fps = float_or_none(parts[8]) if fps is None else fps
                            cpu = float_or_none(parts[9]) if cpu is None else cpu
                            try:
                                gpu = float_or_none(parts[10]) if gpu is None else gpu
                            except Exception:
                                pass
                        elif len(parts) == 10:
                            fps = float_or_none(parts[7]) if fps is None else fps
                            cpu = float_or_none(parts[8]) if cpu is None else cpu
                            try:
                                gpu = float_or_none(parts[9]) if gpu is None else gpu
                            except Exception:
                                pass

                    frame_data = {
                        'frame': frame,
                        'total_ms': total_ms,
                        'red_ms': red_ms,
                        'canny_ms': canny_ms,
                        'ellipse_ms': ellipse_ms,
                        'read_sign_ms': read_sign_ms,
                        'detections': detections,
                        'detected_speed': detected_speed,
                        'weather': weather,
                        'fps': fps,
                        'cpu': cpu,
                        'gpu': gpu,
                        'gpu_mb': gpu_mb,
                    }

                    result['frames'].append(frame_data)
                except Exception:
                    # skip malformed
                    continue
    # -------------------------
    # End RAW DATA parsing
    # -------------------------

    # Parse summary statistics
    summary_patterns = {
        'total_frames': r'Total frames:\s*(\d+)',
        'red_avg': r'Red Nulling\s*\|\s*([\d.]+)',
        'red_max': r'Red Nulling\s*\|.*?\|\s*([\d.]+)',
        'canny_avg': r'Canny\s*\|\s*([\d.]+)',
        'canny_max': r'Canny\s*\|.*?\|\s*([\d.]+)',
        'ellipse_avg': r'Ellipse Detection\s*\|\s*([\d.]+)',
        'ellipse_max': r'Ellipse Detection\s*\|.*?\|\s*([\d.]+)',
        'total_avg': r'TOTAL\s*\|\s*([\d.]+)',
        'total_max': r'TOTAL\s*\|.*?\|\s*([\d.]+)',
    }

    for key, pattern in summary_patterns.items():
        match = re.search(pattern, content)
        if match:
            result['summary'][key] = float(match.group(1))

    # Parse system metrics
    fps_pattern = r'FPS\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)'
    cpu_pattern = r'App CPU %\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)'

    fps_match = re.search(fps_pattern, content)
    if fps_match:
        result['summary']['fps_avg'] = float(fps_match.group(1))
        result['summary']['fps_min'] = float(fps_match.group(2))
        result['summary']['fps_max'] = float(fps_match.group(3))

    cpu_match = re.search(cpu_pattern, content)
    if cpu_match:
        result['summary']['cpu_avg'] = float(cpu_match.group(1))
        result['summary']['cpu_min'] = float(cpu_match.group(2))
        result['summary']['cpu_max'] = float(cpu_match.group(3))

    return result


def generate_graphs(data: dict, output_dir: str = None) -> tuple:
    """
    Generate analysis graphs from parsed log data.

    Args:
        data: Parsed log data from parse_log_file()
        output_dir: Directory to save graphs (default: data_analysis inside project)

    Returns:
        Tuple of paths to saved images: (analysis_png_path, speed_pie_png_path)
    """
    if not data['frames']:
        raise ValueError("No frame data to analyze")

    # Ensure the output directory defaults to project data_analysis folder
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), 'data_analysis')
    os.makedirs(output_dir, exist_ok=True)

    frames = data['frames']
    n_frames = len(frames)

    # Extract arrays
    frame_nums = np.array([f['frame'] for f in frames])
    # Use NaN for missing values so we can compute nan-aware statistics
    total_ms = np.array([np.nan if f.get('total_ms') is None else f.get('total_ms') for f in frames], dtype=float)
    red_ms = np.array([np.nan if f.get('red_ms') is None else f.get('red_ms') for f in frames], dtype=float)
    canny_ms = np.array([np.nan if f.get('canny_ms') is None else f.get('canny_ms') for f in frames], dtype=float)
    ellipse_ms = np.array([np.nan if f.get('ellipse_ms') is None else f.get('ellipse_ms') for f in frames], dtype=float)
    read_sign_ms = np.array([np.nan if f.get('read_sign_ms') is None else f.get('read_sign_ms') for f in frames], dtype=float)
    detections = np.array([0 if f.get('detections') is None else f.get('detections') for f in frames], dtype=int)

    # Get per-frame FPS/CPU/GPU values. Use np.nan for missing values (more robust than zeros)
    fps_values = np.array([np.nan if f.get('fps') in (None, 0) else f.get('fps') for f in frames], dtype=float)
    cpu_values = np.array([np.nan if f.get('cpu') in (None, 0) else f.get('cpu') for f in frames], dtype=float)
    # GPU values may be recorded as util % (gpu) or GPU memory MB (gpu_mb)
    gpu_values = np.array([np.nan if f.get('gpu') in (None, 0) else f.get('gpu') for f in frames], dtype=float)
    gpu_mb_values = np.array([np.nan if f.get('gpu_mb') in (None, 0) else f.get('gpu_mb') for f in frames], dtype=float)

    # Also compute FPS from total_ms for comparison / fallback
    safe_total = np.copy(total_ms)
    safe_total[~np.isfinite(safe_total)] = np.nan
    safe_total = np.where(safe_total < 0.1, np.nan, safe_total)
    computed_fps = 1000.0 / safe_total

    # Decide which FPS to plot: prefer logged per-frame FPS (Real FPS) if present
    logged_exists = np.any(np.isfinite(fps_values))
    if logged_exists:
        fps_plot = fps_values
        fps_label_main = 'Real FPS (log)'
        # If logged values exist but some frames are NaN, fill those with computed_fps where available for smoother plot
        fps_plot = np.where(np.isfinite(fps_plot), fps_plot, computed_fps)
        # Keep a computed_fps line for optional comparison (dashed)
        show_computed = True
    else:
        # No logged per-frame FPS: use summary avg if present, otherwise computed_fps
        fps_summary = data.get('summary', {}).get('fps_avg')
        if fps_summary is not None and fps_summary > 0:
            fps_plot = np.full(n_frames, float(fps_summary), dtype=float)
        else:
            fps_plot = computed_fps
        fps_label_main = 'FPS (computed)'
        show_computed = False

    # If computed_fps contains NaNs everywhere, replace with nan to avoid warnings
    if not np.any(np.isfinite(computed_fps)):
        computed_fps = np.full(n_frames, np.nan)

    # Get summary stats (use nan-aware functions)
    # safe nan-aware aggregates with fallbacks
    def safe_nanmean(arr, fallback=0.0):
        try:
            if np.any(np.isfinite(arr)):
                return float(np.nanmean(arr))
        except Exception:
            pass
        return float(fallback)

    def safe_nanmax(arr, fallback=0.0):
        try:
            if np.any(np.isfinite(arr)):
                return float(np.nanmax(arr))
        except Exception:
            pass
        return float(fallback)

    cpu_avg = data['summary'].get('cpu_avg', safe_nanmean(cpu_values))
    fps_avg = data['summary'].get('fps_avg', safe_nanmean(fps_plot)) if data.get('summary') else safe_nanmean(fps_plot)

    # safe maxima used for axis limits
    fps_max_safe = safe_nanmax(fps_plot, fallback=0.0)
    cpu_max_safe = safe_nanmax(cpu_values, fallback=0.0)
    gpu_max_safe = safe_nanmax(gpu_values, fallback=0.0)
    gpu_mb_max_safe = safe_nanmax(gpu_mb_values, fallback=0.0)

    # Create figure - 2x2 layout
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('VisionPilot-XR Performance Analysis', fontsize=16, fontweight='bold')

    # ===== GRAPH 1: FPS over time (Top Left) =====
    ax1 = axes[0, 0]
    ax1.plot(frame_nums, fps_plot, color='#2563eb', linewidth=1.6, label=fps_label_main)
    # Plot computed fps as dashed faint line for comparison if logged fps exists
    if show_computed and np.any(np.isfinite(computed_fps)):
        ax1.plot(frame_nums, computed_fps, color='#93c5fd', linewidth=1.0, linestyle='--', label='Computed FPS (1000/total_ms)')
    ax1.axhline(y=30, color='#22c55e', linestyle='--', linewidth=2, label='30 FPS target')
    ax1.axhline(y=15, color='#dc2626', linestyle='--', linewidth=1.5, label='15 FPS critical')
    ax1.fill_between(frame_nums, fps_plot, alpha=0.2, color='#2563eb')

    ax1.set_xlabel('Frame', fontsize=10)
    ax1.set_ylabel('FPS', fontsize=10)
    # Use nan-aware statistics for title to avoid showing misleading zeros when data missing
    fps_mean = np.nanmean(fps_plot) if np.isfinite(np.nanmean(fps_plot)) else 0.0
    fps_min = np.nanmin(fps_plot) if np.isfinite(np.nanmin(fps_plot)) else 0.0
    fps_max = np.nanmax(fps_plot) if np.isfinite(np.nanmax(fps_plot)) else 0.0
    ax1.set_title(f'FPS During Recording (Avg: {fps_mean:.1f}, Min: {fps_min:.1f}, Max: {fps_max:.1f})',
                  fontsize=12, fontweight='bold')
    # Choose a sane upper limit: either a bit above max FPS or 35 to show targets
    if np.isfinite(fps_max_safe) and fps_max_safe > 0:
        upper = max(35, fps_max_safe * 1.1)
    else:
        upper = 35
    ax1.set_ylim(0, upper)
    ax1.legend(loc='lower right', fontsize=9)
    ax1.grid(True, alpha=0.3)

    # ===== GRAPH 2: CPU and GPU load (Top Right) =====
    ax2 = axes[0, 1]

    # Primary axis: CPU % (always percent)
    ax2.plot(frame_nums, cpu_values, color='#f59e0b', linewidth=1.2, label=f'CPU % (avg: {safe_nanmean(cpu_values):.1f}%)')
    ax2.fill_between(frame_nums, cpu_values, alpha=0.2, color='#f59e0b')
    ax2.set_xlabel('Frame', fontsize=10)
    ax2.set_ylabel('CPU %', fontsize=10, color='#f59e0b')
    ax2.tick_params(axis='y', labelcolor='#f59e0b')

    # Secondary axis for GPU: if we have GPU util% use same unit (percent) on same axis; if we only have GPU MB, use twin y-axis
    gpu_on_percent = gpu_max_safe > 0
    gpu_on_mb = gpu_mb_max_safe > 0

    if gpu_on_percent:
        # GPU util% — plot on same numeric scale as CPU% for easy comparison
        ax2.plot(frame_nums, gpu_values, color='#22c55e', linewidth=1.2, label=f'GPU % (avg: {safe_nanmean(gpu_values):.1f}%)')
        ax2.fill_between(frame_nums, gpu_values, alpha=0.15, color='#22c55e')
        # safe ylim using safe maxima
        ax2.set_ylim(0, max(cpu_max_safe * 1.2, gpu_max_safe * 1.2, 10))
        # Combine legends from ax2 only
        handles, labels = ax2.get_legend_handles_labels()
        ax2.legend(handles, labels, loc='upper right', fontsize=9)
        ax2.set_title('CPU and GPU Utilization (%)', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3)
    elif gpu_on_mb:
        # GPU memory MB — use twin y-axis to avoid mixing units
        ax2.set_ylim(0, max(cpu_max_safe * 1.2, 10))
        ax2.set_title('CPU % and GPU Memory (MB)', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3)

        ax2b = ax2.twinx()
        ax2b.plot(frame_nums, gpu_mb_values, color='#22c55e', linewidth=1.2, label=f'GPU Mem MB (avg: {np.mean(gpu_mb_values):.1f} MB)')
        ax2b.fill_between(frame_nums, gpu_mb_values, alpha=0.15, color='#22c55e')
        ax2b.set_ylabel('GPU Memory (MB)', fontsize=10, color='#22c55e')
        ax2b.tick_params(axis='y', labelcolor='#22c55e')

        # Legends from both axes
        h1, l1 = ax2.get_legend_handles_labels()
        h2, l2 = ax2b.get_legend_handles_labels()
        ax2.legend(h1 + h2, l1 + l2, loc='upper right', fontsize=9)
    else:
        # No GPU data — show CPU axis only
        ax2.set_ylim(0, max(cpu_max_safe * 1.2, 10))
        ax2.set_title('CPU Utilization', fontsize=12, fontweight='bold')
        ax2.legend(loc='upper right', fontsize=9)
        ax2.grid(True, alpha=0.3)

    # ===== GRAPH 3: Processing stages over time (Bottom Left) =====
    ax3 = axes[1, 0]

    ax3.plot(frame_nums, red_ms, color='#dc2626', linewidth=1, label=f'Red extraction (avg: {np.mean(red_ms):.2f}ms)')
    ax3.plot(frame_nums, canny_ms, color='#fbbf24', linewidth=1, label=f'Canny (avg: {np.mean(canny_ms):.2f}ms)')
    ax3.plot(frame_nums, ellipse_ms, color='#22c55e', linewidth=1, label=f'Ellipse (avg: {np.mean(ellipse_ms):.2f}ms)')
    ax3.plot(frame_nums, read_sign_ms, color='#8b5cf6', linewidth=1, label=f'Read Sign (avg: {np.mean(read_sign_ms):.2f}ms)')

    ax3.set_xlabel('Frame', fontsize=10)
    ax3.set_ylabel('Processing Time (ms)', fontsize=10)
    ax3.set_title('Processing Stages During Recording', fontsize=12, fontweight='bold')
    ax3.legend(loc='upper right', fontsize=9)
    ax3.grid(True, alpha=0.3)

    # Set y-limit based on max values (nan-safe)
    max_stage = max(safe_nanmax(red_ms, fallback=0.0), safe_nanmax(canny_ms, fallback=0.0), safe_nanmax(ellipse_ms, fallback=0.0), safe_nanmax(read_sign_ms, fallback=0.0))
    ax3.set_ylim(0, max(max_stage * 1.2, 1))

    # ===== GRAPH 4: Detections per frame (Bottom Right) =====
    ax4 = axes[1, 1]

    # Color bars: highlight frames that contain detections
    bar_colors = ['#10b981' if d > 0 else '#c7c7cc' for d in detections]
    # Draw bars without black edges (edgecolor='none') to avoid continuous top-edge artifacts
    ax4.bar(frame_nums, detections, color=bar_colors, edgecolor='none', linewidth=0, alpha=0.9, width=1.0)

    # (Previously we annotated each bar with a small number above it; removed to reduce clutter.)

    ax4.set_xlabel('Frame', fontsize=10)
    ax4.set_ylabel('Number of Detections', fontsize=10)
    ax4.set_title(f'Detections per Frame (Total detections: {int(np.sum(detections))}, Max/frame: {int(np.max(detections))})',
                  fontsize=12, fontweight='bold')
    ax4.set_ylim(0, max(np.max(detections) * 1.15, 1))
    ax4.grid(True, alpha=0.2, axis='y')

    plt.tight_layout()


    # Save figure to output_dir (data_analysis by default)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_path = os.path.join(output_dir, f"analysis_{timestamp}.png")

    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"[Analysis] Graph saved to: {output_path}")

    # --- SPEED PIE CHART GENERATION (exact speeds) ---
    frames = data['frames']
    # Collect detected speeds (None or 0 => 'No detection')
    raw_speeds = [f.get('detected_speed') for f in frames]

    # Build counts: key 'No detection' for None/0, else integer km/h (rounded)
    speed_keys = []
    for s in raw_speeds:
        if s is None or s == 0:
            speed_keys.append('No detection')
        else:
            # round to nearest int for exact speed grouping
            speed_keys.append(f"{int(round(s))} km/h")

    cnt = Counter(speed_keys)

    # If too many unique speeds, keep top N and aggregate others as 'Other'
    MAX_SLICES = 12
    items = cnt.most_common()
    if len(items) > MAX_SLICES:
        top = items[:MAX_SLICES-1]
        other_count = sum(c for _, c in items[MAX_SLICES-1:])
        display_items = top + [('Other', other_count)]
    else:
        display_items = items

    labels = [k for k, v in display_items]
    sizes = [v for k, v in display_items]

    # avoid empty pie
    if sum(sizes) == 0:
        labels = ['No data']
        sizes = [1]

    # generate colors (recycle if needed)
    base_colors = ['#c7c7cc', '#60a5fa', '#34d399', '#fbbf24', '#ef4444', '#a78bfa', '#fb7185', '#60a5fa', '#f472b6', '#38bdf8', '#f97316', '#84cc16']
    colors = [base_colors[i % len(base_colors)] for i in range(len(labels))]

    fig, ax = plt.subplots(figsize=(6, 6))

    # Labels will be the exact speed (e.g., '50 km/h') and autopct will show percentage
    def make_autopct(values):
        def my_autopct(pct):
            total = sum(values)
            val = int(round(pct * total / 100.0))
            return f"{pct:.1f}%\n({val})"
        return my_autopct

    wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct=make_autopct(sizes), startangle=90, colors=colors, textprops={'fontsize':9})
    ax.set_title('Detected Speed')

    # Improve legibility: bold labels for significant slices
    for t in texts:
        t.set_fontsize(9)
    for at in autotexts:
        at.set_fontsize(8)
        at.set_fontweight('bold')

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = os.path.join(output_dir, f"speed_pie_{timestamp}.png")
    plt.savefig(out_path, dpi=140, bbox_inches='tight')
    plt.close()
    print(f"[Analysis] Speed pie saved to: {out_path}")

    # return both paths (main analysis image, speed pie)
    return output_path, out_path


def analyse_latest_log(log_dir: str = None) -> tuple:
    """
    Find the latest log file and generate analysis.

    Args:
        log_dir: Directory containing log files (default: log_files in script dir)

    Returns:
        Tuple of paths to generated images (analysis_png, speed_pie_png)
    """
    if log_dir is None:
        log_dir = os.path.join(os.path.dirname(__file__), "log_files")

    if not os.path.isdir(log_dir):
        raise FileNotFoundError(f"Log directory not found: {log_dir}")

    # Find all log files
    log_files = [f for f in os.listdir(log_dir) if f.startswith("perf_log_") and f.endswith(".txt")]

    if not log_files:
        raise FileNotFoundError("No log files found in " + log_dir)

    # Sort by modification time, get latest
    log_files.sort(key=lambda x: os.path.getmtime(os.path.join(log_dir, x)), reverse=True)
    latest_log = os.path.join(log_dir, log_files[0])

    print(f"[Analysis] Analyzing: {latest_log}")

    # Parse and generate graphs
    data = parse_log_file(latest_log)
    result = generate_graphs(data, log_dir)

    return result


def open_analysis_graph(graph_path: str):
    """Open the generated graph in default image viewer."""
    import subprocess
    import platform

    if platform.system() == 'Windows':
        os.startfile(graph_path)
    elif platform.system() == 'Darwin':  # macOS
        subprocess.call(['open', graph_path])
    else:  # Linux
        subprocess.call(['xdg-open', graph_path])


# Entry point for standalone use
if __name__ == "__main__":
    try:
        graphs = analyse_latest_log()
        # graphs may be a tuple (analysis, speed_pie)
        if isinstance(graphs, tuple):
            for p in graphs:
                try:
                    open_analysis_graph(p)
                except Exception:
                    pass
        else:
            open_analysis_graph(graphs)
    except Exception as e:
        print(f"[Analysis Error] {e}")
