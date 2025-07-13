import pandas as pd
from io import StringIO
import numpy as np

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


# === Load files ===
main_df = load_custom_csv(FILE_PATH)
mc_df = load_custom_csv(MC_PATH)

# === Validate required columns ===
for col in JOINT_COLUMNS:
    if col not in main_df.columns:
        raise ValueError(f"Missing column: {col}")
if "msg.joystick_homing_right" not in mc_df.columns:
    raise ValueError("Missing column: msg.joystick_homing_right")

# === Parse homing flags ===
homing_flags = [safe_int_equals(v, 1) for v in mc_df["msg.joystick_homing_right"][:len(main_df)]]

# === Analyze homing movement ===
results = []

for joint_col in JOINT_COLUMNS:
    raw_angles = [float(v) if str(v).strip() != '' else None for v in main_df[joint_col][:len(homing_flags)]]

    # Filter only valid + homing data
    homing_angles = [a for a, h in zip(raw_angles, homing_flags) if h and a is not None]

    if len(homing_angles) < 2:
        print(f"{joint_col}: Not enough homing data to analyze.")
        continue

    # Compute total movement (sum of abs delta)
    total_movement = sum(abs(homing_angles[i] - homing_angles[i - 1]) for i in range(1, len(homing_angles)))
    std_dev = np.std(homing_angles)

    joint_label = joint_col.split('.')[0].replace('_Right', '')
    results.append((joint_label, total_movement, std_dev))

    print(f"== {joint_label} ==")
    print(f" Total Movement (deg): {total_movement:.4f}")
    print(f" Std Dev (deg):         {std_dev:.4f}")
    print()

# === Optional: Save results to CSV ===
results_df = pd.DataFrame(results, columns=["Joint", "Total_Movement_deg", "Std_Deviation_deg"])
results_df.to_csv("robot_homing_motion_stats.csv", index=False)

print("Analysis complete. Results saved to 'robot_homing_motion_stats.csv'")
