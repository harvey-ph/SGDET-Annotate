# pwang.py
from main import AnnotationTool
import tkinter as tk

class EnhancedAnnotationTool(AnnotationTool):
    def __init__(self, master):
        self.multi_selected_bboxes = []  # Ensure this is initialized
        super().__init__(master)
        master.bind_all("<Up>", self.move_boxes_up)
        master.bind_all("<Down>", self.move_boxes_down)
        master.bind_all("<Left>", self.move_boxes_left)
        master.bind_all("<Right>", self.move_boxes_right)
        master.bind_all("<Return>", self.confirm_bbox_and_advance)

    def move_all_boxes(self, dx, dy):
        for bbox in self.confirmed_bboxes:
            self._move_bbox(bbox, dx, dy)

    def move_selected_boxes(self, dx, dy):
        if hasattr(self, 'multi_selected_bboxes') and self.multi_selected_bboxes:
            for bbox in self.multi_selected_bboxes:
                self._move_bbox(bbox, dx, dy)
        elif self.selected_bbox:
            self._move_bbox(self.selected_bbox, dx, dy)
        else:
            self.move_all_boxes(dx, dy)

    def _move_bbox(self, bbox, dx, dy):
        x1, y1, x2, y2 = bbox['coords']
        new_coords = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)
        bbox['coords'] = new_coords
        self.canvas.coords(bbox['rect_id'], *new_coords)
        if 'text_id' in bbox:
            self.canvas.move(bbox['text_id'], dx, dy)
        if 'text_bg_id' in bbox:
            self.canvas.move(bbox['text_bg_id'], dx, dy)
        if 'handles' in bbox:
            self.update_handles(bbox)

    def move_boxes_up(self, event):
        self.move_selected_boxes(0, -5)
        return "break"

    def move_boxes_down(self, event):
        self.move_selected_boxes(0, 5)
        return "break"

    def move_boxes_left(self, event):
        self.move_selected_boxes(-5, 0)
        return "break"

    def move_boxes_right(self, event):
        self.move_selected_boxes(5, 0)
        return "break"

    def confirm_bbox_and_advance(self, event):
        if self.selected_bbox:
            self._deselect_bbox(self.selected_bbox)
        if self.labeled_listbox.size() > 0:
            # Advance to next box in the list
            current = self.labeled_listbox.curselection()
            next_index = (current[0] + 1) if current else 0
            if next_index < self.labeled_listbox.size():
                self.labeled_listbox.selection_clear(0, tk.END)
                self.labeled_listbox.selection_set(next_index)
                self.labeled_listbox.activate(next_index)
                self.labeled_listbox.event_generate("<<ListboxSelect>>")
        self.canvas.focus_set()  # Ensure canvas retains keyboard focus
        return "break"

    def _select_bbox(self, bbox):
        super()._select_bbox(bbox)
        self.canvas.focus_set()  # Ensure arrow keys go to canvas

if __name__ == "__main__":
    root = tk.Tk()
    app = EnhancedAnnotationTool(root)
    root.mainloop()
