import customtkinter as ctk
import psutil
import time
import shutil
import threading
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import GPUtil

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class LiveGraph(ctk.CTkFrame):
    def __init__(self, parent, title, y_label, max_points=60, y_limit=100):
        super().__init__(parent, fg_color="transparent")
        self.max_points = max_points
        self.y_limit = y_limit
        
        self.x_data = list(range(max_points))
        self.y_data = deque([0]*max_points, maxlen=max_points)
        self.y_data2 = deque([0]*max_points, maxlen=max_points) # For second line
        self.has_second_line = False

        # Create Figure
        self.fig = Figure(figsize=(5, 2), dpi=100)
        self.fig.patch.set_facecolor('#2b2b2b') 
        
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#2b2b2b')
        self.ax.set_title(title, color='white', fontsize=8)
        self.ax.set_ylabel(y_label, color='white', fontsize=7)
        self.ax.tick_params(axis='x', colors='white', labelsize=6)
        self.ax.tick_params(axis='y', colors='white', labelsize=6)
        self.ax.set_ylim(0, y_limit)
        self.ax.set_xlim(0, max_points - 1)
        self.ax.grid(True, color='#444444', linestyle='--', linewidth=0.5)
        
        # Lines
        self.line1, = self.ax.plot(self.x_data, self.y_data, color='#1f538d', linewidth=1.5)
        self.line2 = None

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def add_second_line(self, label, color='#e0e0e0'):
        self.has_second_line = True
        self.line2, = self.ax.plot(self.x_data, self.y_data2, color=color, linewidth=1.5, label=label)
        self.ax.legend(loc='upper left', facecolor='#2b2b2b', edgecolor='white', labelcolor='white', fontsize=6)

    def update_graph(self, new_value, new_value2=None):
        self.y_data.append(new_value)
        self.line1.set_ydata(self.y_data)
        
        if self.has_second_line and new_value2 is not None:
            self.y_data2.append(new_value2)
            self.line2.set_ydata(self.y_data2)
            
            if self.y_limit is None:
                max_val = max(max(self.y_data), max(self.y_data2))
                if max_val > 0:
                    self.ax.set_ylim(0, max_val * 1.2)
        
        self.canvas.draw()

class DataCollector(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = True
        self.lock = threading.Lock()
        self.stats = {
            "cpu": 0,
            "ram": {"percent": 0, "used": 0, "total": 0},
            "gpu": {"load": 0, "memoryUsed": 0, "memoryTotal": 0, "temperature": 0, "found": False},
            "disk_text": "",
            "disk_io": {"read": 0, "write": 0},
            "net_io": {"sent": 0, "recv": 0, "up_mb": 0, "down_mb": 0},
            "processes": []
        }
        self.prev_net_io = psutil.net_io_counters()
        self.prev_disk_io = psutil.disk_io_counters()
        self.prev_time = time.time()
        self.cpu_count = psutil.cpu_count(logical=True)

    def get_size(self, bytes, suffix="B"):
        factor = 1024
        for unit in ["", "K", "M", "G", "T", "P"]:
            if bytes < factor:
                return f"{bytes:.2f}{unit}{suffix}"
            bytes /= factor

    def run(self):
        while self.running:
            try:
                # --- CPU ---
                cpu_percent = psutil.cpu_percent(interval=None)

                # --- RAM ---
                svmem = psutil.virtual_memory()
                ram_stats = {
                    "percent": svmem.percent,
                    "used": svmem.used,
                    "total": svmem.total
                }

                # --- GPU ---
                gpu_stats = {"found": False, "load": 0, "memoryUsed": 0, "memoryTotal": 0, "temperature": 0}
                try:
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        gpu = gpus[0]
                        gpu_stats = {
                            "found": True,
                            "load": gpu.load * 100,
                            "memoryUsed": gpu.memoryUsed,
                            "memoryTotal": gpu.memoryTotal,
                            "temperature": gpu.temperature
                        }
                except Exception:
                    pass

                # --- Disk Space ---
                partitions = psutil.disk_partitions()
                disk_text = ""
                for partition in partitions:
                    try:
                        usage = shutil.disk_usage(partition.mountpoint)
                        percent = (usage.used / usage.total) * 100
                        disk_text += f"{partition.device} ({partition.mountpoint}): {percent:.1f}% Used of {self.get_size(usage.total)}\n"
                    except Exception:
                        continue

                # --- Time Delta ---
                curr_time = time.time()
                time_delta = curr_time - self.prev_time
                if time_delta == 0: time_delta = 1

                # --- Disk I/O ---
                curr_disk_io = psutil.disk_io_counters()
                read_bytes_sec = (curr_disk_io.read_bytes - self.prev_disk_io.read_bytes) / time_delta
                write_bytes_sec = (curr_disk_io.write_bytes - self.prev_disk_io.write_bytes) / time_delta
                disk_io_stats = {
                    "read": read_bytes_sec / (1024 * 1024), # MB/s
                    "write": write_bytes_sec / (1024 * 1024) # MB/s
                }
                self.prev_disk_io = curr_disk_io

                # --- Network I/O ---
                curr_net_io = psutil.net_io_counters()
                bytes_sent_sec = (curr_net_io.bytes_sent - self.prev_net_io.bytes_sent) / time_delta
                bytes_recv_sec = (curr_net_io.bytes_recv - self.prev_net_io.bytes_recv) / time_delta
                net_io_stats = {
                    "sent": bytes_sent_sec,
                    "recv": bytes_recv_sec,
                    "up_mb": bytes_sent_sec / (1024 * 1024),
                    "down_mb": bytes_recv_sec / (1024 * 1024)
                }
                self.prev_net_io = curr_net_io
                self.prev_time = curr_time

                # --- Processes ---
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                    try:
                        processes.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                processes = sorted(processes, key=lambda p: p['cpu_percent'], reverse=True)[:10]
                
                # Normalize CPU
                proc_list = []
                for p in processes:
                    norm_cpu = p['cpu_percent'] / self.cpu_count
                    proc_list.append({
                        "pid": p['pid'],
                        "name": p['name'],
                        "cpu": norm_cpu
                    })

                # --- Update Shared Stats ---
                with self.lock:
                    self.stats = {
                        "cpu": cpu_percent,
                        "ram": ram_stats,
                        "gpu": gpu_stats,
                        "disk_text": disk_text,
                        "disk_io": disk_io_stats,
                        "net_io": net_io_stats,
                        "processes": proc_list
                    }

                time.sleep(1)
            except Exception as e:
                print(f"Error in DataCollector: {e}")
                time.sleep(1)

class SystemDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("System Monitor")
        self.geometry("1100x950")

        # Configure grid layout (1x2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        self.sidebar_visible = True

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="SysMonitor", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.sidebar_button_1 = ctk.CTkButton(self.sidebar_frame, text="Overview", command=self.show_overview)
        self.sidebar_button_1.grid(row=1, column=0, padx=20, pady=10)
        
        # Main Content Area
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1) # Content row

        # Header Frame (Menu Button)
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent", height=40)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        self.menu_button = ctk.CTkButton(self.header_frame, text="<", width=30, command=self.toggle_sidebar)
        self.menu_button.pack(side="left")

        # Scrollable Content
        self.content_scroll = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        self.content_scroll.grid(row=1, column=0, sticky="nsew")
        self.content_scroll.grid_columnconfigure(0, weight=1)

        # --- CPU Section ---
        self.cpu_frame = ctk.CTkFrame(self.content_scroll)
        self.cpu_frame.grid(row=0, column=0, padx=20, pady=10, sticky="ew")
        
        self.cpu_header = ctk.CTkFrame(self.cpu_frame, fg_color="transparent")
        self.cpu_header.pack(fill="x", padx=10, pady=5)
        self.cpu_toggle_btn = ctk.CTkButton(self.cpu_header, text="▼", width=20, height=20, command=lambda: self.toggle_graph(self.cpu_graph, self.cpu_toggle_btn))
        self.cpu_toggle_btn.pack(side="left", padx=(0, 10))
        self.cpu_label = ctk.CTkLabel(self.cpu_header, text="CPU Usage", font=ctk.CTkFont(size=16, weight="bold"))
        self.cpu_label.pack(side="left")
        
        self.cpu_progressbar = ctk.CTkProgressBar(self.cpu_frame)
        self.cpu_progressbar.pack(fill="x", padx=10, pady=5)
        self.cpu_percent_label = ctk.CTkLabel(self.cpu_frame, text="0%")
        self.cpu_percent_label.pack(anchor="e", padx=10, pady=5)
        
        self.cpu_graph = LiveGraph(self.cpu_frame, "CPU History", "%", y_limit=100)
        self.cpu_graph.pack(fill="x", padx=10, pady=10)

        # --- RAM Section ---
        self.ram_frame = ctk.CTkFrame(self.content_scroll)
        self.ram_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        self.ram_header = ctk.CTkFrame(self.ram_frame, fg_color="transparent")
        self.ram_header.pack(fill="x", padx=10, pady=5)
        self.ram_toggle_btn = ctk.CTkButton(self.ram_header, text="▼", width=20, height=20, command=lambda: self.toggle_graph(self.ram_graph, self.ram_toggle_btn))
        self.ram_toggle_btn.pack(side="left", padx=(0, 10))
        self.ram_label = ctk.CTkLabel(self.ram_header, text="RAM Usage", font=ctk.CTkFont(size=16, weight="bold"))
        self.ram_label.pack(side="left")
        
        self.ram_progressbar = ctk.CTkProgressBar(self.ram_frame)
        self.ram_progressbar.pack(fill="x", padx=10, pady=5)
        self.ram_stats_label = ctk.CTkLabel(self.ram_frame, text="Used: 0GB / Total: 0GB")
        self.ram_stats_label.pack(anchor="e", padx=10, pady=5)

        self.ram_graph = LiveGraph(self.ram_frame, "RAM History", "%", y_limit=100)
        self.ram_graph.pack(fill="x", padx=10, pady=10)

        # --- GPU Section ---
        self.gpu_frame = ctk.CTkFrame(self.content_scroll)
        self.gpu_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        
        self.gpu_header = ctk.CTkFrame(self.gpu_frame, fg_color="transparent")
        self.gpu_header.pack(fill="x", padx=10, pady=5)
        self.gpu_toggle_btn = ctk.CTkButton(self.gpu_header, text="▼", width=20, height=20, command=lambda: self.toggle_graph(self.gpu_graph, self.gpu_toggle_btn))
        self.gpu_toggle_btn.pack(side="left", padx=(0, 10))
        self.gpu_label = ctk.CTkLabel(self.gpu_header, text="GPU Usage", font=ctk.CTkFont(size=16, weight="bold"))
        self.gpu_label.pack(side="left")
        
        self.gpu_progressbar = ctk.CTkProgressBar(self.gpu_frame)
        self.gpu_progressbar.pack(fill="x", padx=10, pady=5)
        self.gpu_stats_label = ctk.CTkLabel(self.gpu_frame, text="Searching for GPU...")
        self.gpu_stats_label.pack(anchor="e", padx=10, pady=5)
        
        self.gpu_graph = LiveGraph(self.gpu_frame, "GPU Load History", "%", y_limit=100)
        self.gpu_graph.pack(fill="x", padx=10, pady=10)

        # --- Disk Section ---
        self.disk_frame = ctk.CTkFrame(self.content_scroll)
        self.disk_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        
        self.disk_header = ctk.CTkFrame(self.disk_frame, fg_color="transparent")
        self.disk_header.pack(fill="x", padx=10, pady=5)
        self.disk_toggle_btn = ctk.CTkButton(self.disk_header, text="▼", width=20, height=20, command=lambda: self.toggle_graph(self.disk_graph, self.disk_toggle_btn))
        self.disk_toggle_btn.pack(side="left", padx=(0, 10))
        self.disk_label = ctk.CTkLabel(self.disk_header, text="Disk Usage", font=ctk.CTkFont(size=16, weight="bold"))
        self.disk_label.pack(side="left")
        
        self.disk_container = ctk.CTkFrame(self.disk_frame, fg_color="transparent")
        self.disk_container.pack(fill="x", padx=10, pady=5)
        self.disk_info_label = ctk.CTkLabel(self.disk_container, text="", justify="left")
        self.disk_info_label.pack(anchor="w")

        self.disk_graph = LiveGraph(self.disk_frame, "Disk Activity (MB/s)", "MB/s", y_limit=None)
        self.disk_graph.add_second_line("Write", color="#ff7f0e")
        self.disk_graph.pack(fill="x", padx=10, pady=10)

        # --- Network Section ---
        self.net_frame = ctk.CTkFrame(self.content_scroll)
        self.net_frame.grid(row=4, column=0, padx=20, pady=10, sticky="ew")
        
        self.net_header = ctk.CTkFrame(self.net_frame, fg_color="transparent")
        self.net_header.pack(fill="x", padx=10, pady=5)
        self.net_toggle_btn = ctk.CTkButton(self.net_header, text="▼", width=20, height=20, command=lambda: self.toggle_graph(self.net_graph, self.net_toggle_btn))
        self.net_toggle_btn.pack(side="left", padx=(0, 10))
        self.net_label = ctk.CTkLabel(self.net_header, text="Network", font=ctk.CTkFont(size=16, weight="bold"))
        self.net_label.pack(side="left")
        
        self.net_stats_label = ctk.CTkLabel(self.net_frame, text="Sent: 0B | Recv: 0B")
        self.net_stats_label.pack(anchor="w", padx=10, pady=5)

        self.net_graph = LiveGraph(self.net_frame, "Network Traffic (MB/s)", "MB/s", y_limit=None)
        self.net_graph.add_second_line("Download", color="#ff7f0e") 
        self.net_graph.pack(fill="x", padx=10, pady=10)

        # --- Processes Section ---
        self.proc_frame = ctk.CTkFrame(self.content_scroll)
        self.proc_frame.grid(row=5, column=0, padx=20, pady=10, sticky="ew")
        self.proc_label = ctk.CTkLabel(self.proc_frame, text="Top Processes (Total CPU %)", font=ctk.CTkFont(size=16, weight="bold"))
        self.proc_label.pack(anchor="w", padx=10, pady=5)
        
        self.proc_header_frame = ctk.CTkFrame(self.proc_frame, fg_color="transparent")
        self.proc_header_frame.pack(fill="x", padx=10, pady=2)
        self.proc_header_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self.proc_header_frame, text="PID", width=60, anchor="w", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0)
        ctk.CTkLabel(self.proc_header_frame, text="Name", anchor="w", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(self.proc_header_frame, text="CPU %", width=60, anchor="e", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2)

        self.proc_rows = []
        for i in range(10):
            row_frame = ctk.CTkFrame(self.proc_frame, fg_color="transparent")
            row_frame.pack(fill="x", padx=10, pady=2)
            row_frame.grid_columnconfigure(1, weight=1)
            
            pid_lbl = ctk.CTkLabel(row_frame, text="-", width=60, anchor="w")
            pid_lbl.grid(row=0, column=0)
            
            name_lbl = ctk.CTkLabel(row_frame, text="-", anchor="w")
            name_lbl.grid(row=0, column=1, sticky="ew")
            
            cpu_lbl = ctk.CTkLabel(row_frame, text="-", width=60, anchor="e")
            cpu_lbl.grid(row=0, column=2)
            
            self.proc_rows.append((pid_lbl, name_lbl, cpu_lbl))

        # Start Data Collector
        self.collector = DataCollector()
        self.collector.start()
        
        # Start update loop
        self.update_stats()

    def toggle_sidebar(self):
        if self.sidebar_visible:
            self.sidebar_frame.grid_remove()
            self.sidebar_visible = False
            self.menu_button.configure(text=">")
        else:
            self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
            self.sidebar_visible = True
            self.menu_button.configure(text="<")

    def toggle_graph(self, graph_widget, button):
        if graph_widget.winfo_viewable():
            graph_widget.pack_forget()
            button.configure(text="▶")
        else:
            graph_widget.pack(fill="x", padx=10, pady=10)
            button.configure(text="▼")

    def show_overview(self):
        pass

    def get_size(self, bytes, suffix="B"):
        factor = 1024
        for unit in ["", "K", "M", "G", "T", "P"]:
            if bytes < factor:
                return f"{bytes:.2f}{unit}{suffix}"
            bytes /= factor

    def update_stats(self):
        try:
            with self.collector.lock:
                stats = self.collector.stats.copy()

            # CPU
            self.cpu_progressbar.set(stats["cpu"] / 100)
            self.cpu_percent_label.configure(text=f"{stats['cpu']}%")
            if self.cpu_graph.winfo_viewable():
                self.cpu_graph.update_graph(stats["cpu"])

            # RAM
            self.ram_progressbar.set(stats["ram"]["percent"] / 100)
            self.ram_stats_label.configure(text=f"Used: {self.get_size(stats['ram']['used'])} / Total: {self.get_size(stats['ram']['total'])} ({stats['ram']['percent']}%)")
            if self.ram_graph.winfo_viewable():
                self.ram_graph.update_graph(stats["ram"]["percent"])

            # GPU
            if stats["gpu"]["found"]:
                self.gpu_progressbar.set(stats["gpu"]["load"] / 100)
                self.gpu_stats_label.configure(text=f"Memory: {stats['gpu']['memoryUsed']}MB / {stats['gpu']['memoryTotal']}MB | Temp: {stats['gpu']['temperature']}C")
                if self.gpu_graph.winfo_viewable():
                    self.gpu_graph.update_graph(stats["gpu"]["load"])
            else:
                self.gpu_stats_label.configure(text="No NVIDIA GPU detected")
                self.gpu_progressbar.set(0)

            # Disk
            self.disk_info_label.configure(text=stats["disk_text"])
            if self.disk_graph.winfo_viewable():
                self.disk_graph.update_graph(stats["disk_io"]["read"], stats["disk_io"]["write"])

            # Network
            self.net_stats_label.configure(text=f"Upload: {self.get_size(stats['net_io']['sent'])}/s | Download: {self.get_size(stats['net_io']['recv'])}/s")
            if self.net_graph.winfo_viewable():
                self.net_graph.update_graph(stats["net_io"]["up_mb"], stats["net_io"]["down_mb"])

            # Processes
            for i, row_widgets in enumerate(self.proc_rows):
                if i < len(stats["processes"]):
                    p = stats["processes"][i]
                    row_widgets[0].configure(text=str(p['pid']))
                    row_widgets[1].configure(text=p['name'])
                    row_widgets[2].configure(text=f"{p['cpu']:.1f}%")
                else:
                    row_widgets[0].configure(text="-")
                    row_widgets[1].configure(text="-")
                    row_widgets[2].configure(text="-")

        except Exception as e:
            print(f"Error in update_stats: {e}")

        # Schedule next update
        self.after(1000, self.update_stats)

if __name__ == "__main__":
    app = SystemDashboard()
    app.mainloop()
