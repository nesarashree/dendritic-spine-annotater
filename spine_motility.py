import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
import os

# loading spines: from a csv file :
def calculate_motility(csv_file):
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()
    print(f"cols in CSV {df.columns.tolist()}")

    spines = df['spine_name'].unique() # treat each spine name as a unique object (each gets its own motility calculation in output!)
    print(f"unique spines found in CSV {spines}")

    results = []
    
    for spine in spines:
        spine_data = df[df['spine_name'] == spine].copy()
        spine_data = spine_data.sort_values('Time (min)')
        
        lengths = spine_data['length_microns'].values
        times = spine_data['Time (min)'].values
        
        T = times[-1] - times[0] # total time duration

        # calculate summation by looping over lengths t=0 to t=T-delta
        sum_differences = 0
        for i in range(len(lengths)-1):
            current_length = lengths[i] # lengths(s,t)
            next_length = lengths[i+1] # advance time point to lengths(s,t+delta) 
            difference = abs(next_length - current_length) # abs value bc spine can be growing/shrinking 
            sum_differences += difference
        
        # calculate motility as 1/T * summation
        motility = (1/T) * sum_differences
        
        results.append({
            'spine_name': spine,
            'motility (microns per min)': motility
        })
    
    return pd.DataFrame(results)

if __name__ == "__main__":
    folder_path = "/Users/nesarashree/Downloads/spinemotilityCSVtests"  # folder containing CSVs
    all_results = []

    for file in os.listdir(folder_path):
        if file.endswith(".csv"):
            csv_file = os.path.join(folder_path, file)
            print(f"\nProcessing: {csv_file}")
            motility_results = calculate_motility(csv_file)
            motility_results['source_file'] = file  # track which CSV it came from
            all_results.append(motility_results)

    if all_results:
        combined_results = pd.concat(all_results, ignore_index=True)
        print("\nall motility results:")
        print(combined_results.to_string(index=False))
        
        combined_results.to_csv('motility_results.csv', index=False)
        print("\nresults saved to 'motility_results.csv'")

        # visualize
        fig, ax = plt.subplots(figsize=(10, 6))
        file_groups = combined_results.groupby('source_file')['motility (microns per min)'] # take from the results csv
        means = file_groups.mean() # average of spine motilities for each file
        sems = file_groups.sem()
        
        # init bar chart
        x_pos = np.arange(len(means))
        ax.bar(x_pos, means, yerr = sems, capsize = 5, color='pink', edgecolor='black', linewidth=2, width=0.6)
        
        ax.set_ylabel('motility (um/min)', fontsize=12, fontweight='bold')
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
        print("\n bar chart saved to 'motility_bar_chart.png'")
    else:
        print("no CSV files found")
