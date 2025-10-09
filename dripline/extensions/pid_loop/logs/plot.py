import csv
import glob
import os
from datetime import datetime
import matplotlib.pyplot as plt

log_dir = "./logs"
csv_files = glob.glob(os.path.join(log_dir, "pid_log*.csv"))
print(f"Found {len(csv_files)} CSV files in {log_dir}")
print(f"CSV files: {csv_files}")

for csv_file in csv_files:
    times, PV, SP, throttle = [], [], [], []

    with open(csv_file, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            # assuming column order: time, PV, SP, throttle
            try:
                times.append(datetime.fromisoformat(row[0]))
                PV.append(float(row[1]))
                SP.append(float(row[2]))
                throttle.append(float(row[3]))
            except Exception as e:
                print(f"Skipping row in {csv_file}: {row}, error={e}")

    if not times:
        print(f"Skipping {csv_file}, no valid data")
        continue

    # Use filename (without extension) as title
    title_str = os.path.basename(csv_file).replace(".csv", "")
    print(f"Saving plot to {title_str}_sensor.png")
    print(f"Saving plot to {title_str}_throttle.png")

    # Sensor vs Setpoint
    plt.figure()
    plt.plot(times, PV, 'ro', label="PV (sensor)", ms=1)
    plt.plot(times, SP, label="SP (setpoint)", linestyle="--")
    plt.xlabel("Time")
    plt.ylabel("Sensor Value")
    plt.title(f"{title_str}: Sensor vs Setpoint")
    plt.legend()
    plt.grid(True)
    plt.savefig(f"{title_str}_sensor.png", dpi=300)
    plt.close()

    # Throttle vs Time
    plt.figure()
    plt.plot(times, throttle, 'go', label="Throttle (actuator)", ms=1)
    plt.xlabel("Time")
    plt.ylabel("Throttle")
    plt.title(f"{title_str}: Throttle")
    plt.legend()
    plt.grid(True)
    plt.savefig(f"{title_str}_throttle.png", dpi=300)
    plt.close()
    print(f"Saved plot to {title_str}_throttle.png")
    print(f"Saved plot to {title_str}_sensor.png")
    print(f"Saved plot to {title_str}_throttle.png")

print("Plots saved for all CSV files in logs/")
