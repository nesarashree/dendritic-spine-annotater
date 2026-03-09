import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
import os

# Set this to your actual time interval between frames (in minutes)
FRAME_INTERVAL_MIN = 5  # ← change if needed

def calculate_motility(csv_file):
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()
    print(f"cols in CSV {df.columns.tolist()}")

    # Filter to only properly named spines
    df = df[df['spine_name'].str.match(r'^spine_\d+$', na=False)]

    spines = df['spine_name'].unique()
    print(f"unique spines found in CSV {spines}")

    results = []

    for spine in spines:
        spine_data = df[df['spine_name'] == spine].copy()
        spine_data = spine_data.sort_values('image_idx')  # CRITICAL: sort by time
        
        # Reset index after sorting
        spine_data = spine_data.reset_index(drop=True)

        lengths = spine_data['length_microns'].values
        frames = spine_data['image_idx'].values

        if len(lengths) < 2:
            print(f"  Skipping {spine}: not enough timepoints")
            continue

        # Calculate total time based on ACTUAL frame differences, not just first-last
        # This accounts for missing frames
        total_time = 0
        sum_differences = 0
        
        for i in range(len(lengths) - 1):
            # Time between consecutive measurements
            frame_diff = frames[i+1] - frames[i]
            time_diff = frame_diff * FRAME_INTERVAL_MIN
            
            # Length change
            length_diff = abs(lengths[i+1] - lengths[i])
            
            # Add to totals
            total_time += time_diff
            sum_differences += length_diff

        if total_time == 0:
            print(f"  Skipping {spine}: zero time duration")
            continue

        # Motility = (1/T) * sum of absolute length changes
        motility = sum_differences / total_time

        results.append({
            'spine_name': spine,
            'motility (microns per min)': motility,
            'n_timepoints': len(lengths),
            'total_time_min': total_time
        })

    return pd.DataFrame(results)


if __name__ == "__main__":
    folder_path = "/Users/nesarashree/Downloads/CSV-scaled-time=5"
    all_results = []

    for file in os.listdir(folder_path):
        if file.endswith(".csv"):
            csv_file = os.path.join(folder_path, file)
            print(f"\nProcessing: {csv_file}")
            motility_results = calculate_motility(csv_file)
            motility_results['source_file'] = file
            all_results.append(motility_results)

    if all_results:
        combined_results = pd.concat(all_results, ignore_index=True)
        print("\nAll motility results:")
        print(combined_results.to_string(index=False))

        # Summary statistics
        print("\n=== SUMMARY STATISTICS ===")
        for file in combined_results['source_file'].unique():
            subset = combined_results[combined_results['source_file'] == file]
            motility_values = subset['motility (microns per min)']
            print(f"\n{file}:")
            print(f"  n = {len(motility_values)} spines")
            print(f"  Mean ± SEM: {motility_values.mean():.4f} ± {motility_values.sem():.4f}")
            print(f"  Median: {motility_values.median():.4f}")
            print(f"  Range: {motility_values.min():.4f} - {motility_values.max():.4f}")

        combined_results.to_csv('motility_results.csv', index=False)
        output_path = os.path.abspath('motility_results.csv')  # Get full path
        print(f"\nResults saved to: {output_path}")

        # Visualize
        fig, ax = plt.subplots(figsize=(10, 6))
        file_groups = combined_results.groupby('source_file')['motility (microns per min)']
        means = file_groups.mean()
        sems = file_groups.sem()

        x_pos = np.arange(len(means))
        ax.bar(x_pos, means, yerr=sems, capsize=5,
               color='pink', edgecolor='black', linewidth=2, width=0.6)

        ax.set_ylabel('Motility (µm/min)', fontsize=12, fontweight='bold')
        ax.set_xticks(x_pos)
        ax.set_xticklabels([f.replace('.csv', '') for f in means.index],
                           rotation=45, ha='right', fontsize=10, fontweight='bold')
        ax.set_ylim(0, max(means) * 1.3)
        ax.tick_params(width=2, length=6)
        for spine in ax.spines.values():
            spine.set_linewidth(2)

        plt.tight_layout()
        plt.savefig('motility_bar_chart.png', dpi=300, bbox_inches='tight')
        plt.show()
        print("\nBar chart saved to 'motility_bar_chart.png'")
    else:
        print("No CSV files found")