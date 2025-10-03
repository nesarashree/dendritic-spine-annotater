import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import numpy as np
from PIL import Image, ImageTk, ImageDraw
import pandas as pd
import os
import math
from typing import List, Tuple, Dict, Optional

try:
    import tifffile
    TIFFFILE_AVAILABLE = True
except ImportError:
    TIFFFILE_AVAILABLE = False
    print("run in terminal: pip install tifffile")

class SpineAnnotationTool:
    #  initialize application window, data structures for storing images + annotations, and default config values
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Dendritic Spine Annotation Tool")
        self.root.geometry("1200x800")
        
        self.images: List[Image.Image] = []
        self.image_paths: List[str] = []
        self.current_image_idx = 0
        self.current_spine_name = "spine_1"

        # box annotations
        self.spine_annotations: Dict[str, Dict[int, Tuple[int, int, int, int]]] = {}  # spine_name, {image_idx: (x1, y1, x2, y2)}
        self.spine_colors: Dict[str, str] = {}
        self.measurements_df = pd.DataFrame(columns=['spine_name', 'image_idx', 'length_pixels', 'length_microns', 'stable'])
        
        self.pixel_to_micron = 1/7.75  # conversion factor
        self.stability_threshold = 50  # placeholder (pixel length for spine to be considered stable/unstable)
        
        # UI state
        self.zoom_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.drawing = False
        self.start_x = None
        self.start_y = None
        self.current_box = None
        
        self.available_colors = ['red', 'blue', 'green', 'orange', 'purple', 'cyan', 'yellow', 'pink']
        self.color_index = 0
        
        self.setup_ui()
        
    # create UI elements (buttons, scrollbar, event bindings)
    def setup_ui(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill='x', pady=(0, 5))
        
        # file operations
        ttk.Button(control_frame, text="Load Images", command=self.load_images).pack(side='left', padx=2)
        ttk.Button(control_frame, text="Save Data", command=self.save_data).pack(side='left', padx=2)
        ttk.Button(control_frame, text="Save Annotations", command=self.save_annotations).pack(side='left', padx=2)
        ttk.Button(control_frame, text="Load Annotations", command=self.load_annotations).pack(side='left', padx=2)
        
        
        ttk.Separator(control_frame, orient='vertical').pack(side='left', fill='y', padx=5)
        
        # spine management
        ttk.Label(control_frame, text="Current Spine:").pack(side='left', padx=(5,2))
        self.spine_name_var = tk.StringVar(value=self.current_spine_name)
        spine_entry = ttk.Entry(control_frame, textvariable=self.spine_name_var, width=15)
        spine_entry.pack(side='left', padx=2)
        spine_entry.bind('<Return>', self.change_spine_name)
        
        ttk.Button(control_frame, text="New Spine", command=self.new_spine).pack(side='left', padx=2)
        ttk.Button(control_frame, text="Delete Current Box", command=self.delete_current_box).pack(side='left', padx=2)
        
        # dropdown for spine selection?
        ttk.Label(control_frame, text="Select:").pack(side='left', padx=(10,2))
        self.spine_dropdown = ttk.Combobox(control_frame, width=12, state='readonly')
        self.spine_dropdown.pack(side='left', padx=2)
        self.spine_dropdown.bind('<<ComboboxSelected>>', self.on_spine_selected)
        
        # navigation 
        nav_frame = ttk.Frame(main_frame)
        nav_frame.pack(fill='x', pady=(0, 5))
        
        ttk.Button(nav_frame, text="< Previous", command=self.prev_image).pack(side='left', padx=2)
        self.image_info_var = tk.StringVar(value="No images loaded")
        ttk.Label(nav_frame, textvariable=self.image_info_var).pack(side='left', padx=10)
        ttk.Button(nav_frame, text="Next >", command=self.next_image).pack(side='left', padx=2)
        
        ttk.Separator(nav_frame, orient='vertical').pack(side='left', fill='y', padx=10)
        
        # zoom 
        ttk.Button(nav_frame, text="Zoom In", command=self.zoom_in).pack(side='left', padx=2)
        ttk.Button(nav_frame, text="Zoom Out", command=self.zoom_out).pack(side='left', padx=2)
        ttk.Button(nav_frame, text="Reset View", command=self.reset_view).pack(side='left', padx=2)
        self.zoom_var = tk.StringVar(value="100%")
        ttk.Label(nav_frame, textvariable=self.zoom_var).pack(side='left', padx=5)
        
        # scrollbars
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill='both', expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, bg='white', cursor='crosshair')
        
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient='vertical', command=self.canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient='horizontal', command=self.canvas.xview)
        
        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')
        self.canvas.pack(side='left', fill='both', expand=True)
        
        # bind canvas events
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        self.canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_canvas_release)
        
        # status bar
        self.status_var = tk.StringVar(value="Load images to begin annotation")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief='sunken')
        status_bar.pack(fill='x', pady=(5, 0))
   
    # load and normalize tif files from a folder for display
    def load_images(self):
        folder_path = filedialog.askdirectory(title="Select folder containing images")
        if not folder_path:
            return
            
        extensions = ('.tif', '.tiff')
        
        image_files = []
        for file in os.listdir(folder_path):
            if file.lower().endswith(extensions):
                image_files.append(os.path.join(folder_path, file))
        
        image_files.sort()
        
        # load images
        self.images = []
        self.image_paths = []
        
        for img_path in image_files:
            img_array = tifffile.imread(img_path)         
            while img_array.ndim > 2:
                img_array = img_array[0]
            
            # normalize to 8-bit for display
            if img_array.dtype != np.uint8:
                img_min, img_max = img_array.min(), img_array.max()
                if img_max > img_min:
                    img_array = ((img_array - img_min) / (img_max - img_min) * 255).astype(np.uint8)
                else:
                    img_array = np.zeros_like(img_array, dtype=np.uint8)
            
            # convert to PIL Image, RGB
            img = Image.fromarray(img_array, mode='L').convert('RGB')
            
            self.images.append(img)
            self.image_paths.append(img_path)
            print(f"Successfully loaded: {os.path.basename(img_path)}, size={img.size}")
            
        self.current_image_idx = 0
        self.update_display()
        self.status_var.set(f"Loaded {len(self.images)} images")

    # redraw canvas with current image, all spine annotations, and maintain current zoom/pan settings
    def update_display(self):
        if not self.images:
            return
            
        self.image_info_var.set(f"Image {self.current_image_idx + 1} of {len(self.images)}")
        img = self.images[self.current_image_idx].copy()
        draw = ImageDraw.Draw(img)
        
        # draw all previous spine annotations
        for spine_name, annotations in self.spine_annotations.items():
            if self.current_image_idx in annotations:
                x1, y1, x2, y2 = annotations[self.current_image_idx]
                color = self.spine_colors.get(spine_name, 'gray')
                draw.rectangle([x1, y1, x2, y2], outline=color, width=1)
                draw.text((x1, y1-15), spine_name, fill=color)
        
        # update spine dropdown with all existing spines
        self.update_spine_dropdown()

        # zoom
        if self.zoom_factor != 1.0:
            new_size = (int(img.width * self.zoom_factor), int(img.height * self.zoom_factor))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        self.photo_image = ImageTk.PhotoImage(img)
        
        self.canvas.delete("all")
        self.canvas.create_image(self.pan_x, self.pan_y, anchor='nw', image=self.photo_image)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        # update zoom display to save prev zoom
        self.zoom_var.set(f"{int(self.zoom_factor * 100)}%")
        
    # record starting point of bounding box
    def on_canvas_click(self, event):
        if not self.images:
            return
            
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        img_x = int((canvas_x - self.pan_x) / self.zoom_factor)
        img_y = int((canvas_y - self.pan_y) / self.zoom_factor)
        
        self.drawing = True
        self.start_x = img_x
        self.start_y = img_y
        
    # draw temp rectangle 
    def on_canvas_drag(self, event):
        if not self.drawing or not self.images:
            return
            
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        img_x = int((canvas_x - self.pan_x) / self.zoom_factor)
        img_y = int((canvas_y - self.pan_y) / self.zoom_factor)
        
        if self.current_box:
            self.canvas.delete(self.current_box)
        
        x1 = self.pan_x + self.start_x * self.zoom_factor
        y1 = self.pan_y + self.start_y * self.zoom_factor
        x2 = self.pan_x + img_x * self.zoom_factor
        y2 = self.pan_y + img_y * self.zoom_factor
        
        current_color = self.spine_colors.get(self.current_spine_name, 'red')
        self.current_box = self.canvas.create_rectangle(x1, y1, x2, y2, outline=current_color, width=2)
        
    # save box upon release
    def on_canvas_release(self, event):
        if not self.drawing or not self.images:
            return
            
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        img_x = int((canvas_x - self.pan_x) / self.zoom_factor)
        img_y = int((canvas_y - self.pan_y) / self.zoom_factor)
        
        self.save_annotation(self.start_x, self.start_y, img_x, img_y)

        self.drawing = False
        self.current_box = None
   
    # save bounding box coordinates, calculate diagonal (pixels/microns), store data
    def save_annotation(self, x1, y1, x2, y2):
        # coordinates
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        
        img_w, img_h = self.images[self.current_image_idx].size
        
        x1 = max(0, min(x1, img_w))
        x2 = max(0, min(x2, img_w))
        y1 = max(0, min(y1, img_h))
        y2 = max(0, min(y2, img_h))
        
        # save annotation
        if self.current_spine_name not in self.spine_annotations:
            self.spine_annotations[self.current_spine_name] = {}
            # color for new spine
            if self.current_spine_name not in self.spine_colors:
                self.spine_colors[self.current_spine_name] = self.available_colors[self.color_index % len(self.available_colors)]
                self.color_index += 1
        
        self.spine_annotations[self.current_spine_name][self.current_image_idx] = (x1, y1, x2, y2)
        
        # calculate measurements
        diagonal_pixels = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        diagonal_microns = diagonal_pixels * self.pixel_to_micron
        is_stable = diagonal_pixels < self.stability_threshold
        
        # update data
        row_data = {
            'spine_name': self.current_spine_name,
            'image_idx': self.current_image_idx,
            'length_pixels': diagonal_pixels,
            'length_microns': diagonal_microns,
            'stable': is_stable
        }
        
        # remove any existing measurement for this spine/image combo
        mask = (self.measurements_df['spine_name'] == self.current_spine_name) & \
               (self.measurements_df['image_idx'] == self.current_image_idx)
        self.measurements_df = self.measurements_df[~mask]
        
        # overrite w new measurement
        self.measurements_df = pd.concat([self.measurements_df, pd.DataFrame([row_data])], ignore_index=True)
        
        self.update_display()
        self.status_var.set(f"Saved: {self.current_spine_name} - {diagonal_pixels:.1f} pixels, {diagonal_microns:.2f} μm")
        
    # update current spine name 
    def change_spine_name(self, event=None):
        new_name = self.spine_name_var.get().strip()
        if new_name and new_name != self.current_spine_name:
            self.current_spine_name = new_name
            self.update_display()

    # select spine from dropdown
    def on_spine_selected(self, event=None):
        selected_spine = self.spine_dropdown.get()
        if selected_spine:
            self.current_spine_name = selected_spine
            self.spine_name_var.set(selected_spine)
            self.update_display()
            
            # ehich images have this spine
            annotated_images = list(self.spine_annotations[selected_spine].keys())
            if annotated_images:
                self.status_var.set(f"Selected {selected_spine} annotated on images: {sorted(annotated_images)}")
            else:
                self.status_var.set(f"Selected {selected_spine} no annotations yet")
    
    # update dropdown with all existing spines
    def update_spine_dropdown(self):
        spine_names = sorted(self.spine_annotations.keys())
        self.spine_dropdown['values'] = spine_names
        if self.current_spine_name in spine_names:
            self.spine_dropdown.set(self.current_spine_name)
        else:
            self.spine_dropdown.set('')

    # switch to annotating new spine + new color
    def new_spine(self):
        spine_name = simpledialog.askstring("New Spine", "Enter spine name:", initialvalue=f"spine_{len(self.spine_colors) + 1}")
        if spine_name:
            self.current_spine_name = spine_name
            self.spine_name_var.set(spine_name)
            self.update_display()
            
    # delete annotation of current annotation from canvas + data
    def delete_current_box(self):
        if self.current_spine_name in self.spine_annotations and self.current_image_idx in self.spine_annotations[self.current_spine_name]:
            del self.spine_annotations[self.current_spine_name][self.current_image_idx]
            
            # remove from data
            mask = (self.measurements_df['spine_name'] == self.current_spine_name) & \
                   (self.measurements_df['image_idx'] == self.current_image_idx)
            self.measurements_df = self.measurements_df[~mask]
            
            self.update_display()
            self.status_var.set(f"Deleted annotation for {self.current_spine_name} on current image")
            
    # decrease image idx (maintain zoom+pan)
    def prev_image(self):
        if self.images and self.current_image_idx > 0:
            self.current_image_idx -= 1
            self.update_display()
    
    # increase image idx 
    def next_image(self):
        if self.images and self.current_image_idx < len(self.images) - 1:
            self.current_image_idx += 1
            self.update_display()

    # zoom factor increase (max 10x, 20% each time)      
    def zoom_in(self):
        self.zoom_factor = min(self.zoom_factor * 1.2, 10.0)
        self.update_display()
    
    # zoom factor decrease (min 0.1x)
    def zoom_out(self):
        self.zoom_factor = max(self.zoom_factor / 1.2, 0.1)
        self.update_display()
    
    # reset zoom = 100%, pan = (0,0)
    def reset_view(self):
        self.zoom_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.update_display()
        
    # save measurements to CSV file
    def save_data(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save measurements"
        )
        
        if filename:
            self.measurements_df.to_csv(filename, index=False)
            messagebox.showinfo("Success", f"Measurements saved to {filename}")
            
    # load and save annotations (json)
    def save_annotations(self):
        import json
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save annotations"
        )
        
        if filename:
            data = {
                'spine_annotations': {spine: {str(k): v for k, v in annots.items()} 
                                     for spine, annots in self.spine_annotations.items()},
                'spine_colors': self.spine_colors,
                'color_index': self.color_index,
                'image_paths': self.image_paths
            }
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Success", f"Annotations saved to {filename}")
    
    def load_annotations(self):
        import json
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load annotations"
        )
        
        if filename:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            self.spine_annotations = {spine: {int(k): tuple(v) for k, v in annots.items()} 
                                     for spine, annots in data['spine_annotations'].items()}
            self.spine_colors = data['spine_colors']
            self.color_index = data['color_index']
            
            saved_paths = data.get('image_paths', [])
            if saved_paths and saved_paths != self.image_paths:
                    return
            
            self.measurements_df = pd.DataFrame(columns=['spine_name', 'image_idx', 'length_pixels', 'length_microns', 'stable'])
            for spine_name, annotations in self.spine_annotations.items():
                for image_idx, (x1, y1, x2, y2) in annotations.items():
                    line_length_pixels = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                    line_length_microns = line_length_pixels * self.pixel_to_micron
                    is_stable = line_length_pixels < self.stability_threshold
                    row_data = {
                        'spine_name': spine_name,
                        'image_idx': image_idx,
                        'length_pixels': line_length_pixels,
                        'length_microns': line_length_microns,
                        'stable': is_stable
                    }
                    self.measurements_df = pd.concat([self.measurements_df, pd.DataFrame([row_data])], ignore_index=True)
            
            self.update_display()
            messagebox.showinfo("Success", f"Annotations loaded from {filename}")
            
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = SpineAnnotationTool()
    app.run()