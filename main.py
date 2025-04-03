#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SGDET-Annotate Tool
@author: Minh Huy Pham <minhhuypham.working@gmail.com>

This script implements an image annotation tool UI with the following components:

     Component 1: Image view (Canvas) with a fixed black background and
                  an active image area (zoomed along its longest side).

     Component 2: "Import Label List" button, import a text file as list of labels.
     Component 3: Imported label list view (Listbox).
     Component 4: "Import Attribute List" button, import a text file as list of attributes.
     Component 5: Imported attribute list view (Listbox).
     Component 6: "Import Relationship List" button, import a text file as list of relationships.
     Component 7: Imported relationship list view (Listbox).

     Component 8: "Open" button to load an image.
     Component 9: "Save" button (stub for future saving functionality).
     Component 10: "Create Bounding Box" button. When active, the user can draw a box
                  on the image view. After drawing, the box flashes until a label is assigned.
     Component 11: Labeled view (Listbox) displays confirmed bounding boxes as "label:id".
     Component 12: Attribute view (Listbox) displays assigned attributes of selected box.
     Component 13: Relationship view (Listbox) display relationships of all boxes or selected box only.
     
"""

# Dependencies:
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageOps
from typing import Optional, List, Tuple
import json
import os
import numpy as np
import h5py
class AnnotationTool:
     """
     Main application class for the Annotation Tool.
     Sets up the Tkinter UI elements and implements all behaviors.
     """

     def __init__(self, master):
          """
          Initialize the main window, layout, and bind events.
          :param master: The root Tkinter window.
          """
          self.master = master
          self.master.title("SGDET-Annotate")

          # Set initial window size and disable resizing
          self.master.geometry("1600x900")
          self.master.resizable(False, False)

          # ---------------------------
          # Instance Variables
          # ---------------------------
          self.loaded_image = None    # PIL Image
          self.image_tk = None        # Tkinter image
          self.image_area = None      # (x, y, width, height) of displayed image within canvas (Component 1)

          # For handling create new bounding box with label
          self.create_bbox_active = False  # True when "Create Bounding Box" is active
          self.handling_new_bbox = False
          self.start_x = None  # Starting x coordinate for new bbox (in canvas coords)
          self.start_y = None  # Starting y coordinate for new bbox (in canvas coords)
          self.temp_rect = None  # Canvas item id for the temporary bbox while dragging

          # For handling pending (unlabeled) and confirmed bounding boxes.
          # pending_bbox: dict with keys 'rect_id', 'coords', and 'flash_state'
          self.pending_bbox = None
          self.confirmed_bboxes = []
          self.label_counts = {}  # For auto-incrementing IDs per label
          self.selected_bbox = None  # Currently selected confirmed bbox (dict)

          # For handling change label:
          self.change_label_mode: bool = False
          self.change_bbox = None
          self.change_old_label = None

          # For handling attribute creation:
          self.attribute_add_mode: bool = False # True when in attribute-adding mode
          
          # For handing relationship creation:
          self.relationship_mode: bool = False  # True when in relationship-adding mode
          self.source_bbox: Optional[dict] = None  # The currently selected (source) bbox
          self.pending_relationship: str = ""       # Relationship string chosen from Component 7
          self.relationships: List[Tuple[str, str, str]] = []  # List to store relationships

          # --------------------
          # Layout Setup
          # --------------------
          # The main window is divided into:
          #  - Left: Image view (Component 1)
          #  - Right: Import panels (Component 8-13)
          #  - Bottom: Control buttons and assigned annotation views (Components 2-7)

          # Configure grid for root window: two columns (left: image; right: import lists), 
          # and a bottom panel spanning both columns.
          self.master.grid_rowconfigure(0, weight=1)
          self.master.grid_columnconfigure(0, minsize=1200)
          self.master.grid_columnconfigure(1, minsize=400)

          # ------------
          # Component 1: Image View (Canvas)
          # ------------
          self.image_frame = tk.Frame(self.master, bd=2, relief=tk.SUNKEN)
          self.image_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
          
          # Canvas with black background
          self.canvas = tk.Canvas(self.image_frame, bg="black")
          self.canvas.pack(expand=True, fill=tk.BOTH)
          
          # Bind mouse events for both drawing and selection:
          self.canvas.bind("<Button-1>", self.on_canvas_click)

          # For drawing new bounding boxes (only if create_bbox_active)
          self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
          self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

          # For Opening Context menu to interact with created bounding box:
          self.canvas.bind("<Button-3>", self.show_context_menu)
          self.canvas.bind("<Button-2>", self.show_context_menu)

          # ---------------------------
          # Right Panel (Import Lists)
          # Contains Components 2-7.
          # ---------------------------
          self.right_panel = tk.Frame(self.master, bd=2, relief=tk.GROOVE)
          self.right_panel.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
          self.right_panel.grid_columnconfigure(0, weight=1)

          # Component 2: "Import Label List" button
          self.import_label_button = tk.Button(
               self.right_panel,
               text="Import Label List",
               command=self.import_label_list
          )
          self.import_label_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

          self.label_list_frame = tk.Frame(self.right_panel)

          # Component 3: Imported label list view
          self.label_list_frame = tk.Frame(self.right_panel)
          self.label_list_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
          self.label_scrollbar = tk.Scrollbar(self.label_list_frame, orient=tk.VERTICAL)
          self.label_listbox = tk.Listbox(
               self.label_list_frame,
               yscrollcommand=self.label_scrollbar.set
          )
          self.label_scrollbar.config(command=self.label_listbox.yview)
          self.label_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
          self.label_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
          
          # Bind double-click to trigger label assignment for pending bbox
          self.label_listbox.bind("<Double-Button-1>", self.on_label_select)

          # Component 4: "Import Attribute List" button
          self.import_attr_button = tk.Button(
               self.right_panel,
               text="Import Attribute List",
               command=self.import_attribute_list
          )
          self.import_attr_button.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

          # Component 5: Imported attribute list view
          self.attr_list_frame = tk.Frame(self.right_panel)
          self.attr_list_frame.grid(row=3, column=0, padx=5, pady=5, sticky="nsew")
          self.attr_scrollbar = tk.Scrollbar(self.attr_list_frame, orient=tk.VERTICAL)
          self.attr_listbox = tk.Listbox(self.attr_list_frame, yscrollcommand=self.attr_scrollbar.set)
          self.attr_scrollbar.config(command=self.attr_listbox.yview)
          self.attr_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
          self.attr_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
          self.attr_listbox.bind("<Double-Button-1>", self.on_attr_double_click)

          # Component 6: "Import Relationship List" button
          self.import_rel_button = tk.Button(
               self.right_panel,
               text="Import Relationship List",
               command=self.import_relationship_list
          )
          self.import_rel_button.grid(row=4, column=0, padx=5, pady=5, sticky="ew")

          # Components 7: Imported relationship list view
          self.rel_list_frame = tk.Frame(self.right_panel)
          self.rel_list_frame.grid(row=5, column=0, padx=5, pady=5, sticky="nsew")
          self.rel_scrollbar = tk.Scrollbar(self.rel_list_frame, orient=tk.VERTICAL)
          self.rel_listbox = tk.Listbox(self.rel_list_frame, yscrollcommand=self.rel_scrollbar.set)
          self.rel_listbox.bind("<Double-Button-1>", self.on_relationship_selected)
          self.rel_scrollbar.config(command=self.rel_listbox.yview)
          self.rel_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
          self.rel_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

          # Make right_panel rows expandable where needed
          self.right_panel.grid_rowconfigure(1, weight=1)
          self.right_panel.grid_rowconfigure(3, weight=1)
          self.right_panel.grid_rowconfigure(5, weight=1)

          # ---------------------------
          # Bottom Panel (Control & Annotation Views)
          # Contains components 8, 9, 10, 11, 12, 13.
          # Layout:
          #   Row 0: Components 8 ("Open") and Components 9 ("Save")
          #   Row 1: Components 10 ("Create Bounding Box"), Components 11 (Labeled view),
          #          Components 12 (Attribute view), Components 13 (Relationship view)
          # ---------------------------
          self.bottom_panel = tk.Frame(self.master, bd=2, relief=tk.GROOVE)
          self.bottom_panel.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

          # Row 0: Open and Save buttons
          # Components 8: "Open" button
          self.open_button = tk.Button(
               self.bottom_panel,
               text="Open",
               command=self.open_image
          )
          self.open_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
          
          # Components 9: "Save" button
          self.save_button = tk.Button(
               self.bottom_panel,
               text="Save",
               command=self.save_data,  # Same fixed width as Open
          )
          self.save_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

          # Row 1: Annotation views and control buttons.
          # Component 10: "Create Bounding Box" button.
          self.create_bbox_button = tk.Button(
               self.bottom_panel,
               text="Create Bounding Box",
               command=self.toggle_create_bbox
          )
          self.create_bbox_button.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

          # Components 11: Labeled view (shows confirmed boxes as "label:id")
          self.labeled_frame = tk.Frame(self.bottom_panel, bd=1, relief=tk.SUNKEN)
          self.labeled_frame.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")
          self.labeled_scrollbar = tk.Scrollbar(self.labeled_frame, orient=tk.VERTICAL)
          self.labeled_listbox = tk.Listbox(self.labeled_frame, yscrollcommand=self.labeled_scrollbar.set)
          self.labeled_scrollbar.config(command=self.labeled_listbox.yview)
          self.labeled_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
          self.labeled_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
          
          # Bind selection from components 11 to select/deselect corresponding bbox
          self.labeled_listbox.bind("<<ListboxSelect>>", self.on_labeled_select)

          # Component 12: Attribute view
          self.attribute_view_frame = tk.Frame(self.bottom_panel, bd=1, relief=tk.SUNKEN)
          self.attribute_view_frame.grid(row=1, column=2, padx=5, pady=5, sticky="nsew")
          self.attribute_view_scroll = tk.Scrollbar(self.attribute_view_frame, orient=tk.VERTICAL)
          self.attribute_view_listbox = tk.Listbox(
               self.attribute_view_frame, yscrollcommand=self.attribute_view_scroll.set
          )
          self.attribute_view_scroll.config(command=self.attribute_view_listbox.yview)
          self.attribute_view_scroll.pack(side=tk.RIGHT, fill=tk.Y)
          self.attribute_view_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
          
          # Bind right‐click on the attribute view for removing attributes
          self.attribute_view_listbox.bind("<Button-3>", self.show_attribute_context_menu)
          self.attribute_view_listbox.bind("<Button-2>", self.show_attribute_context_menu)

          # Components 13: Relationship view
          self.relationship_view_frame = tk.Frame(self.bottom_panel, bd=1, relief=tk.SUNKEN)
          self.relationship_view_frame.grid(row=1, column=3, padx=5, pady=5, sticky="nsew")
          self.relationship_view_scroll = tk.Scrollbar(self.relationship_view_frame, orient=tk.VERTICAL)
          self.relationship_view_listbox = tk.Listbox(
               self.relationship_view_frame, yscrollcommand=self.relationship_view_scroll.set
          )
          self.relationship_view_scroll.config(command=self.relationship_view_listbox.yview)
          self.relationship_view_scroll.pack(side=tk.RIGHT, fill=tk.Y)
          self.relationship_view_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
          
          # Bind right‐click on the relationship view for removing relationships
          self.relationship_view_listbox.bind("<Button-3>", self.show_relationship_context_menu)
          self.relationship_view_listbox.bind("<Button-2>", self.show_relationship_context_menu)

          # Configure grid weights in bottom_panel so row 1 expands equally.
          self.bottom_panel.grid_columnconfigure(0, weight=1)
          self.bottom_panel.grid_columnconfigure(1, weight=2)
          self.bottom_panel.grid_columnconfigure(2, weight=2)
          self.bottom_panel.grid_columnconfigure(3, weight=2)
          self.bottom_panel.grid_rowconfigure(1, weight=1)

          # Initializing Application
          # Checking if output folder is created? 
          self.output_dir = "output"
          if not os.path.exists(self.output_dir):
               os.makedirs(self.output_dir)

          # Auto load the labels, relationships or attributes if imported before:
          self._auto_load_imported_files()

     # ---------------------------------------
     # Mouse and Canvas Event Handlers
     # ---------------------------------------

     def on_canvas_click(self, event):
          """
          Handler for canvas (component 1 - image view) mouse click.
          If in 'create bbox' mode, this starts drawing if within active image area.
          Otherwise, it checks for selection of confirmed bounding boxes.
          """
          if self.create_bbox_active:
               
               # Check if click is inside the active image area.
               if self.image_area and self._inside_image_area(event.x, event.y) and not self.handling_new_bbox:
                    self.start_x = event.x
                    self.start_y = event.y
                    
                    # Create a temporary dashed rectangle.
                    self.temp_rect = self.canvas.create_rectangle(
                         self.start_x, self.start_y, self.start_x, self.start_y,
                         outline="red", dash=(5, 2), width=3
                    )
                    self.handling_new_bbox = True
               return

          # If not in drawing mode, check if a confirmed bbox was clicked
          clicked_bbox = self._get_confirmed_bbox_at(event.x, event.y)
          
          # If in attribute or relationship mode and the clicked bbox is the already selected one, then do nothing.
          if (self.attribute_add_mode or self.relationship_mode or self.change_label_mode) and (clicked_bbox == self.selected_bbox):
               return
          
          # Toggle selection for the clicked bbox.
          if clicked_bbox:
               if self.selected_bbox == None:
                    self._select_bbox(clicked_bbox)
               elif self.selected_bbox == clicked_bbox:
                    self._deselect_bbox(clicked_bbox)

          # In relationship mode, treat the click as target bbox selection.
          # If no relationship has been selected from Component 7, ignore the click.
          if self.relationship_mode:
               if not self.pending_relationship:
                    return
               
               # Treat this click as target relationship bbox selection.
               target_bbox = self._get_confirmed_second_bbox_relationship(event.x, event.y)
               if target_bbox is None:
                    messagebox.showwarning("Add Relationship", "Please click on a valid target bounding box.")
                    return
               if target_bbox == self.source_bbox:
                    messagebox.showwarning("Add Relationship", "Target bbox must be different from the source.")
                    return
               
               # Check if an identical relationship already exists.
               for rel in self.relationships:
                    if rel[0] == self.source_bbox and rel[1] == self.pending_relationship and rel[2] == target_bbox:
                         messagebox.showwarning("Add Relationship",
                                             "This relationship has already been created.")
                         # Cancel relationship creation.
                         self.relationship_mode = False
                         self.source_bbox = None
                         self.pending_relationship = ""
                         self.labeled_listbox.config(state="normal")
                         return

               # Get source and target for display relationship on UI
               source_str = f"{self.source_bbox['label_str']}:{self.source_bbox['id']}"
               target_str = f"{target_bbox['label_str']}:{target_bbox['id']}"
               
               # Convert the pending relationship string to its numeric id using the mapping.
               predicate = self.relationships_mapping.get(self.pending_relationship, 0)
               confirm = messagebox.askokcancel("Confirm Relationship",
                    f"Create relationship: {source_str} --- {self.pending_relationship} --- {target_str}?")
               if confirm:
                    # Store the relationship as a tuple of (source_bbox, relationship string, target_bbox)
                    self.relationships.append((self.source_bbox, self.pending_relationship, target_bbox))
                    if not hasattr(self, "predicates"):
                         self.predicates = []
                    self.predicates.append(predicate)
                    self.update_relationship_view()
               
               # Reset relationship mode regardless of confirmation.
               self.relationship_mode = False
               self.source_bbox = None
               self.pending_relationship = ""

               # Re-enable label view.
               self.labeled_listbox.config(state="normal")
               return

     def on_mouse_drag(self, event):
          """
          Now mouse drag event only working in creating bbox
          """
          if not self.create_bbox_active or self.temp_rect is None:
               return

          # Clamp the current coordinates to the image area boundaries
          if self.image_area:
               area_x, area_y, area_w, area_h = self.image_area
               clamped_x = min(max(event.x, area_x), area_x + area_w)
               clamped_y = min(max(event.y, area_y), area_y + area_h)
          else:
               clamped_x, clamped_y = event.x, event.y

          self.canvas.coords(self.temp_rect, self.start_x, self.start_y, clamped_x, clamped_y)

     def on_mouse_up(self, event):
          """
          Handler for mouse button release.
          Finalizes the bounding box (if in drawing mode and within active image area)
          and starts the flashing effect until a label is assigned.
          """
          if not self.create_bbox_active or self.temp_rect is None:
               return

          # Clamp the release coordinates to the boundaries of the image area.
          if self.image_area:
               area_x, area_y, area_w, area_h = self.image_area
               clamped_x = min(max(event.x, area_x), area_x + area_w)
               clamped_y = min(max(event.y, area_y), area_y + area_h)
          else:
               clamped_x, clamped_y = event.x, event.y


          # Final coordinates for the bounding box.
          # x1, y1, x2, y2 = self.start_x, self.start_y, event.x, event.y
          x1, y1, x2, y2 = self.start_x, self.start_y, clamped_x, clamped_y

          if abs(x2 - x1) < 10 or abs(y2 - y1) < 10:
               # Too small, discard
               self.canvas.delete(self.temp_rect)
               self.temp_rect = None
               self.handling_new_bbox = False
               return

          # Ensure coordinates are ordered.
          x1, x2 = sorted((x1, x2))
          y1, y2 = sorted((y1, y2))
          self.canvas.coords(self.temp_rect, x1, y1, x2, y2)

          # Set the newly created bounding box to a dashed style:
          self.canvas.itemconfig(self.temp_rect, dash=(5, 2), outline="red", width=3)

          # Store the pending bounding box (awaiting label assignment).
          self.pending_bbox = {
               'rect_id': self.temp_rect,
               'coords': (x1, y1, x2, y2)
          }
          
          # self.pending_bbox = {
          #      'rect_id': self.temp_rect,
          #      'coords': (x1, y1, x2, y2),
          #      'flash_state': True  # True means next flash will show dashed
          # }
          # Start flashing.
          # self.flash_pending_bbox()

          # Create draggable handles at the corners and midpoints.
          self.create_handles(self.pending_bbox)

          # Reset temporary rectangle (it is now managed by pending_bbox).
          self.temp_rect = None

     # ---------------------------------------
     # Image Loading and Scaling (Component 1)
     # ---------------------------------------
     def open_image(self):
          """
          Open an image file, scale and center it in the canvas according to the rules:
               - The image is zoomed in along its longest side to fit the canvas.
               - The remaining area is filled with black, and is inactive.
          """
          file_path = filedialog.askopenfilename(
               title="Open Image",
               filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif"), ("All Files", "*.*")]
          )
          if not file_path:
               return

          # Clear previous image's temporary and persistent data
          self.canvas.delete("all")
          self.confirmed_bboxes.clear()
          self.pending_bbox = None
          self.relationships.clear()
          if hasattr(self, "predicates"):
               self.predicates.clear()
          self.label_counts.clear()
          self.selected_bbox = None

          # Also reset state flags and temporary variables:
          self.create_bbox_active = False
          self.start_x = None
          self.start_y = None
          self.temp_rect = None
          self.handling_new_bbox = False
          self.change_label_mode = False
          self.change_bbox = None
          self.change_old_label = None
          self.attribute_add_mode = False
          self.relationship_mode = False
          self.loaded_image = None

          # Update the views
          self.update_attribute_view()
          self.update_labeled_view()
          self.update_relationship_view()

          # Get the image file path
          self.image_path = file_path

          try:
               pil_image = Image.open(file_path)
               pil_image = ImageOps.exif_transpose(pil_image)
               self.loaded_image = pil_image

               # Ensure layout is updated so can get canvas size.
               self.master.update_idletasks()
               canvas_w = self.canvas.winfo_width()
               canvas_h = self.canvas.winfo_height()

               # Determine scaling:
               # If image is landscape, scale width to canvas width.
               # If portrait, scale height to canvas height.
               # Always scale the image so that its height equals the canvas height.
               img_w, img_h = pil_image.size
          
               scale = min(canvas_w / img_w, canvas_h / img_h)
               new_w = int(img_w * scale)
               new_h = int(img_h * scale)

               x_offset = (canvas_w - new_w) // 2
               y_offset = (canvas_h - new_h) // 2

               resized_image = pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
               self.image_tk = ImageTk.PhotoImage(resized_image)

               # Clear canvas and draw image centered.
               self.canvas.delete("all")
               # Calculate top-left coordinates to center the image.
               self.image_area = (x_offset, y_offset, new_w, new_h)
               self.canvas.create_image(x_offset, y_offset, anchor=tk.NW, image=self.image_tk)

               # Reset confirmed bounding boxes and selections.
               self.confirmed_bboxes.clear()
               self.update_labeled_view()
               self.selected_bbox = None
          except Exception as e:
               messagebox.showerror("Open Image Error", str(e))

     def toggle_create_bbox(self):
          """
          Toggle the 'Create Bounding Box' mode on or off.
          When activated, change the button appearance and set the canvas cursor to a crosshair.
          When deactivated, revert the button and cursor to normal.
          """

          if self.selected_bbox is not None:
               return
          
          if self.label_listbox.size() == 0:
               messagebox.showwarning("Import Label List", "Please import label list before creating new bbox.")
               return
          
          self.create_bbox_active = not self.create_bbox_active
          if self.create_bbox_active:
               self.create_bbox_button.config(relief=tk.SUNKEN, bg="lightblue")
               self.canvas.config(cursor="crosshair")

               # Disable the label view (components 11) while in create bbox mode.
               self.labeled_listbox.unbind("<<ListboxSelect>>")

          else:
               self.create_bbox_button.config(relief=tk.RAISED, bg="SystemButtonFace")
               self.canvas.config(cursor="")

               # Re-enable the label view when create bbox mode is turned off.
               self.labeled_listbox.bind("<<ListboxSelect>>", self.on_labeled_select)

     # ---------------------------------------
     # Label Assignment and Confirmation
     # ---------------------------------------

     def flash_pending_bbox(self):
          """
          Toggle the flash state (dashed/solid) of the pending bounding box.
          Continues until a label is confirmed.
          """
          if not self.pending_bbox or "flash_state" not in self.pending_bbox:
               return

          rect_id = self.pending_bbox['rect_id']
          
          # Toggle flash state: if True, set to solid; if False, set to dashed.
          if self.pending_bbox['flash_state']:
               self.canvas.itemconfig(rect_id, dash="")
          else:
               self.canvas.itemconfig(rect_id, dash=(5, 2))
          
          # Flip the flash state.
          self.pending_bbox['flash_state'] = not self.pending_bbox['flash_state']

          # Schedule the next flash toggle in 500 ms.
          self.master.after(500, self.flash_pending_bbox)

     def on_label_select(self, event):
          """
          Handler for double-clicking an item in the imported label list (Components 3).
          If there is a pending bounding box, prompt the user to confirm
          assigning the selected label.
          """
          # Get the label from imported label list 
          selection = self.label_listbox.curselection()
          if not selection:
               return
          label = self.label_listbox.get(selection[0])

          # For changing label mode:
          if self.change_label_mode:
               if label == self.change_old_label:
                    messagebox.showwarning("Change Label", "The new label must be different from the old label.")
                    return
               if not messagebox.askokcancel("Confirm Change",
                                             f"Change label from {self.change_old_label} to {label}?"):
                    return
               
               # Determine new instance id for the new label.
               new_instance_id = self.label_counts.get(label, 0) + 1
               self.label_counts[label] = new_instance_id
               
               # Update the bbox data:
               self.change_bbox['label'] = self.labels_mapping.get(label, 0)
               self.change_bbox['id'] = new_instance_id
               self.change_bbox['label_str'] = label
               
               # Update the text label on canvas.
               self.canvas.itemconfig(self.change_bbox['text_id'], text=f"{label}:{new_instance_id}")
               
               # Also update all relationships that involve this bbox.
               for idx, rel in enumerate(self.relationships):
                    source_bbox, rel_str, target_bbox = rel
                    if source_bbox == self.change_bbox:
                         self.relationships[idx] = (self.change_bbox, rel_str, target_bbox)
                    if target_bbox == self.change_bbox:
                         self.relationships[idx] = (source_bbox, rel_str, self.change_bbox)
               
               # End change-label mode.
               self.update_relationship_view()
               self.canvas.itemconfig(self.change_bbox['rect_id'], dash="")
               self.change_label_mode = False
               self.change_bbox = None
               self.change_old_label = None
               self.labeled_listbox.config(state="normal")
               self.update_labeled_view()
          
          elif self.pending_bbox:
               # Normal pending bbox label assignment.
               self.confirm_label_assignment(label)

     def confirm_label_assignment(self, label):
          """
          Prompt the user to confirm the assignment of the given label to the pending bbox.
          If confirmed, the bounding box stops flashing, is assigned the label (and auto-generated id),
          and is added to the confirmed list (Components 3 is updated).
          :param label: The label selected by the user.
          """

          # Asking user to confirm the new label
          answer = messagebox.askokcancel("Confirm Label", f"Confirm label assignment is '{label}'?")
          if answer:
               # Stop flashing by clearing the pending bbox.
               pending = self.pending_bbox
               self.pending_bbox = None

               # Determine the new id for this label.
               current_instance_id = self.label_counts.get(label, 0) + 1
               self.label_counts[label] = current_instance_id

               # Update the bounding box (set solid outline and add a text tag).
               rect_id = pending['rect_id']
               self.canvas.itemconfig(rect_id, dash="", outline="red", width=3)

               # If handles exist, remove them
               if 'handles' in pending:
                    for handle in pending['handles'].values():
                         self.canvas.delete(handle)
                    del pending['handles']

               # Add a label tag above the bounding box.
               x1, y1, x2, y2 = pending['coords']
               numeric_label = self.labels_mapping.get(label, 0)
               tag_text = f"{label}:{current_instance_id}"
               
               # Create a text label above the box (centered horizontally).
               text_x = (x1 + x2) / 2
               text_y = y1 - 10  # 10 pixels above
               text_id = self.canvas.create_text(text_x, text_y, text=tag_text,
                                                  fill="yellow", font=("Arial", 12, "bold"))
               # Store the confirmed bbox data.
               confirmed = {
                    'rect_id': rect_id,
                    'coords': pending['coords'],
                    'label': numeric_label,      # numeric label (for saving)
                    'id': current_instance_id,     # instance count for this label (for display)
                    'label_str': label,            # original string label for display in UI
                    'text_id': text_id,
                    'selected': False,
                    'attributes': []               # list of attribute strings
               }

               self.confirmed_bboxes.append(confirmed)
               self.update_labeled_view()
               self.handling_new_bbox = False

     # ---------------------------------------
     # Selection/Deselection of Confirmed Bounding Boxes
     # ---------------------------------------

     def _get_confirmed_bbox_at(self, x, y):
          
          # If a bbox is already selected, only allow deselection
          if self.selected_bbox:
               x1, y1, x2, y2 = self.selected_bbox['coords']
               if x1 <= x <= x2 and y1 <= y <= y2:
                    return self.selected_bbox  # Clicking on selected bbox returns it for deselection
               return None  # Clicking outside does nothing

          # Otherwise, find the smallest bbox containing the point
          selected_bbox = None
          smallest_area = None
          for bb in self.confirmed_bboxes:
               x1, y1, x2, y2 = bb['coords']
               if x1 <= x <= x2 and y1 <= y <= y2:
                    area = (x2 - x1) * (y2 - y1)
                    if smallest_area is None or area < smallest_area:
                         smallest_area = area
                         selected_bbox = bb
          return selected_bbox
     
     def _get_confirmed_second_bbox_relationship(self, x, y):
          """
          This method is used for get the target bbox in adding new relationships.
          """
          selected_bbox = None
          smallest_area = None
          for bb in self.confirmed_bboxes:
               x1, y1, x2, y2 = bb['coords']
               if x1 <= x <= x2 and y1 <= y <= y2:
                    area = (x2 - x1) * (y2 - y1)
                    if smallest_area is None or area < smallest_area:
                         smallest_area = area
                         selected_bbox = bb
          return selected_bbox
     
     def _select_bbox(self, bbox):
          """
          Mark the given confirmed bbox as selected (change outline to blue)
          and update the labeled view selection.
          """

          if self.create_bbox_active or self.attribute_add_mode or self.relationship_mode:
               return
          
          if self.selected_bbox is not None and self.selected_bbox is not bbox:
               self._deselect_bbox(self.selected_bbox)
          
          bbox['selected'] = True
          self.canvas.itemconfig(bbox['rect_id'], outline="blue", width=3)
          self.selected_bbox = bbox

          # Update the label view: clear any existing selection and set the item corresponding to this bbox.
          target_entry = f"{bbox['label_str']}:{bbox['id']}"
          list_items = self.labeled_listbox.get(0, tk.END)
          for index, item in enumerate(list_items):
               if item == target_entry:
                    self.labeled_listbox.selection_clear(0, tk.END)
                    self.labeled_listbox.selection_set(index)
                    self.labeled_listbox.activate(index)
                    break
          
          # Create a background rectangle behind the text label
          if "text_id" in bbox:
               # Get the bounding box of the text item
               text_coords = self.canvas.bbox(bbox['text_id'])
               if text_coords:
                    pad = 2  # add a little padding
                    bg_rect = self.canvas.create_rectangle(
                         text_coords[0] - pad, text_coords[1] - pad,
                         text_coords[2] + pad, text_coords[3] + pad,
                         fill="black",  # choose a contrasting background color (or any color you prefer)
                         outline=""
                    )
                    
                    # Lower the rectangle below the text item.
                    self.canvas.tag_lower(bg_rect, bbox['text_id'])
                    bbox['text_bg_id'] = bg_rect

          # Update the view for new label
          self.update_relationship_view()
          self.update_attribute_view()

     def _deselect_bbox(self, bbox):
          """
          Deselect the given bbox (restore outline to red) and update the selection state.
          """
          bbox['selected'] = False
          self.canvas.itemconfig(bbox['rect_id'], outline="red", width=3)

          # Remove background rectangle if it exists.
          if 'text_bg_id' in bbox:
               self.canvas.delete(bbox['text_bg_id'])
               del bbox['text_bg_id']

          target_entry = f"{bbox['label_str']}:{bbox['id']}"
          list_items = self.labeled_listbox.get(0, tk.END)
          for index, item in enumerate(list_items):
               if item == target_entry:
                    self.labeled_listbox.selection_clear(index)
                    break
          
          # Click a bbox again will deselect it
          if self.selected_bbox == bbox:
               self.selected_bbox = None

          # Update the view for new label
          self.update_relationship_view()
          self.update_attribute_view()

     
     #---------------------------------------
     # Import List Functions for components 3-5-7
     # ---------------------------------------

     def import_label_list(self):
          """
          Import a list of labels from a text file and display them in components 3.
          Also create a dictionary matching id saved in outputs for storing annotated data as int values.
          """
          file_path = filedialog.askopenfilename(
               title="Import Label List",
               filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
          )
          if not file_path:
               return

          # Determine the JSON filename from the imported file's name.
          json_file = os.path.join(self.output_dir, "labels.json")

          # Check if the JSON file already exists.
          if os.path.exists(json_file):
               proceed = messagebox.askokcancel(
                    "File Exists",
                    f"A file list of labels is already exists in the output folder. "
                    "Importing will replace it. Do you want to proceed?"
               )
               if not proceed:
                    return

          try:
               with open(file_path, "r", encoding="utf-8") as file:
                    labels = file.read().splitlines()
               self.label_listbox.delete(0, tk.END)
               for lbl in labels:
                    self.label_listbox.insert(tk.END, lbl)

               # Create a dictionary mapping ids (starting at 1) to labels.
               self.labels_mapping = {lbl: int(i + 1) for i, lbl in enumerate(labels)}

               with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(self.labels_mapping, f, indent=4)

               # Check if 
          except Exception as e:
               messagebox.showerror("Import Label List Error", str(e))


     def import_attribute_list(self):
          """
          Import a list of attributes from a text file and display them in Components 5.
          Also create a dictionary matching id saved in outputs for storing annotated data as int values.
          """
          file_path = filedialog.askopenfilename(
               title="Import Attribute List",
               filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
          )
          if not file_path:
               return

          # Determine the JSON filename from the imported file's name.
          json_file = os.path.join(self.output_dir, "attributes.json")

          # Check if the JSON file already exists.
          if os.path.exists(json_file):
               proceed = messagebox.askokcancel(
                    "File Exists",
                    f"A file list of attributes is already exists in the output folder. "
                    "Importing will replace it. Do you want to proceed?"
               )
               if not proceed:
                    return

          try:
               with open(file_path, "r", encoding="utf-8") as file:
                    attributes = file.read().splitlines()
               self.attr_listbox.delete(0, tk.END)
               for attr in attributes:
                    self.attr_listbox.insert(tk.END, attr)

               # Create a dictionary mapping ids (starting at 1) to attributes.
               self.attributes_mapping = {attr: int(i + 1) for i, attr in enumerate(attributes)}
               with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(self.attributes_mapping, f, indent=4)
          except Exception as e:
               messagebox.showerror("Import Attribute List Error", str(e))

     def import_relationship_list(self):
          """
          Import a list of relationships from a text file and display them in components 7.
          Also create a dictionary matching id saved in outputs for storing annotated data as int values.
          """
          file_path = filedialog.askopenfilename(
               title="Import Relationship List",
               filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
          )
          if not file_path:
               return

          # Determine the JSON filename from the imported file's name.
          json_file = os.path.join(self.output_dir, "relationships.json")

          # Check if the JSON file already exists.
          if os.path.exists(json_file):
               proceed = messagebox.askokcancel(
                    "File Exists",
                    f"A file list of relationships is already exists in the output folder. "
                    "Importing will replace it. Do you want to proceed?"
               )
               if not proceed:
                    return

          try:
               with open(file_path, "r", encoding="utf-8") as file:
                    relationships = file.read().splitlines()
               self.rel_listbox.delete(0, tk.END)
               for rel in relationships:
                    self.rel_listbox.insert(tk.END, rel)
               
               # Create a dictionary mapping ids (starting at 1) to relationship.
               self.relationships_mapping = {rel: int(i + 1) for i, rel in enumerate(relationships)}
               with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(self.relationships_mapping, f, indent=4)

          except Exception as e:
               messagebox.showerror("Import Relationship List Error", str(e))


     #---------------------------------------
     # Creating draggable bounding box
     # ---------------------------------------

     def create_handles(self, bbox):
          """Create draggable handle ovals at the corners and midpoints of the box."""
          x1, y1, x2, y2 = bbox['coords']
          r = 5  # radius of the handle circles
          handles = {}
          # Corners
          handles['tl'] = self.canvas.create_oval(x1 - r, y1 - r, x1 + r, y1 + r, fill="blue", outline="")
          handles['tr'] = self.canvas.create_oval(x2 - r, y1 - r, x2 + r, y1 + r, fill="blue", outline="")
          handles['bl'] = self.canvas.create_oval(x1 - r, y2 - r, x1 + r, y2 + r, fill="blue", outline="")
          handles['br'] = self.canvas.create_oval(x2 - r, y2 - r, x2 + r, y2 + r, fill="blue", outline="")
          # Midpoints
          handles['tm'] = self.canvas.create_oval((x1+x2)/2 - r, y1 - r, (x1+x2)/2 + r, y1 + r, fill="blue", outline="")
          handles['bm'] = self.canvas.create_oval((x1+x2)/2 - r, y2 - r, (x1+x2)/2 + r, y2 + r, fill="blue", outline="")
          handles['ml'] = self.canvas.create_oval(x1 - r, (y1+y2)/2 - r, x1 + r, (y1+y2)/2 + r, fill="blue", outline="")
          handles['mr'] = self.canvas.create_oval(x2 - r, (y1+y2)/2 - r, x2 + r, (y1+y2)/2 + r, fill="blue", outline="")
          bbox['handles'] = handles

          # For each handle, add a tag with the handle type and bind events.
          for key, hid in handles.items():
               # Add a tag with the key (e.g. "tl", "tr", etc.)
               self.canvas.itemconfig(hid, tags=("handle", key))
               # Bind mouse events to the handle
               self.canvas.tag_bind(hid, "<Button-1>", self.on_handle_press)
               self.canvas.tag_bind(hid, "<B1-Motion>", self.on_handle_drag)
               self.canvas.tag_bind(hid, "<ButtonRelease-1>", self.on_handle_release)

     def update_handles(self, bbox):
          """Reposition the handles based on the new bbox coordinates."""
          if 'handles' not in bbox:
               return
          x1, y1, x2, y2 = bbox['coords']
          r = 5
          new_coords = {
               "tl": (x1 - r, y1 - r, x1 + r, y1 + r),
               "tr": (x2 - r, y1 - r, x2 + r, y1 + r),
               "bl": (x1 - r, y2 - r, x1 + r, y2 + r),
               "br": (x2 - r, y2 - r, x2 + r, y2 + r),
               "tm": ((x1+x2)/2 - r, y1 - r, (x1+x2)/2 + r, y1 + r),
               "bm": ((x1+x2)/2 - r, y2 - r, (x1+x2)/2 + r, y2 + r),
               "ml": (x1 - r, (y1+y2)/2 - r, x1 + r, (y1+y2)/2 + r),
               "mr": (x2 - r, (y1+y2)/2 - r, x2 + r, (y1+y2)/2 + r)
          }
          for key, hid in bbox['handles'].items():
               self.canvas.coords(hid, *new_coords[key])

     def on_handle_press(self, event):
          """Record which handle is being pressed and its starting position."""
          handle_id = self.canvas.find_withtag("current")[0]
          self.dragging_handle = handle_id
          self.last_handle_x = event.x
          self.last_handle_y = event.y

     def on_handle_drag(self, event):
          """Handle dragging of a resize handle to adjust the pending bbox, clamped to the image area."""
          if not hasattr(self, "dragging_handle"):
               return
          dx = event.x - self.last_handle_x
          dy = event.y - self.last_handle_y
          self.last_handle_x = event.x
          self.last_handle_y = event.y
          # Get which handle (key) is being dragged.
          tags = self.canvas.gettags(self.dragging_handle)
          if len(tags) < 2:
               return
          handle_key = tags[1]  # e.g., "tl", "tr", etc.
          x1, y1, x2, y2 = self.pending_bbox['coords']
          # Update coordinates based on which handle is dragged.
          if handle_key == "tl":
               x1 += dx
               y1 += dy
          elif handle_key == "tr":
               x2 += dx
               y1 += dy
          elif handle_key == "bl":
               x1 += dx
               y2 += dy
          elif handle_key == "br":
               x2 += dx
               y2 += dy
          elif handle_key == "tm":
               y1 += dy
          elif handle_key == "bm":
               y2 += dy
          elif handle_key == "ml":
               x1 += dx
          elif handle_key == "mr":
               x2 += dx

          # Enforce a minimum size.
          min_size = 10
          if x2 - x1 < min_size:
               if handle_key in ["tl", "ml", "bl"]:
                    x1 = x2 - min_size
               else:
                    x2 = x1 + min_size
          if y2 - y1 < min_size:
               if handle_key in ["tl", "tm", "tr"]:
                    y1 = y2 - min_size
               else:
                    y2 = y1 + min_size

          # Clamp the new coordinates to remain within the image area.
          if self.image_area:
               img_x, img_y, img_w, img_h = self.image_area
               x_min, y_min = img_x, img_y
               x_max, y_max = img_x + img_w, img_y + img_h
               x1 = max(x1, x_min)
               y1 = max(y1, y_min)
               x2 = min(x2, x_max)
               y2 = min(y2, y_max)

          # Update the pending bbox coordinates and redraw the rectangle.
          self.pending_bbox['coords'] = (x1, y1, x2, y2)
          self.canvas.coords(self.pending_bbox['rect_id'], x1, y1, x2, y2)
          # Update the handle positions based on the new bbox coordinates.
          self.update_handles(self.pending_bbox)


     def on_handle_release(self, event):
          """Clear dragging info when the user releases a handle."""
          if hasattr(self, "dragging_handle"):
               del self.dragging_handle
               del self.last_handle_x
               del self.last_handle_y


     #---------------------------------------
     # Interactions with created bounding boxes
     # ---------------------------------------

     def add_attribute(self) -> None:
          """
          Add an attribute to the currently selected bounding box.
               
               The user is prompted to select an attribute from the attribute list (Components 5).
               The function ensures that:
               - A bbox is selected.
               - An attribute is selected in Components 5.
               - No duplicate attribute is added.
               - A maximum of 10 attributes is enforced.
               After a successful addition, the user is asked if they want to add another.
          """
          if self.attr_listbox.size() == 0:
               messagebox.showwarning("Import Attribute List", "Please import attribute list before adding an attribute.")
               return
          
          if self.selected_bbox is None:
               messagebox.showwarning("Add Attribute", "Please select a bounding box first.")
               return
          
          # Disable the label view to prevent switching selection.
          self.labeled_listbox.config(state="disabled")

          messagebox.showinfo("Add Attribute", "Please double-click an attribute in the attribute list (Component 5) to add.")
          self.attribute_add_mode = True

     def on_attr_double_click(self, event: tk.Event) -> None:
          """
          Handle double-click on the attribute list (component 5) when in attribute-add mode.
          
          This method retrieves the attribute that was double-clicked and then:
          - Uses askyesnocancel to confirm adding the attribute.
          - If confirmed (Yes), adds the attribute to the selected bbox (if not already added
               and if the max of 10 attributes is not reached) and then asks whether to add another.
          - If the user chooses No, the process remains active so the user can double-click another attribute.
          - If the user chooses Cancel, the attribute-add mode is aborted.
          """
          if not self.attribute_add_mode:
               return

          # Get the selected attribute from component 5.
          selection = self.attr_listbox.curselection()
          if not selection:
               return
          attribute = self.attr_listbox.get(selection[0])
          
          # Ensure the selected bbox has an attribute list.
          if 'attributes' not in self.selected_bbox:
               self.selected_bbox['attributes'] = []
          
          # Check for duplicate attribute.
          if attribute in self.selected_bbox['attributes']:
               messagebox.showwarning("Add Attribute", f"The attribute '{attribute}' is already assigned to this bbox.")
               return

          # Enforce maximum of 10 attributes per bbox.
          if len(self.selected_bbox['attributes']) >= 10:
               messagebox.showwarning("Add Attribute", "You have already reached the limit of 10 attributes for this bbox.")
               self.attribute_add_mode = False
               self.labeled_listbox.config(state="normal")
               return

          # Ask for confirmation to add the attribute.
          result = messagebox.askyesnocancel("Confirm Attribute",
                                             f"Confirm add attribute '{attribute}' to the selected bbox?")
          if result is None:
               # Cancel the attribute-add process.
               self.attribute_add_mode = False
               self.labeled_listbox.config(state="normal")
               return
          if result is True:
               # Add the attribute.
               self.selected_bbox['attributes'].append(attribute)
               self.update_attribute_view()
               # Ask if the user wants to add another attribute.
               add_more = messagebox.askyesno("Add Attribute", "Do you want to add another attribute?")
               if not add_more:
                    self.attribute_add_mode = False
                    self.labeled_listbox.config(state="normal")
               # If yes, leave attribute_add_mode True for another double-click.
          else:
               # User chose No, so simply show a message and let them choose another.
               messagebox.showinfo("Add Attribute", "Please choose another attribute.")

     def add_relationship(self) -> None:
          """
          Initiate the process to add a relationship.

          The source bounding box is the currently selected bbox.
          If no bbox is selected, a warning is shown.
          Otherwise, enter relationship mode and prompt the user to
          double-click a relationship in components 7.
          """
          if self.rel_listbox.size() == 0:
               messagebox.showwarning("Import Relationship List", "Please import relationship list before adding a relationship.")
               return
          
          if self.selected_bbox is None:
               messagebox.showwarning("Add Relationship", "No bounding box is selected as source.")
               return
          
          # Disable label view during relationship mode.
          self.labeled_listbox.config(state="disabled")

          self.relationship_mode = True
          self.source_bbox = self.selected_bbox
          messagebox.showinfo("Add Relationship", 
                              "Please double-click a relationship in imported relationship list, then click on the target bounding box (different from the source).")
          
     def on_relationship_selected(self, event: tk.Event) -> None:
          """
          Handle double-click on the relationship list (components 7).
          Records the selected relationship in the pending_relationship variable.
          """
          if not self.relationship_mode:
               return
          selection = self.rel_listbox.curselection()
          if not selection:
               return
          self.pending_relationship = self.rel_listbox.get(selection[0])
          messagebox.showinfo("Add Relationship", 
                              f"Selected relationship: {self.pending_relationship}. Now click on the target bounding box (different from source).")

     def on_labeled_select(self, event):
          """
          Handler for selecting an item in Components 3 (Labeled view).
          This toggles the selection of the corresponding bounding box.
          """

          if self.create_bbox_active or self.attribute_add_mode or self.relationship_mode:
               return
          
          selection = self.labeled_listbox.curselection()

          if not selection:
               return
          
          # Get the text of the selected entry.
          idx = selection[0]
          entry = self.labeled_listbox.get(idx)

          # Find the matching confirmed bbox.
          found_bbox = None
          for bb in self.confirmed_bboxes:
               if f"{bb['label_str']}:{bb['id']}" == entry:
                    found_bbox = bb
                    break

          if found_bbox is None:
               return

          # If the clicked bbox is already selected, deselect it.
          if self.selected_bbox == found_bbox:
               self._deselect_bbox(found_bbox)
               self.labeled_listbox.selection_clear(0, tk.END)
          else:
               # Otherwise, unselect any current selection...
               if self.selected_bbox is not None:
                    self._deselect_bbox(self.selected_bbox)
               # And select the new bbox.
               self._select_bbox(found_bbox)

               # Update the listbox selection.
               self.labeled_listbox.selection_clear(0, tk.END)
               self.labeled_listbox.selection_set(idx)

     def change_label(self) -> None:
          """
          Placeholder method for changing the label of the selected bounding box.
          """
          if self.selected_bbox is None:
               messagebox.showwarning("Change Label", "No bounding box is selected.")
               return
          if self.create_bbox_active or self.attribute_add_mode or self.relationship_mode:
               messagebox.showwarning("Change Label", "Cannot change label during other operations.")
               return
          if not messagebox.askokcancel("Change Label",
                                        "Are you sure you want to change the label of the selected bounding box?\n"
                                        "All related relationships will be updated accordingly."):
               return
          
          # Enter change-label mode:
          self.change_label_mode = True
          self.change_bbox = self.selected_bbox
          self.change_old_label = self.selected_bbox['label_str']
          
          # Disable confirmed bbox (label view) selection to avoid switching.
          self.labeled_listbox.config(state="disabled")
          
          # Start flashing the selected bbox to indicate change-label mode.
          self._flash_change_bbox(self.change_bbox)
          messagebox.showinfo("Change Label",
                              "Please double-click a new label in the imported label list to choose the new label.")
          
     def remove_bbox(self) -> None:
          """
          Remove the currently selected bounding box from the canvas and the confirmed list.
          """
          if self.selected_bbox:
               
               # Find all relationships that involve this bbox.
               related_relationships = [
                    rel for rel in self.relationships 
                    if rel[0] == self.selected_bbox or rel[2] == self.selected_bbox
               ]

               # Construct confirmation message.
               if related_relationships:
                    msg = ("Removing this bounding box will also remove all related relationships "
                         f"({len(related_relationships)} found) and its attributes. Confirm removal?")
               else:
                    msg = "Removing this bounding box will also remove its attributes. Confirm removal?"

               # Ask user to confirm.
               if not messagebox.askokcancel("Remove Bounding Box", msg):
                    return

               # Remove relationships involving this bbox.
               self.relationships = [
                    rel for rel in self.relationships 
                    if rel[0] != self.selected_bbox and rel[2] != self.selected_bbox
               ]

               # If using a predicates list, update it accordingly:
               if hasattr(self, "predicates"):
                    # Create new lists that only keep predicates corresponding to remaining relationships.
                    new_predicates = []
                    for idx, rel in enumerate(self.relationships):
                         # (Assuming self.predicates is aligned with self.relationships by index.)
                         new_predicates.append(self.predicates[idx])

                    self.predicates = new_predicates

               # Delete the rectangle and associated text from the canvas.
               self.canvas.delete(self.selected_bbox['rect_id'])
               if 'text_id' in self.selected_bbox:
                    self.canvas.delete(self.selected_bbox['text_id'])
                    if 'text_bg_id' in self.selected_bbox:
                         self.canvas.delete(self.selected_bbox['text_bg_id'])
                         del self.selected_bbox['text_bg_id']


               # Remove from confirmed bounding boxes list and clear selection.
               self.confirmed_bboxes.remove(self.selected_bbox)
               self.selected_bbox = None
               
               # Update views.
               self.update_labeled_view()
               self.update_relationship_view()
               self.update_attribute_view()

     def remove_attribute(self):
          """
          Remove the selected attribute from the currently selected bounding box
          after confirming with the user.
          """
          selection = self.attribute_view_listbox.curselection()
          if not selection:
               return
          index = selection[0]
          attribute = self.attribute_view_listbox.get(index)
          if not messagebox.askokcancel("Remove Attribute", f"Are you sure you want to remove attribute '{attribute}'?"):
               return
          if self.selected_bbox and 'attributes' in self.selected_bbox:
               try:
                    self.selected_bbox['attributes'].remove(attribute)
               except ValueError:
                    pass
          self.update_attribute_view()

     def remove_relationship(self) -> None:
          """
          Remove the selected relationship from the internal relationships list
          and also remove its corresponding predicate from self.predicates.
          """
          selection = self.relationship_view_listbox.curselection()
          if not selection:
               return
          index = selection[0]
          if not messagebox.askokcancel("Remove Relationship", "Are you sure you want to remove this relationship?"):
               return
          
          # Build a list of indices that correspond to relationships shown in the view.
          displayed_indices = []
          for i, rel in enumerate(self.relationships):
               source_bbox, rel_str, target_bbox = rel
               
               # If a bbox is selected, then only relationships whose source equals the selected bbox are displayed.
               if self.selected_bbox is not None and source_bbox != self.selected_bbox:
                    continue
               displayed_indices.append(i)

          if index < len(displayed_indices):
               actual_index = displayed_indices[index]
               # Remove the relationship and its corresponding predicate
               self.relationships.pop(actual_index)
               if hasattr(self, "predicates") and self.predicates:
                    self.predicates.pop(actual_index)
               self.update_relationship_view()

     #---------------------------------------
     # Handling context menus (Total 3)
     # ---------------------------------------
     def show_context_menu(self, event: tk.Event) -> None:
          """
          Display a context menu at the current cursor position when a
          bounding box is selected.

          The menu provides options: Add Attribute, Add Relationship,
          Change Label, and Remove bbox.

          :param event: The Tkinter event that triggered the right-click.
          """
          # Only show context menu if a bounding box is selected.
          if self.selected_bbox is None:
               return
          
          # If in the middle of adding an attribute, adding a relationship, or changing a label, do not allow any context menu operations.
          if self.attribute_add_mode or self.relationship_mode or self.change_label_mode:
               return

          # Create a context menu with tearoff disabled.
          context_menu = tk.Menu(self.master, tearoff=0)
          context_menu.add_command(label="Add Attribute", command=self.add_attribute)
          context_menu.add_command(label="Add Relationship", command=self.add_relationship)
          context_menu.add_command(label="Change Label", command=self.change_label)
          context_menu.add_command(label="Remove bbox", command=self.remove_bbox)

          # Post the menu at the current screen position of the cursor.
          context_menu.post(event.x_root, event.y_root)

     def show_attribute_context_menu(self, event):
          """
          Show a context menu in the attribute view (components 12) to remove an attribute.
          """
          # If we are in the middle of adding an attribute, adding a relationship, or changing a label, do not allow any context menu operations.
          if self.attribute_add_mode or self.relationship_mode or self.change_label_mode or self.create_bbox_active:
               return

          try:
               # Get the index of the clicked item.
               index = self.attribute_view_listbox.nearest(event.y)
               
               # Optionally, select that item.
               self.attribute_view_listbox.selection_clear(0, tk.END)
               self.attribute_view_listbox.selection_set(index)
               
               # Create the context menu.
               menu = tk.Menu(self.master, tearoff=0)
               menu.add_command(label="Remove Attribute", command=self.remove_attribute)
               menu.post(event.x_root, event.y_root)
          except Exception as e:
               # You can log the exception if needed.
               pass

     def show_relationship_context_menu(self, event: tk.Event) -> None:
          """
          Show a context menu in the relationship view (component 13) to remove a relationship.
          """
          # If we are in the middle of adding an attribute, adding a relationship, or changing a label, do not allow any context menu operations.
          if self.attribute_add_mode or self.relationship_mode or self.change_label_mode or self.create_bbox_active:
               return
          
          try:
               # Get the index of the clicked item in the relationship view.
               index = self.relationship_view_listbox.nearest(event.y)
               self.relationship_view_listbox.selection_clear(0, tk.END)
               self.relationship_view_listbox.selection_set(index)
               
               # Create and show the context menu.
               menu = tk.Menu(self.master, tearoff=0)
               menu.add_command(label="Remove Relationship", command=self.remove_relationship)
               menu.post(event.x_root, event.y_root)
          except Exception as e:
               # (Optional) log or print(e)
               pass

     # ---------------------------------------
     # Update view components (11-labels, 12-attributes, 13-relationships)
     # ---------------------------------------
     def update_labeled_view(self):
          """
          Update Components 11 (Labeled view) with confirmed bounding boxes.
          Entries are shown as "label:id", sorted alphabetically (with same label sorted by id).
          """
          # Sort confirmed bounding boxes.
          sorted_bboxes = sorted(self.confirmed_bboxes,
                                   key=lambda bb: (bb['label'], bb['id']))
          self.labeled_listbox.delete(0, tk.END)
          for bb in sorted_bboxes:
               entry = f"{bb['label_str']}:{bb['id']}"
               self.labeled_listbox.insert(tk.END, entry)

     def update_attribute_view(self) -> None:
          """
          Update Attribute view (component 12) with attributes assigned to the selected bounding box.
          
          If no bbox is selected, the view is cleared.
          """
          self.attribute_view_listbox.delete(0, tk.END)
          if self.selected_bbox and 'attributes' in self.selected_bbox:
               for attr in self.selected_bbox['attributes']:
                    self.attribute_view_listbox.insert(tk.END, attr)

     def update_relationship_view(self) -> None:
          """
          Update Relationship view (component 13) with saved relationships.
          
          If a bbox is selected, display only relationships whose source matches the selected bbox.
          Each entry is displayed as "label_str:instance --- relationship --- label_str:instance".
          """
          self.relationship_view_listbox.delete(0, tk.END)
          for rel in self.relationships:
               source_bbox, rel_str, target_bbox = rel
               # If a bbox is selected, filter to only those whose source equals the selected bbox.
               if self.selected_bbox is not None and source_bbox != self.selected_bbox:
                    continue
               entry = f"{source_bbox['label_str']}:{source_bbox['id']} --- {rel_str} --- {target_bbox['label_str']}:{target_bbox['id']}"
               self.relationship_view_listbox.insert(tk.END, entry)

     # ---------------------------------------
     # Handling saving data:
     # ---------------------------------------
     def save_data(self) -> None:
          """
          Save annotation data to disk in JSON format.

          The output JSON file will have the format:
          {
               "image-name": <absolute path>,
               "width": <image original width>
               "height: <image original height>
               "attribute": <(N x 10) array of attributes (np.int32) as list>,
               "boxes_1024": <(N x 4) array of bounding boxes scaled to 1024 as list>,
               "boxes_512": <(N x 4) array of bounding boxes scaled to 512 as list>,
               "labels": <(N,) array of label ids (np.int32) as list>,
               "relationships": <(M x 2) array of relationships (np.int32) as list>,
               "predicates": <(M,) array of predicate ids (np.int32) as list>
          }
          """
          if self.loaded_image is None:
               messagebox.showwarning("Save Data", "No image loaded!")
               return

          # Get original image size.
          orig_w, orig_h = self.loaded_image.size

          # Get the displayed image parameters.
          x_offset, y_offset, disp_w, disp_h = self.image_area
          
          # The scale used to display the image:
          scale = disp_w / orig_w  # or disp_h / orig_h

          # Prepare lists for boxes and other data.
          boxes_1024 = []
          boxes_512 = []
          attributes_list = []
          labels_list = []

          for bbox in self.confirmed_bboxes:
               # Canvas coordinates for the bbox:
               x1, y1, x2, y2 = bbox['coords']
               
               # Convert to original image coordinates:
               orig_x1 = (x1 - x_offset) / scale
               orig_y1 = (y1 - y_offset) / scale
               orig_x2 = (x2 - x_offset) / scale
               orig_y2 = (y2 - y_offset) / scale
               
               # Compute center, width, height in original coordinates:
               center_x = (orig_x1 + orig_x2) / 2
               center_y = (orig_y1 + orig_y2) / 2
               box_width = orig_x2 - orig_x1
               box_height = orig_y2 - orig_y1

               # Compute scaling factors for 1024 and 512.
               factor_1024 = 1024 / max(orig_w, orig_h)
               factor_512 = 512 / max(orig_w, orig_h)

               box_1024 = np.array([int(center_x * factor_1024), int(center_y * factor_1024),
                         int(box_width * factor_1024), int(box_height * factor_1024)], dtype=np.int32)
               box_512 = np.array([int(center_x * factor_512), int(center_y * factor_512),
                         int(box_width * factor_512), int(box_height * factor_512)], dtype=np.int32)
               boxes_1024.append(box_1024)
               boxes_512.append(box_512)

               # Process attributes: convert attribute strings to numeric ids
               # using self.attributes_mapping. Pad to length 10.
               attr_ids = [self.attributes_mapping.get(a, 0) for a in bbox.get('attributes', [])]
               while len(attr_ids) < 10:
                    attr_ids.append(0)
               attributes_list.append(attr_ids)

               # For label, already stored as numeric.
               labels_list.append(bbox['label'])

          # For relationships:
          relationships_list = []
          if self.relationships:
               for rel in self.relationships:
                    source_bbox, rel_str, target_bbox = rel
                    try:
                         src_index = self.confirmed_bboxes.index(source_bbox)
                         tgt_index = self.confirmed_bboxes.index(target_bbox)
                    except ValueError:
                         # If one of the bboxes is not found (should not happen normally), skip this relationship.
                         continue
                    relationships_list.append(np.array([src_index, tgt_index], dtype=np.int32))
          else:
               relationships_list = []

          # Convert lists to numpy arrays of type int32.
          attributes_array = np.array(attributes_list, dtype=np.int32)
          boxes_1024_array = np.array(boxes_1024, dtype=np.int32)
          boxes_512_array = np.array(boxes_512, dtype=np.int32)
          labels_array = np.array(labels_list, dtype=np.int32)
          relationships_array = np.array(relationships_list, dtype=np.int32)
          predicates_array = np.array(self.predicates, dtype=np.int32) if hasattr(self, "predicates") and self.predicates else np.empty((0,), dtype=np.int32)

          # Construct output data dictionary.
          output_data = {
               "image-name": os.path.abspath(self.image_path) if hasattr(self, "image_path") else "",
               "width": orig_w,
               "height": orig_h,
               "attribute": attributes_array.tolist(),
               "boxes_1024": boxes_1024_array.tolist(),
               "boxes_512": boxes_512_array.tolist(),
               "labels": labels_array.tolist(),
               "relationships": relationships_array.tolist(),
               "predicates": predicates_array.tolist()
          }

          # Save the output data to a JSON file.
          if hasattr(self, "image_path"):
               base_name = os.path.splitext(os.path.basename(self.image_path))[0]
          else:
               base_name = "annotation_output"

          output_file_json = os.path.join(self.output_dir, f"{base_name}.json")
          output_file_h5 = os.path.join(self.output_dir, f"{base_name}.h5")
          try:
               # Save data in json file:
               with open(output_file_json, "w", encoding="utf-8") as f:
                    json.dump(output_data, f, indent=4)

               # Save data in h5 file:
               with h5py.File(output_file_h5, "w") as hf:
                    # Store image name as a string attribute
                    hf.attrs["image-name"] = os.path.abspath(self.image_path) if hasattr(self, "image_path") else ""

                    # Store width/height as numeric attributes
                    hf.attrs["width"] = orig_w
                    hf.attrs["height"] = orig_h

                    # Create datasets for the numeric arrays
                    hf.create_dataset("attribute", data=attributes_array)
                    hf.create_dataset("boxes_1024", data=boxes_1024_array)
                    hf.create_dataset("boxes_512", data=boxes_512_array)
                    hf.create_dataset("labels", data=labels_array)
                    hf.create_dataset("relationships", data=relationships_array)
                    hf.create_dataset("predicates", data=predicates_array)

               messagebox.showinfo("Save Data", f"Annotation data saved to {output_file_json}")
          except Exception as e:
               messagebox.showerror("Save Data Error", str(e))

     # ---------------------------------------
     # Helper Methods
     # ---------------------------------------
     def _inside_image_area(self, x, y):
          """
          Check if the given (x,y) coordinates fall inside the active image area.
          :return: True if inside; False otherwise.
          """

          if not self.image_area:
               print("False")
               return False
     
          area_x, area_y, area_w, area_h = self.image_area
          return area_x <= x <= area_x + area_w and area_y <= y <= area_y + area_h
     

     def _auto_load_imported_files(self) -> None:
          # Auto-load labels.json
          labels_file = os.path.join(self.output_dir, "labels.json")
          if os.path.exists(labels_file):
               try:
                    with open(labels_file, "r", encoding="utf-8") as f:
                         self.labels_mapping = json.load(f)
                    self.label_listbox.delete(0, tk.END)
                    
                    # Sort by the numeric id (the value) instead of trying to convert the key.
                    for label in sorted(self.labels_mapping, key=lambda k: self.labels_mapping[k]):
                         self.label_listbox.insert(tk.END, label)
               except Exception as e:
                    messagebox.showerror("Load Label List", str(e))
          
          # Auto-load attributes.json
          attr_file = os.path.join(self.output_dir, "attributes.json")
          if os.path.exists(attr_file):
               try:
                    with open(attr_file, "r", encoding="utf-8") as f:
                         self.attributes_mapping = json.load(f)
                    self.attr_listbox.delete(0, tk.END)
                    for attr in sorted(self.attributes_mapping, key=lambda k: self.attributes_mapping[k]):
                         self.attr_listbox.insert(tk.END, attr)
               except Exception as e:
                    messagebox.showerror("Load Attribute List", str(e))
          
          # Auto-load relationships.json
          rel_file = os.path.join(self.output_dir, "relationships.json")
          if os.path.exists(rel_file):
               try:
                    with open(rel_file, "r", encoding="utf-8") as f:
                         self.relationships_mapping = json.load(f)
                    self.rel_listbox.delete(0, tk.END)
                    for rel in sorted(self.relationships_mapping, key=lambda k: self.relationships_mapping[k]):
                         self.rel_listbox.insert(tk.END, rel)

               except Exception as e:
                    messagebox.showerror("Load Relationship List", str(e))

     def _flash_change_bbox(self, bbox: dict) -> None:
          """
          Flash the given bbox (by toggling its dash) to indicate that its label
          is in change mode.
          """
          if not self.change_label_mode:
               return
          
          # Alternate the dash pattern (for example, blue dashed vs. solid blue)
          current_dash = self.canvas.itemcget(bbox['rect_id'], "dash")
          new_dash = (5, 2) if current_dash == "" else ""
          self.canvas.itemconfig(bbox['rect_id'], outline="blue", dash=new_dash)
          self.master.after(500, lambda: self._flash_change_bbox(bbox))

def main():
    """
    Main entry point for the Annotation Tool application.
    """
    root = tk.Tk()
    app = AnnotationTool(root)
    root.mainloop()


if __name__ == "__main__":
    main()
