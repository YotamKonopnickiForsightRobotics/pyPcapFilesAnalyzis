import pandas as pd
from io import StringIO
from matplotlib import pyplot as plt

# === CONFIGURATION ===
FILE_PATH = r"C:\Users\yotam.konopnicki\Desktop\pcap_files\rabbit_studies_04_06-15\network63.csv"
RC_PATH = r"C:\Users\yotam.konopnicki\Desktop\pcap_files\rabbit_studies_04_06-15\network63RC.csv"
MC_PATH = r"C:\Users\yotam.konopnicki\Desktop\pcap_files\rabbit_studies_04_06-15\network63MC.csv"
TARGET_COLUMN = "J4_Yaw_Right.Filtered"
SAMPLE_TIME_MS = 1.040


def safe_int_equals(val, target):
    try:
        return int(str(val).strip()) == target
    except:
        return False



# === Helper function to load CSVs with headers starting with '%' ===
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


# === Load main, MC, and RC data ===
main_df = load_custom_csv(FILE_PATH)
mc_df = load_custom_csv(MC_PATH)
rc_df = load_custom_csv(RC_PATH)

# === Extract relevant columns ===
if TARGET_COLUMN not in main_df.columns:
    raise ValueError(f"Column '{TARGET_COLUMN}' not found in main CSV.")
if "msg.joystick_homing_right" not in mc_df.columns:
    raise ValueError("Column 'msg.joystick_homing_right' not found in MC CSV.")
if "rightCmd.slow_mode" not in rc_df.columns:
    raise ValueError("Column 'rightCmd.slow_mode' not found in RC CSV.")

raw_angles = [float(a) if str(a).strip() != '' else None for a in main_df[TARGET_COLUMN]]
timestamps = [i * SAMPLE_TIME_MS for i in range(len(raw_angles))]
homing_flags = [safe_int_equals(v, 1) for v in mc_df["msg.joystick_homing_right"][:len(timestamps)]]
engaged_flags = [not safe_int_equals(v, 10) for v in rc_df["rightCmd.slow_mode"][:len(timestamps)]]

# === Clean and calculate speed ===
angles, valid_times, homing_states, engaged_states = [], [], [], []
for angle, t, h, e in zip(raw_angles, timestamps, homing_flags, engaged_flags):
    if angle is not None:
        angles.append(angle)
        valid_times.append(t)
        homing_states.append(h)
        engaged_states.append(e)

speeds_deg_per_s = [0.0] * len(angles)
speeds_deg_per_ms = [0.0] * len(angles)
start_idx = 0
for i in range(1, len(angles)):
    if angles[i] != angles[i - 1]:
        end_idx = i
        delta_angle = angles[i] - angles[start_idx]
        delta_time = (i - start_idx) * (SAMPLE_TIME_MS / 1000)
        speed_deg_per_s = delta_angle / delta_time
        speed_deg_per_ms = speed_deg_per_s / 1000
        for j in range(start_idx + 1, end_idx + 1):
            speeds_deg_per_s[j] = speed_deg_per_s
            speeds_deg_per_ms[j] = speed_deg_per_ms
        start_idx = i

# === Create full DataFrame ===
output_df = pd.DataFrame({
    "Time_ms": valid_times,
    "Angle_deg": angles,
    "Speed_deg_per_ms": speeds_deg_per_ms,
    "Speed_deg_per_s": speeds_deg_per_s,
    "Is_Homing": homing_states,
    "Is_Engaged": engaged_states
})

# Save full CSV with flags
output_df.to_csv("robot_speed_output_with_flags.csv", index=False)

# === Filter for plotting and filtered CSV ===
filtered_df = output_df[(output_df["Is_Homing"] == False) & (output_df["Is_Engaged"] == True)]
filtered_df.to_csv("robot_speed_filtered_output.csv", index=False)

# === Plotting ===
plt.figure(figsize=(12, 6))
plt.plot(filtered_df["Time_ms"], filtered_df["Speed_deg_per_s"], label="Speed (deg/s)", linewidth=1)
plt.xlabel("Time (ms)")
plt.ylabel("Speed (deg/s)")
plt.title("Robot Arm Speed over Time (Filtered: Engaged & Not Homing)")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig("robot_speed_filtered_plot.png")
plt.show()

print("finished plotting")
