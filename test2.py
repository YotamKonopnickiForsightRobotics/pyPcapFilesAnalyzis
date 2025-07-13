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

# === Validate required columns ===
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

# === Process joints ===
all_data = {"Time_ms": [], "Is_Homing": [], "Is_Engaged": []}
joint_data = {}

for joint in JOINT_COLUMNS:
    raw_vals = [float(v) if str(v).strip() != '' else None for v in main_df[joint]]
    angles, speeds_s, speeds_ms, accels, times, homing, engaged = [], [], [], [], [], [], []

    for v, t, h, e in zip(raw_vals, timestamps, homing_flags, engaged_flags):
        if v is not None:
            angles.append(v)
            times.append(t)
            homing.append(h)
            engaged.append(e)

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

    accel = [0.0]
    for i in range(1, len(speed_s)):
        delta_speed = speed_s[i] - speed_s[i - 1]
        a = delta_speed / (SAMPLE_TIME_MS / 1000)
        accel.append(a)

    joint_label = joint.split('.')[0].replace('_Right', '')
    if joint == "J4_Yaw_Right.Filtered":
        all_data["Time_ms"] = times
        all_data["Is_Homing"] = homing
        all_data["Is_Engaged"] = engaged

    all_data[f"{joint_label}_Angle_deg"] = angles
    all_data[f"{joint_label}_Speed_deg_per_s"] = speed_s
    all_data[f"{joint_label}_Speed_deg_per_ms"] = speed_ms
    all_data[f"{joint_label}_Acceleration_deg_per_s2"] = accel

    joint_data[joint_label] = {
        "Time_ms": times,
        "Speed_deg_per_s": speed_s,
        "Acceleration_deg_per_s2": accel,
        "Is_Homing": homing,
        "Is_Engaged": engaged
    }

# === Save output CSVs ===
output_df = pd.DataFrame(all_data)
output_df.to_csv("robot_speed_output_with_flags.csv", index=False)

filtered_df = output_df[(output_df["Is_Homing"] == False) & (output_df["Is_Engaged"] == True)]
filtered_df.to_csv("robot_speed_filtered_output.csv", index=False)

# === Plot speed + acceleration with color-coded segments ===
for joint_label, data in joint_data.items():
    times = data["Time_ms"]
    speeds = data["Speed_deg_per_s"]
    accels = data["Acceleration_deg_per_s2"]
    homing_flags = data["Is_Homing"]
    engaged_flags = data["Is_Engaged"]

    # === SPEED PLOT ===
    plt.figure(figsize=(12, 6))
    start_idx = 0
    for i in range(1, len(times)):
        current_valid = engaged_flags[i] and not homing_flags[i]
        previous_valid = engaged_flags[i - 1] and not homing_flags[i - 1]
        if current_valid != previous_valid or i == len(times) - 1:
            t_chunk = times[start_idx:i]
            s_chunk = speeds[start_idx:i]
            if len(t_chunk) >= 2:
                color = 'green' if previous_valid else 'red'
                plt.plot(t_chunk, s_chunk, color=color, linewidth=1)
            start_idx = i

    plt.xlabel("Time (ms)")
    plt.ylabel("Speed (deg/s)")
    plt.title(f"{joint_label} Speed over Time\nGreen = Engaged & Not Homing, Red = Invalid")
    plt.ylim(-100, 100)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"robot_speed_colored_plot_{joint_label}.png")
    plt.close()

    # === ACCELERATION PLOT ===
    plt.figure(figsize=(12, 6))
    start_idx = 0
    for i in range(1, len(times)):
        current_valid = engaged_flags[i] and not homing_flags[i]
        previous_valid = engaged_flags[i - 1] and not homing_flags[i - 1]
        if current_valid != previous_valid or i == len(times) - 1:
            t_chunk = times[start_idx:i]
            a_chunk = accels[start_idx:i]
            if len(t_chunk) >= 2:
                color = 'green' if previous_valid else 'red'
                plt.plot(t_chunk, a_chunk, color=color, linewidth=1)
            start_idx = i

    plt.xlabel("Time (ms)")
    plt.ylabel("Acceleration (deg/s²)")
    plt.title(f"{joint_label} Acceleration over Time\nGreen = Engaged & Not Homing, Red = Invalid")
    plt.ylim(-100, 100)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"robot_acceleration_colored_plot_{joint_label}.png")
    plt.close()

print("Finished computing and plotting.")
