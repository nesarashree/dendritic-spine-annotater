import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont
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

try:
    from pystackreg import StackReg
    STACKREG_AVAILABLE = True
except ImportError:
    STACKREG_AVAILABLE = False
    print("run in terminal: pip install pystackreg")

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
        self.registration_applied = False  # track if registration was applied

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
        
        # Box editing state
        self.editing_mode = False
        self.editing_spine = None
        self.editing_corner = None  # which corner/edge is being dragged
        self.edit_handle_size = 6  # size of corner handles in pixels
        
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
        ttk.Button(control_frame, text="Register Images", command=self.register_images).pack(side='left', padx=2)
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
        self.canvas.bind('<Motion>', self.on_canvas_motion)
        
        # status bar
        self.status_var = tk.StringVar(value="Load images to begin annotation")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief='sunken')
        status_bar.pack(fill='x', pady=(5, 0))
   
    # load 16-bit tif files from a folder (preserve pixel fidelity)
    def load_images(self):
        folder_path = filedialog.askdirectory(title="Select folder containing images")
        if not folder_path:
            return

        extensions = ('.tif', '.tiff')
        image_files = [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if f.lower().endswith(extensions)
        ]
        image_files.sort()

        self.images = []
        self.image_paths = []

        for img_path in image_files:
            # load 16-bit TIFF image using tifffile
            img_array = tifffile.imread(img_path)

            # if multi-channel or z-stack, take first frame
            while img_array.ndim > 2:
                img_array = img_array[0]

            # ensure correct dtype
            img_array = img_array.astype(np.uint16)

            self.images.append(img_array)
            self.image_paths.append(img_path)

            print(f"Loaded: {os.path.basename(img_path)}, shape={img_array.shape}, dtype={img_array.dtype}")

        # reset to first image
        self.current_image_idx = 0
        self.registration_applied = False  # reset registration flag

        # reset global normalization (for consistent display)
        self.global_minmax = None

        # update the canvas
        self.update_display()
        self.status_var.set(f"Loaded {len(self.images)} images, click Register Images to align stack")

    # stackreg image registration (rigid body) to combat drift/misalignment across images
    def register_images(self):
        try:
            self.status_var.set("registering images")
            self.root.update()
        
            # init stackreg with RIGID_BODY transformation
            sr = StackReg(StackReg.RIGID_BODY)

            # first image to reference (grayscale numpy array)
            reference = np.array(self.images[0].convert('L'))
            registered_images = [self.images[0]]  # Keep first image as-is
            
            for i in range(1, len(self.images)):
                moving = np.array(self.images[i].convert('L'))
                # create/apply transformation matrix
                tmats = sr.register(reference, moving)
                img_array = np.array(self.images[i])
                
                registered_array = np.zeros_like(img_array)
                for c in range(img_array.shape[2]):
                    registered_array[:,:,c] = sr.transform(img_array[:,:,c], tmats)
                
                # convert back to PIL
                registered_img = Image.fromarray(registered_array.astype(np.uint8))
                registered_images.append(registered_img)
                print(f"Registered image {i+1}/{len(self.images)}")
            
            # replace images w registered versions
            self.images = registered_images
            self.registration_applied = True
            
            self.update_display()
            messagebox.showinfo("success", "successfully registered")
            
        except Exception as e:
            messagebox.showerror("error", f"registration failed: {str(e)}")
            self.status_var.set("registration failed")

    # redraw canvas with current image, all spine annotations, and maintain current zoom/pan settings
    def update_display(self):
        if not self.images:
            return

        self.image_info_var.set(f"Image {self.current_image_idx + 1} of {len(self.images)}")

        # Get the 16-bit image array for the current frame
        img_array = self.images[self.current_image_idx]

        # Compute global normalization from all images (once)
        if not hasattr(self, 'global_minmax') or self.global_minmax is None:
            all_vals = np.concatenate([im.ravel() for im in self.images])
            self.global_minmax = (np.percentile(all_vals, 0.1), np.percentile(all_vals, 99.9))

        vmin, vmax = self.global_minmax

        # Normalize this frame for display (still grayscale)
        disp = np.clip((img_array - vmin) / (vmax - vmin), 0, 1)
        disp = (disp * 255).astype(np.uint8)

        # Convert to RGB for colored annotations
        img = Image.fromarray(disp, mode='L').convert('RGB')
        draw = ImageDraw.Draw(img)

        # Draw all spine annotations (in color)
        for spine_name, annotations in self.spine_annotations.items():
            if self.current_image_idx in annotations:
                x1, y1, x2, y2 = annotations[self.current_image_idx]
                color = self.spine_colors.get(spine_name, 'gray')
                
                # Keep line width consistent at 1
                draw.rectangle([x1, y1, x2, y2], outline=color, width=1)
                draw.line([x1, y1, x2, y2], fill=color, width=1)  # diagonal

                # text label
                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 8)
                except:
                    font = ImageFont.load_default()
                display_text = spine_name.split('_')[-1] if '_' in spine_name else spine_name
                draw.text((x1, y1 - 12), display_text, fill=color, font=font)

        # Update spine dropdown (preserves UI state)
        self.update_spine_dropdown()

        # Apply zoom using nearest-neighbor (pixel-accurate)
        if self.zoom_factor != 1.0:
            new_size = (int(img.width * self.zoom_factor), int(img.height * self.zoom_factor))
            img = img.resize(new_size, Image.Resampling.NEAREST)

        # Convert to PhotoImage for display
        self.photo_image = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(self.pan_x, self.pan_y, anchor='nw', image=self.photo_image)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        # Update zoom indicator
        self.zoom_var.set(f"{int(self.zoom_factor * 100)}%")

    def canvas_to_image_coords(self, canvas_x, canvas_y):
        """Convert canvas coordinates to image coordinates"""
        img_x = int((canvas_x - self.pan_x) / self.zoom_factor)
        img_y = int((canvas_y - self.pan_y) / self.zoom_factor)
        return img_x, img_y
    
    def image_to_canvas_coords(self, img_x, img_y):
        """Convert image coordinates to canvas coordinates"""
        canvas_x = self.pan_x + img_x * self.zoom_factor
        canvas_y = self.pan_y + img_y * self.zoom_factor
        return canvas_x, canvas_y
    
    def find_corner_at_point(self, img_x, img_y, tolerance=None):
        """Find which corner/edge of current spine's box is near the point"""
        if not self.images:
            return None, None
            
        if tolerance is None:
            tolerance = max(8 / self.zoom_factor, 3)  # Scale with zoom
            
        # Check current spine's box on current image
        if self.current_spine_name in self.spine_annotations:
            if self.current_image_idx in self.spine_annotations[self.current_spine_name]:
                x1, y1, x2, y2 = self.spine_annotations[self.current_spine_name][self.current_image_idx]
                
                # Check corners first (priority)
                corners = {
                    'tl': (x1, y1),
                    'tr': (x2, y1),
                    'bl': (x1, y2),
                    'br': (x2, y2)
                }
                
                for corner_name, (cx, cy) in corners.items():
                    if abs(img_x - cx) <= tolerance and abs(img_y - cy) <= tolerance:
                        return self.current_spine_name, corner_name
                
                # Check edges (move entire box)
                if (x1 <= img_x <= x2 and y1 <= img_y <= y2):
                    return self.current_spine_name, 'move'
        
        return None, None

    def on_canvas_motion(self, event):
        """Update cursor based on what's under the mouse"""
        if not self.images or self.drawing:
            return
            
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        img_x, img_y = self.canvas_to_image_coords(canvas_x, canvas_y)
        
        spine_name, corner = self.find_corner_at_point(img_x, img_y)
        
        if corner:
            if corner in ['tl', 'br']:
                self.canvas.config(cursor='size_nw_se')
            elif corner in ['tr', 'bl']:
                self.canvas.config(cursor='size_ne_sw')
            elif corner == 'move':
                self.canvas.config(cursor='fleur')
        else:
            self.canvas.config(cursor='crosshair')

    # record starting point of bounding box or begin editing
    def on_canvas_click(self, event):
        if not self.images:
            return
            
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        img_x, img_y = self.canvas_to_image_coords(canvas_x, canvas_y)
        
        # Check if clicking on an existing box corner/edge
        spine_name, corner = self.find_corner_at_point(img_x, img_y)
        
        if spine_name and corner:
            # Start editing mode
            self.editing_mode = True
            self.editing_spine = spine_name
            self.editing_corner = corner
            self.start_x = img_x
            self.start_y = img_y
            
            # Store original box coordinates
            self.original_box = self.spine_annotations[spine_name][self.current_image_idx]
        else:
            # Start drawing new box
            self.drawing = True
            self.start_x = img_x
            self.start_y = img_y
        
    # draw temp rectangle or edit existing box
    def on_canvas_drag(self, event):
        if not self.images:
            return
            
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        img_x, img_y = self.canvas_to_image_coords(canvas_x, canvas_y)
        
        if self.editing_mode:
            # Edit existing box
            x1, y1, x2, y2 = self.original_box
            dx = img_x - self.start_x
            dy = img_y - self.start_y
            
            if self.editing_corner == 'tl':
                x1 += dx
                y1 += dy
            elif self.editing_corner == 'tr':
                x2 += dx
                y1 += dy
            elif self.editing_corner == 'bl':
                x1 += dx
                y2 += dy
            elif self.editing_corner == 'br':
                x2 += dx
                y2 += dy
            elif self.editing_corner == 'move':
                x1 += dx
                y1 += dy
                x2 += dx
                y2 += dy
            
            # Update the annotation temporarily
            self.spine_annotations[self.editing_spine][self.current_image_idx] = (x1, y1, x2, y2)
            self.update_display()
            
        elif self.drawing:
            # Draw new box
            if self.current_box:
                self.canvas.delete(self.current_box)
            
            x1, y1 = self.image_to_canvas_coords(self.start_x, self.start_y)
            x2, y2 = self.image_to_canvas_coords(img_x, img_y)
            
            current_color = self.spine_colors.get(self.current_spine_name, 'red')
            self.current_box = self.canvas.create_rectangle(x1, y1, x2, y2, outline=current_color, width=2)
        
    # save box upon release
    def on_canvas_release(self, event):
        if not self.images:
            return
            
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        img_x, img_y = self.canvas_to_image_coords(canvas_x, canvas_y)
        
        if self.editing_mode:
            # Finalize edit
            x1, y1, x2, y2 = self.spine_annotations[self.editing_spine][self.current_image_idx]
            
            # Ensure proper ordering
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            
            # Update annotation with final coordinates
            self.spine_annotations[self.editing_spine][self.current_image_idx] = (x1, y1, x2, y2)
            
            # Recalculate measurements
            diagonal_pixels = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            diagonal_microns = diagonal_pixels * self.pixel_to_micron
            is_stable = diagonal_pixels < self.stability_threshold
            
            # Update measurements dataframe
            mask = (self.measurements_df['spine_name'] == self.editing_spine) & \
                   (self.measurements_df['image_idx'] == self.current_image_idx)
            self.measurements_df = self.measurements_df[~mask]
            
            row_data = {
                'spine_name': self.editing_spine,
                'image_idx': self.current_image_idx,
                'length_pixels': diagonal_pixels,
                'length_microns': diagonal_microns,
                'stable': is_stable
            }
            self.measurements_df = pd.concat([self.measurements_df, pd.DataFrame([row_data])], ignore_index=True)
            
            self.editing_mode = False
            self.editing_spine = None
            self.editing_corner = None
            self.status_var.set(f"Updated: {self.editing_spine} - {diagonal_pixels:.1f} pixels, {diagonal_microns:.2f} μm")
            
        elif self.drawing:
            # Save new box
            self.save_annotation(self.start_x, self.start_y, img_x, img_y)
            self.drawing = False
            self.current_box = None
        
        self.update_display()
   
    # save bounding box coordinates, calculate diagonal (pixels/microns), store data
    def save_annotation(self, x1, y1, x2, y2):
        # coordinates
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        
        img_w, img_h = self.images[self.current_image_idx].shape[1], self.images[self.current_image_idx].shape[0]
        
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

    # select spine from dropdwon
    def on_spine_selected(self, event=None):
        selected_spine = self.spine_dropdown.get()
        if selected_spine:
            self.current_spine_name = selected_spine
            self.spine_name_var.set(selected_spine)
            self.update_display()
    
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
            
    # load and save annotations (json extensions)
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