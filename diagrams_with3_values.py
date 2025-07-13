import pandas as pd
from io import StringIO
from matplotlib import pyplot as plt

# === CONFIGURATION ===
FILE_PATH = r"C:\Users\yotam.konopnicki\Desktop\pcap_files\rabbit_studies_04_06-15\network55MCEnc.csv"
RC_PATH = r"C:\Users\yotam.konopnicki\Desktop\pcap_files\rabbit_studies_04_06-15\network55RC.csv"
MC_PATH = r"C:\Users\yotam.konopnicki\Desktop\pcap_files\rabbit_studies_04_06-15\network55MC.csv"
SAMPLE_TIME_MS = 1.040

JOINT_COLUMNS = [
    "J4_Yaw_Right.Filtered",
    "J5_Pitch_Right.Filtered",
    "J6_Roll_Right.Filtered"
]

def safe_int_equals(val, target):
    try:
        return int(str(val).strip()) == target
    except:
        return False

def load_custom_csv(path):
    with open(path, 'r') as f:
        lines = f.readlines()
    header_line = next(l for l in lines if l.strip().startswith('% Time'))
    raw_header = [h.strip() for h in header_line.replace('%', '').strip().split(',')]

    # Make column names unique
    header = []
    seen = {}
    for name in raw_header:
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        header.append(name)

    data_start_index = next(i for i, l in enumerate(lines)
                            if not l.strip().startswith('%') and any(v.strip() for v in l.split(',')))
    data_lines = lines[data_start_index:]
    return pd.read_csv(StringIO(''.join(data_lines)), names=header, low_memory=False)

# === Load data ===
main_df = load_custom_csv(FILE_PATH)
mc_df = load_custom_csv(MC_PATH)
rc_df = load_custom_csv(RC_PATH)

# === Check all joint columns exist ===
for col in JOINT_COLUMNS:
    if col not in main_df.columns:
        raise ValueError(f"Column '{col}' not found in main CSV.")
if "msg.joystick_homing_right" not in mc_df.columns:
    raise ValueError("Column 'msg.joystick_homing_right' not found in MC CSV.")
if "rightCmd.slow_mode" not in rc_df.columns:
    raise ValueError("Column 'rightCmd.slow_mode' not found in RC CSV.")

# === Parse time and flags ===
timestamps = [i * SAMPLE_TIME_MS for i in range(len(main_df))]
homing_flags = [safe_int_equals(v, 1) for v in mc_df["msg.joystick_homing_right"][:len(timestamps)]]
engaged_flags = [not safe_int_equals(v, 10) for v in rc_df["rightCmd.slow_mode"][:len(timestamps)]]

# === Process each joint ===
all_data = {
    "Time_ms": [],
    "Is_Homing": [],
    "Is_Engaged": []
}
joint_speeds = {}

for joint in JOINT_COLUMNS:
    raw_vals = [float(v) if str(v).strip() != '' else None for v in main_df[joint]]
    angles = []
    speeds_deg_per_s = []
    speeds_deg_per_ms = []
    times = []
    homing = []
    engaged = []

    # Filter only valid rows
    for v, t, h, e in zip(raw_vals, timestamps, homing_flags, engaged_flags):
        if v is not None:
            angles.append(v)
            times.append(t)
            homing.append(h)
            engaged.append(e)

    # Calculate speeds
    speed_s = [0.0] * len(angles)
    speed_ms = [0.0] * len(angles)
    start_idx = 0
    for i in range(1, len(angles)):
        if angles[i] != angles[i - 1]:
            end_idx = i
            delta_angle = angles[i] - angles[start_idx]
            delta_time = (i - start_idx) * (SAMPLE_TIME_MS / 1000)
            s = delta_angle / delta_time
            ms = s / 1000
            for j in range(start_idx + 1, end_idx + 1):
                speed_s[j] = s
                speed_ms[j] = ms
            start_idx = i

    # Store values
    if joint == "J4_Yaw_Right.Filtered":
        all_data["Time_ms"] = times
        all_data["Is_Homing"] = homing
        all_data["Is_Engaged"] = engaged

    joint_label = joint.split('.')[0].replace('_Right', '')
    all_data[f"{joint_label}_Angle_deg"] = angles
    all_data[f"{joint_label}_Speed_deg_per_s"] = speed_s
    all_data[f"{joint_label}_Speed_deg_per_ms"] = speed_ms

    # Also keep for plotting
    joint_speeds[joint_label] = (times, speed_s, homing, engaged)

# === Create and save output CSVs ===
output_df = pd.DataFrame(all_data)
output_df.to_csv("robot_speed_output_with_flags.csv", index=False)

# === Filter and save filtered CSV ===
filtered_df = output_df[(output_df["Is_Homing"] == False) & (output_df["Is_Engaged"] == True)]
filtered_df.to_csv("robot_speed_filtered_output.csv", index=False)

# === Plot for each joint ===
for joint_label, (times, speed_s, homing, engaged) in joint_speeds.items():
    # Filter points
    filtered_times = [t for t, h, e in zip(times, homing, engaged) if not h and e]
    filtered_speeds = [s for s, h, e in zip(speed_s, homing, engaged) if not h and e]

    plt.figure(figsize=(12, 6))
    plt.plot(filtered_times, filtered_speeds, label=f"{joint_label} Speed (deg/s)", linewidth=1)
    plt.xlabel("Time (ms)")
    plt.ylabel("Speed (deg/s)")
    plt.title(f"{joint_label} Speed over Time (Filtered: Engaged & Not Homing)")
    plt.ylim(-100, 100)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"robot_speed_filtered_plot_{joint_label}.png")
    plt.close()

print("finished plotting")
