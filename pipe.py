# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "matplotlib",
#     "numpy",
#     "pyserial",
#     "scipy",
# ]
# ///

import serial
import time
import csv
import os
from datetime import datetime
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk  # Import ttk for the Combobox (Dropdown)
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from scipy.signal import savgol_filter
from serial.tools import list_ports

# --- Configuration Constants ---
BAUD_RATE = 115200
RECORD_DURATION_SECONDS = 2.5
DATA_COLUMNS = 6 

# --- Base Data Folder ---
BASE_FOLDER_NAME = "samples"

# --- Wio Terminal Detection IDs ---
# Vendor ID (VID) and Product ID (PID) for the Seeed Wio Terminal
WIO_VID = 10374
WIO_PID = 32813

# --- Smoothing Configuration ---
SMOOTHING_WINDOW_LENGTH = 11 
SMOOTHING_POLYNOMIAL_ORDER = 3 

# --- Global Port Detection Function ---
def auto_detect_wio_port():
    """Scans all available serial ports for the specific VID/PID of the Wio Terminal."""
    for port in list_ports.comports():
        if port.vid == WIO_VID and port.pid == WIO_PID:
            return port.device
    return None

class SerialRecorderApp:
    def __init__(self, master):
        self.master = master
        master.title("Labeled Serial Data Recorder")

        # --- Port Detection ---
        self.wio_port_name = auto_detect_wio_port()
        
        if not self.wio_port_name:
            initial_status = "ERROR: Wio Terminal not found! Check connection."
            print("ERROR: Wio Terminal not found! Check connection.")
            record_state = tk.DISABLED
        else:
            initial_status = f"Wio Terminal found on port: {self.wio_port_name}"
            print(f"Wio Terminal found on port: {self.wio_port_name}")
            record_state = tk.NORMAL

        # --- Matplotlib Figure Setup ---
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.ax.set_title("Data Preview")
        self.ax.set_xlabel("Sample Index")
        self.ax.set_ylabel("Value")
        
        # --- GUI Layout ---
        self.main_frame = tk.Frame(master)
        self.main_frame.pack(padx=10, pady=10)

        # Initialize status_var
        self.status_var = tk.StringVar(value=initial_status) 
        
        # 1. Control Panel (Left Side)
        self.control_frame = tk.LabelFrame(self.main_frame, text="Controls & Samples")
        self.control_frame.pack(side=tk.LEFT, padx=10, pady=5, fill="y")
        
        # Folder Creation Check
        self.create_base_data_folder()
        
        # --- Label Selection and Management ---
        label_frame = tk.Frame(self.control_frame)
        label_frame.pack(pady=(10, 5), padx=10, fill="x")
        tk.Label(label_frame, text="Current Label:").pack(side=tk.LEFT, padx=(0, 5))
        
        # Initialize StringVar and Combobox
        self.current_label = tk.StringVar() 
        self.label_combobox = ttk.Combobox(label_frame, textvariable=self.current_label, state="readonly", width=15)
        self.label_combobox.pack(side=tk.LEFT, fill="x", expand=True)
        self.label_combobox.bind("<<ComboboxSelected>>", self.label_selected)
        
        # Button to Add New Label
        tk.Button(label_frame, text="+", command=self.prompt_new_label, width=2).pack(side=tk.LEFT, padx=(5, 0))
        
        # Record Button (Shortcut 'X')
        self.record_button = tk.Button(self.control_frame, text="Record (Press X)", 
                                        command=self.record_and_save_data, 
                                        bg="lightblue", font=("Arial", 12, "bold"),
                                        state=record_state)
        self.record_button.pack(pady=10, padx=10, fill="x")
        
        self.load_labels()
        
        # Set default label if available (Logic relies on load_labels)
        if self.label_options:
            self.current_label.set(self.label_options[0])
            self.current_label_dir = self.current_label.get().split(' ')[0] # Extract directory name
        else:
            self.current_label.set("No Labels")
            self.current_label_dir = None
            # If no labels exist, disable recording regardless of port
            self.record_button.config(state=tk.DISABLED) 

        # Listbox Label
        tk.Label(self.control_frame, text="Samples in Folder:").pack(pady=(10, 0))
        
        # Listbox for Samples
        self.samples_listbox = tk.Listbox(self.control_frame, height=15, width=40)
        self.samples_listbox.pack(pady=5, padx=10)
        self.samples_listbox.bind("<<ListboxSelect>>", self.preview_selected_sample_event)
        
        # Load samples for the initial/default label
        self.load_sample_list()
        
        # Delete Button (Shortcut 'C')
        self.delete_button = tk.Button(self.control_frame, text="Delete Selected (Press C)", 
                                        command=self.delete_selected_sample, 
                                        bg="salmon", fg="white")
        self.delete_button.pack(pady=(0, 10), padx=10, fill="x")


        # 2. Plotting Panel (Right Side)
        self.plot_frame = tk.LabelFrame(self.main_frame, text="Data Plot")
        self.plot_frame.pack(side=tk.RIGHT, padx=10, pady=5)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

        # Status Label
        self.status_label = tk.Label(master, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Final status check
        if self.wio_port_name and self.current_label_dir:
            self.status_var.set(f"Ready. Recording to '{self.current_label_dir}/'")

        # Bind shortcuts
        master.bind('x', lambda event: self.record_and_save_data())
        master.bind('X', lambda event: self.record_and_save_data())
        master.bind('c', lambda event: self.delete_selected_sample()) 
        master.bind('C', lambda event: self.delete_selected_sample())

    def create_base_data_folder(self):
        """Creates the root 'samples' folder."""
        if not os.path.exists(BASE_FOLDER_NAME):
            os.makedirs(BASE_FOLDER_NAME)
            self.status_var.set(f"Created base data folder: {BASE_FOLDER_NAME}/")

    def load_labels(self):
        """Loads all directories inside BASE_FOLDER_NAME as labels, with sample counts."""
        self.label_dirs = []
        self.label_options = []
        
        if not os.path.exists(BASE_FOLDER_NAME):
            return

        for dirname in os.listdir(BASE_FOLDER_NAME):
            dirpath = os.path.join(BASE_FOLDER_NAME, dirname)
            if os.path.isdir(dirpath):
                self.label_dirs.append(dirname)
                
                # Count CSV files in the directory
                count = sum(1 for entry in os.listdir(dirpath) if entry.endswith(".csv"))
                self.label_options.append(f"{dirname} ({count} samples)")

        self.label_dirs.sort()
        self.label_options.sort()
        self.label_combobox['values'] = self.label_options
        
        if not self.label_options:
            self.record_button.config(state=tk.DISABLED)

    def prompt_new_label(self):
        """Opens a simple dialog to get a new label name."""
        
        # Simple Toplevel window for input
        dialog = tk.Toplevel(self.master)
        dialog.title("Add New Label")
        
        tk.Label(dialog, text="Enter new label name:").pack(padx=10, pady=5)
        
        entry = tk.Entry(dialog)
        entry.pack(padx=10, pady=5)
        entry.focus()
        
        def save_and_close():
            new_label = entry.get().strip()
            if new_label and new_label not in self.label_dirs:
                self.add_new_label(new_label)
            dialog.destroy()

        tk.Button(dialog, text="Create", command=save_and_close).pack(pady=10)
        self.master.wait_window(dialog) # Wait until dialog is closed

    def add_new_label(self, label_name):
        """Creates a new directory and updates the label list/dropdown."""
        # Sanitize label name (optional but recommended)
        sanitized_name = "".join(c for c in label_name if c.isalnum() or c in ('_', '-')).strip()
        if not sanitized_name:
            self.status_var.set("Error: Label name invalid.")
            return

        new_dir_path = os.path.join(BASE_FOLDER_NAME, sanitized_name)
        try:
            os.makedirs(new_dir_path)
            self.status_var.set(f"Created new label folder: {sanitized_name}")
            
            # Reload labels, select the new one, and load samples
            self.load_labels()
            new_option = f"{sanitized_name} (0 samples)"
            if new_option in self.label_options:
                self.current_label.set(new_option)
                self.current_label_dir = sanitized_name
                self.load_sample_list()
                self.record_button.config(state=tk.NORMAL if self.wio_port_name else tk.DISABLED)
            
        except Exception as e:
            self.status_var.set(f"Error creating label folder: {e}")

    def label_selected(self, event=None):
        """Called when a label is selected from the dropdown."""
        selected_option = self.current_label.get()
        # Extract the directory name (before the space/parenthesis)
        self.current_label_dir = selected_option.split(' ')[0]
        self.load_sample_list()
        self.record_button.config(state=tk.NORMAL if self.wio_port_name else tk.DISABLED)


    def load_sample_list(self):
        """Populates the listbox with names of CSV files in the currently selected label folder."""
        self.samples_listbox.delete(0, tk.END)
        if not self.current_label_dir:
            return

        folder_path = os.path.join(BASE_FOLDER_NAME, self.current_label_dir)
        try:
            filenames = []
            for filename in os.listdir(folder_path):
                if filename.endswith(".csv"):
                    filenames.append(filename)
            
            # Sort the files in descending order (most recent timestamp first)
            filenames.sort(reverse=True) 

            for filename in filenames:
                self.samples_listbox.insert(tk.END, filename)
                
            # Clear the plot when loading a new folder
            self.plot_data([])

        except FileNotFoundError:
            self.status_var.set(f"Error: Label folder '{self.current_label_dir}' not found.")
        except Exception as e:
            self.status_var.set(f"Error loading samples: {e}")

    # --- Serial and Plotting Logic (Modified) ---

    def read_serial_data(self):
        if not self.wio_port_name:
            print("ERROR: Cannot record. Wio Terminal port not detected.")
            self.status_var.set("ERROR: Cannot record. Wio Terminal port not detected.")
            return []

        data = []

        try:
            ser = serial.Serial(self.wio_port_name, BAUD_RATE, timeout=0.1)
            ser.reset_input_buffer()
            self.status_var.set(f"Recording data for {RECORD_DURATION_SECONDS}s...")

            start_ts = None
            duration_ms = RECORD_DURATION_SECONDS * 1000

            while True:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                parts = line.split(",")
                # Expecting 1 timestamp + 6 data columns = 7 parts
                if len(parts) != DATA_COLUMNS + 1: 
                    continue

                try:
                    # Parse timestamp (used for loop duration logic only)
                    timestamp = int(parts[0])

                    # Parse floats (ax, ay, az, gx, gy, gz)
                    floats = [float(x) for x in parts[1:]]
                except ValueError:
                    continue

                if start_ts is None:
                    start_ts = timestamp  # first packet defines 0 ms

                if timestamp - start_ts >= duration_ms:
                    break
                
                # MODIFICATION: Append only the floats (excluding timestamp)
                data.append(floats)

            ser.close()
            self.status_var.set(f"Recording finished. Collected {len(data)} samples.")
            return data

        except Exception as e:
            print(f"Error: {e}")
            self.status_var.set(f"Error: {e}")
            return []

    def save_data_to_csv(self, data):
        """Saves the recorded data to a time-stamped CSV file inside the current label directory."""
        if not data or not self.current_label_dir:
            self.status_var.set("Error: No data or no label selected to save.")
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # New filename format: {DIRECTORY_NAME}_{DATETIME}.csv
        filename = f"{self.current_label_dir}_{timestamp}.csv"
        filepath = os.path.join(BASE_FOLDER_NAME, self.current_label_dir, filename)

        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(data)
            
            self.status_var.set(f"Successfully saved {len(data)} samples to {self.current_label_dir}/{filename}")
            return filepath
            
        except Exception as e:
            self.status_var.set(f"Error saving CSV: {e}")
            return None

    def plot_data(self, data):
        """Clears the current plot, applies Savitzky-Golay smoothing, and draws the first 3 columns."""
        self.ax.clear()
        
        if not data:
            self.ax.set_title("No Data to Display")
            self.canvas.draw()
            return
            
        data_np = np.array(data)
        
        # We need at least 3 columns for ax, ay, az
        if data_np.shape[1] < 3:
            self.ax.set_title("Error: Less than 3 columns available for plotting.")
            self.canvas.draw()
            return
        
        if data_np.shape[0] < SMOOTHING_WINDOW_LENGTH:
            # Only show warning if status isn't currently showing an error
            if not self.status_var.get().startswith("ERROR:"):
                self.status_var.set("Warning: Not enough samples for smoothing. Plotting raw data.")
            smooth_data_np = data_np
        else:
            smooth_data_np = data_np.copy()
            # Smooth columns 0, 1, 2 (ax, ay, az)
            for i in range(3):
                smooth_data_np[:, i] = savgol_filter(
                    data_np[:, i], 
                    window_length=SMOOTHING_WINDOW_LENGTH, 
                    polyorder=SMOOTHING_POLYNOMIAL_ORDER
                )

        column_labels = ["acc_x", "acc_y", "acc_z"]
        
        for i in range(3):
            self.ax.plot(smooth_data_np[:, i], label=column_labels[i])
        
        self.ax.set_title(f"Smoothed Data Preview ({self.current_label_dir})")
        self.ax.set_xlabel("Sample Index")
        self.ax.set_ylabel("Acceleration Value")
        self.ax.legend(loc='upper right')
        self.fig.tight_layout()
        self.canvas.draw()

    def record_and_save_data(self):
        """Handler for the Record button/shortcut."""
        if not self.current_label_dir:
            self.status_var.set("ERROR: Cannot record. Please create or select a data label.")
            return

        self.record_button.config(state=tk.DISABLED, text="Recording...")
        self.master.update()
        
        recorded_data = self.read_serial_data()
        saved_filepath = self.save_data_to_csv(recorded_data)
        
        if saved_filepath:
            # Reload list, update count in label dropdown, and set selection
            self.load_labels()
            self.label_selected() # Re-selects the current label to update the list
            
            # The newly saved file will be the first item due to reverse sorting
            if self.samples_listbox.size() > 0:
                self.samples_listbox.selection_clear(0, tk.END)
                self.samples_listbox.selection_set(0)
                self.samples_listbox.event_generate("<<ListboxSelect>>")
            
        self.record_button.config(state=tk.NORMAL)

    def preview_selected_sample_event(self, event=None):
        """Loads and plots the currently selected file."""
        try:
            selected_index = self.samples_listbox.curselection()
            if not selected_index:
                self.plot_data([])
                self.status_var.set("Ready. Select a sample or record new data.")
                return

            filename = self.samples_listbox.get(selected_index[0])
            filepath = os.path.join(BASE_FOLDER_NAME, self.current_label_dir, filename)
            
            self.status_var.set(f"Loading and plotting: {filename}")

            preview_data = []
            with open(filepath, 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    try:
                        floats = [float(x) for x in row]
                        preview_data.append(floats)
                    except ValueError:
                        continue
            
            self.plot_data(preview_data)
            self.status_var.set(f"Previewing: {filename} ({len(preview_data)} samples)")

        except Exception as e:
            self.status_var.set(f"Error previewing file: {e}")

    def delete_selected_sample(self):
        """Deletes the selected CSV file and adjusts the selection focus."""
        selected_index_tuple = self.samples_listbox.curselection()
        
        if not selected_index_tuple or not self.current_label_dir:
            self.status_var.set("Error: Please select a sample to delete.")
            return

        current_index = selected_index_tuple[0]
        filename = self.samples_listbox.get(current_index)
        filepath = os.path.join(BASE_FOLDER_NAME, self.current_label_dir, filename)
        
        try:
            os.remove(filepath)
            
            # --- Selection Focus Logic ---
            next_index_to_select = -1
            
            # Determine the index to select after deletion
            if self.samples_listbox.size() > 1:
                # Try to select the item below (current_index)
                if current_index < self.samples_listbox.size() - 1:
                    next_index_to_select = current_index
                # If deleted item was the last one, select the item above (current_index - 1)
                elif current_index > 0:
                    next_index_to_select = current_index - 1
            
            # 1. Update the label counts and the samples list
            self.load_labels()
            self.label_selected() 
            
            # 2. Set new selection and plot
            if next_index_to_select != -1:
                self.samples_listbox.selection_set(next_index_to_select)
                self.samples_listbox.activate(next_index_to_select)
                self.preview_selected_sample_event()
            else:
                self.plot_data([])
                
            self.status_var.set(f"Successfully deleted: {filename}")

        except OSError as e:
            self.status_var.set(f"Error deleting file: {e}")
        except Exception as e:
            self.status_var.set(f"An unexpected error occurred during deletion: {e}")


if __name__ == "__main__":
    # Create the main window
    root = tk.Tk()
    # Initialize and run the application
    app = SerialRecorderApp(root)
    root.mainloop()