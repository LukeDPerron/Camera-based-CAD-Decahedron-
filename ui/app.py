"""CustomTkinter camera canvas. Run: python ui/app.py"""

import sys
import platform

if not (3, 10) <= sys.version_info[:2] <= (3, 14):
    raise SystemExit(
        f"Python {platform.python_version()} is not supported. "
        "Please use Python 3.10–3.14 with the workspace root requirements.txt."
    )
if (platform.system() == "Darwin" and platform.machine() == "x86_64"
        and sys.version_info[:2] >= (3, 13)):
    raise SystemExit(
        "Intel Macs (including Python running under Rosetta) need Python 3.10–3.12 "
        "because newer MediaPipe releases do not provide Intel Mac wheels. "
        "Use Python 3.12, or native arm64 Python on an Apple Silicon Mac."
    )

import tkinter as tk
from pathlib import Path
from queue import Empty, SimpleQueue
from threading import Thread
import time

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageOps, ImageTk

from tracking import CameraWorker, Frame, ViewOptions
from cameras import CameraDevice, discover_cameras
from dwell import DwellSelector
from scene_overlay import draw_scene, shape_center
from shape_interaction import ShapeInteraction
from gesture_effects import GestureEffects

# Direct script launches put ui/, rather than the repository root, on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.command_handler import CommandHandler
from src.gesture_event import GestureEvent, GestureType, ShapeType
from src.scene import Scene

from color_panel import ColorPanel, panel_frame_rect
from colors.shape_color import set_shape_color


BG = "#10151C"
PANEL = "#18212B"
CANVAS = "#0B1016"
TEXT = "#EDF4F7"
MUTED = "#95A5B5"
ACCENT = "#5FE6BE"


class CameraCanvasApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Camera Canvas · Hand tracking")
        self.geometry("1180x780")
        self.minsize(900, 660)
        self.configure(fg_color=BG)
        self.worker: CameraWorker | None = None
        self.last_image: Image.Image | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.error = False
        self.closing = False
        self.live = False
        self.dwell = DwellSelector()
        self.quit_dwell = DwellSelector(duration=0.85)
        self.tip = None
        self.tip_seen = None
        self.shape_count = 0
        self.scene = Scene()
        self.shape_commands = CommandHandler(self.scene)
        self.interaction = ShapeInteraction()
        self.effects = GestureEffects()
        self.shape_message = ""
        self.shape_message_until = 0.0
        self.color_panel = ColorPanel()
        self.camera_name = tk.StringVar(value="Finding cameras…")
        self.camera_choices: dict[str, CameraDevice] = {}
        self.camera_scan: Thread | None = None
        self.camera_results = SimpleQueue()
        self.sidebar_visible = True
        self.restart_camera = False
        self.mirror = tk.BooleanVar(value=True)
        self.landmarks = tk.BooleanVar(value=True)
        self.cursor = tk.BooleanVar(value=True)
        self.single_hand = tk.BooleanVar(value=False)
        self.snap_to_faces = tk.BooleanVar(value=False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_workspace()
        ctk.CTkLabel(
            self, text="Local camera preview · No video or images are saved",
            text_color=MUTED, font=ctk.CTkFont(size=12), anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=26, pady=(0, 16))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _event: self.close())
        self.after(20, self._poll)
        self.startup_scan_job = self.after(250, lambda: self.refresh_cameras(auto_start=True))

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=26, pady=(24, 20))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="Camera canvas", text_color=TEXT,
            font=ctk.CTkFont(size=28, weight="bold"), anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header, text="Your surroundings. Your hands. One workspace.",
            text_color=MUTED, font=ctk.CTkFont(size=13), anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        self.status = ctk.CTkLabel(
            header, text="●  Ready", fg_color=PANEL, text_color=MUTED,
            corner_radius=14, width=116, height=32, font=ctk.CTkFont(size=12),
        )
        self.status.grid(row=0, column=1, rowspan=2, padx=(20, 0))

    def _build_workspace(self):
        workspace = ctk.CTkFrame(self, fg_color="transparent")
        workspace.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 16))
        workspace.grid_columnconfigure(0, weight=1)
        workspace.grid_rowconfigure(0, weight=1)
        viewport = ctk.CTkFrame(workspace, fg_color=CANVAS, corner_radius=16)
        viewport.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self.viewport = viewport
        self.canvas = tk.Canvas(viewport, bg=CANVAS, highlightthickness=0, bd=0)
        self.canvas.bind("<Button-1>", self._click_shape)
        self.canvas.bind("<Button-1>", self._click_color_panel, add="+")
        self.canvas.pack(fill="both", expand=True, padx=12, pady=12)
        self.image_item = self.canvas.create_image(0, 0, anchor="center")
        self.message_item = self.canvas.create_text(
            0, 0, text="Preparing camera…", fill=MUTED, justify="center",
            font=("Helvetica", 15), width=500,
        )
        self.canvas.bind("<Configure>", self._resize_canvas)
        self.sidebar = ctk.CTkFrame(workspace, fg_color=PANEL, corner_radius=16)
        self.sidebar.grid(row=0, column=1, sticky="ns")
        # Draw a crisp sidebar symbol without depending on platform icon fonts.
        icon = Image.new("RGBA", (48, 48))
        draw = ImageDraw.Draw(icon)
        draw.rounded_rectangle((7, 9, 41, 39), radius=4, outline=TEXT, width=3)
        draw.line((29, 10, 29, 38), fill=TEXT, width=3)
        self.sidebar_icon = ctk.CTkImage(light_image=icon, dark_image=icon, size=(20, 20))
        self.sidebar_toggle = ctk.CTkButton(
            self.sidebar, text="", image=self.sidebar_icon,
            command=self._toggle_sidebar, width=32, height=32,
            fg_color="transparent", hover_color="#243341", corner_radius=8,
        )
        self.sidebar_toggle.pack(anchor="e", padx=6, pady=(6, 2))
        sidebar = ctk.CTkScrollableFrame(
            self.sidebar, width=226, fg_color=PANEL, corner_radius=16,
            scrollbar_button_color="#344353",
        )
        sidebar.pack(fill="both", expand=True)
        self.sidebar_content = sidebar
        sidebar.grid_columnconfigure(0, weight=1)
        self._section(sidebar, "CAMERA", 0, top=22)
        camera_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        camera_row.grid(row=1, column=0, sticky="ew", padx=20)
        self.camera_dropdown = ctk.CTkOptionMenu(
            camera_row, variable=self.camera_name, values=["Finding cameras…"],
            command=self._select_camera, state="disabled", width=186, height=32,
            fg_color=BG, button_color="#344353", button_hover_color="#46596C",
            text_color=TEXT, font=ctk.CTkFont(size=12), dynamic_resizing=False,
        )
        self.camera_dropdown.pack(fill="x")
        self.refresh_button = ctk.CTkButton(
            camera_row, text="Refresh cameras", command=self.refresh_cameras,
            height=26, fg_color="transparent", hover_color="#243341",
            text_color=MUTED, font=ctk.CTkFont(size=12),
        )
        self.refresh_button.pack(fill="x", pady=(8, 0))
        self.camera_button = ctk.CTkButton(
            sidebar, text="Start camera", command=self._toggle_camera,
            fg_color=ACCENT, hover_color="#44CBA5", text_color="#0B2420",
            height=38, font=ctk.CTkFont(size=13, weight="bold"), state="disabled",
        )
        self.camera_button.grid(row=2, column=0, sticky="ew", padx=20, pady=(14, 0))
        self._section(sidebar, "GESTURE MODE", 3)
        self.mode_switch = ctk.CTkSegmentedButton(
            sidebar, values=["Legacy", "Updated"], command=self._set_gesture_mode,
            fg_color=BG, selected_color="#166B59", selected_hover_color="#1C806C",
            unselected_color="#344353", unselected_hover_color="#46596C",
            text_color=TEXT, font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.mode_switch.grid(row=4, column=0, sticky="ew", padx=20)
        self.mode_switch.set(self.interaction.mode)
        self.mode_help = ctk.CTkLabel(
            sidebar, justify="left", anchor="w", text_color=TEXT, wraplength=190,
            font=ctk.CTkFont(size=12),
        )
        self.mode_help.grid(row=5, column=0, sticky="ew", padx=20, pady=(8, 0))
        self._set_gesture_mode(self.interaction.mode)
        self._section(sidebar, "VIEW", 6)
        for row, (label, variable) in enumerate(
            (("Mirror camera", self.mirror), ("Hand landmarks", self.landmarks),
             ("Fingertip cursor", self.cursor)), start=7
        ):
            ctk.CTkSwitch(
                sidebar, text=label, variable=variable, command=self._update_options,
                progress_color=ACCENT, button_color=TEXT, text_color=TEXT,
                font=ctk.CTkFont(size=13), switch_width=36, switch_height=20,
            ).grid(row=row, column=0, sticky="w", padx=20, pady=(0, 14))
        for row, (label, variable, command) in enumerate(
            (("Snap to faces", self.snap_to_faces, self._update_face_snap),
             ("Track one hand", self.single_hand, self._update_hand_limit)), start=10
        ):
            ctk.CTkSwitch(
                sidebar, text=label, variable=variable, command=command,
                progress_color=ACCENT, button_color=TEXT, text_color=TEXT,
                font=ctk.CTkFont(size=13), switch_width=36, switch_height=20,
            ).grid(row=row, column=0, sticky="w", padx=20, pady=(0, 14))
        self._section(sidebar, "TRACKING", 12, top=10)
        telemetry = ctk.CTkFrame(sidebar, fg_color=BG, corner_radius=10)
        telemetry.grid(row=13, column=0, sticky="ew", padx=16, pady=(0, 16))
        self.hand_value = self._metric(telemetry, "Hand", "No hand", 0)
        self.pose_value = self._metric(telemetry, "Pose", "—", 1)
        self.fps_value = self._metric(telemetry, "FPS", "—", 2)
        self.position_value = self._metric(telemetry, "Tip X / Y", "—", 3)

    def _set_gesture_mode(self, mode):
        self.interaction.mode = mode
        self.interaction.grabbed = False
        self.interaction.waiting_for_pinky_down = False
        self.interaction.reset_motion()
        if mode == "Legacy":
            help_text = "Pinch to select. Thumb out moves X, point up moves Y. Sweep an open palm to move Z or twist it to rotate."
        else:
            help_text = "Pinch once to grab. Move or turn your hand with your fingers open. Pinch again to drop."
        self.mode_help.configure(text=help_text + "\nPinky-up pinch adds or removes shapes. Open palm then fist deletes the selection.")

    def _toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible
        self._reset_dwell()
        if self.sidebar_visible:
            self.sidebar_content.pack(fill="both", expand=True)
        else:
            self.sidebar_content.pack_forget()

    @staticmethod
    def _section(parent, text, row, top=22):
        ctk.CTkLabel(
            parent, text=text, text_color=MUTED,
            font=ctk.CTkFont(size=11, weight="bold"), anchor="w", height=18,
        ).grid(row=row, column=0, sticky="ew", padx=20, pady=(top, 10))

    @staticmethod
    def _metric(parent, name, value, row):
        ctk.CTkLabel(parent, text=name, text_color=MUTED, height=22, font=ctk.CTkFont(size=12)).grid(
            row=row, column=0, sticky="w", padx=(12, 8), pady=3
        )
        label = ctk.CTkLabel(parent, text=value, text_color=TEXT, height=22, font=ctk.CTkFont(size=12))
        label.grid(row=row, column=1, sticky="e", padx=(0, 12), pady=3)
        parent.grid_columnconfigure(1, weight=1)
        return label

    def _view_options(self):
        return ViewOptions(self.mirror.get(), self.landmarks.get(), self.cursor.get(),
                           self.single_hand.get())

    def _update_face_snap(self):
        self.interaction.snap_to_faces = self.snap_to_faces.get()

    def _update_hand_limit(self):
        if self.worker and self.worker.is_alive() and not self.worker.stop_event.is_set():
            self.restart_camera = True
            self._stop_camera("Changing hand tracking…")

    def _update_options(self):
        self._reset_dwell()
        if self.worker:
            self.worker.set_options(self._view_options())

    def refresh_cameras(self, auto_start=False):
        if self.closing or self.camera_scan or self.worker:
            return
        self._scan_auto_start = auto_start
        self._scan_selected = self.camera_choices.get(self.camera_name.get())
        self.camera_dropdown.configure(state="disabled")
        self.refresh_button.configure(state="disabled", text="Finding cameras…")
        self.camera_button.configure(state="disabled")
        self.status.configure(text="●  Scanning", text_color=MUTED)
        self._empty_canvas("Finding available cameras…")

        def scan():
            try:
                self.camera_results.put((discover_cameras(), ""))
            except Exception as exc:
                self.camera_results.put(([], str(exc)))

        self.camera_scan = Thread(target=scan, name="camera-discovery", daemon=True)
        self.camera_scan.start()

    def _poll_camera_scan(self):
        try:
            devices, error = self.camera_results.get_nowait()
        except Empty:
            return
        self.camera_scan = None
        self.camera_choices = {device.label: device for device in devices}
        self.refresh_button.configure(state="normal", text="Refresh cameras")
        if not devices:
            self.error = True
            self.camera_dropdown.configure(values=["No cameras found"], state="disabled")
            self.camera_name.set("No cameras found")
            self.camera_button.configure(state="disabled")
            self.status.configure(text="●  Unavailable", text_color="#FFC266")
            self._empty_canvas(error or (
                "No cameras found. Connect a camera and allow camera access "
                "in system settings, then press Refresh cameras."
            ))
            return
        self.camera_dropdown.configure(values=list(self.camera_choices), state="normal")
        previous = self._scan_selected
        selected = next((d for d in devices if previous and d.device_id == previous.device_id
                         and d.backend == previous.backend), devices[0])
        self.camera_name.set(selected.label)
        self.camera_button.configure(state="normal")
        self.status.configure(text="●  Ready", text_color=MUTED)
        self.error = False
        self._empty_canvas("Select a camera, then press Start camera.")
        if self._scan_auto_start:
            self.start_camera()

    def _select_camera(self, _label):
        if self.worker and self.worker.is_alive():
            self.restart_camera = True
            self._stop_camera("Switching camera…")

    def _stop_camera(self, message="Stopping camera…"):
        self.worker.stop()
        self.camera_button.configure(text=message, state="disabled")
        self.camera_dropdown.configure(state="disabled")
        self.refresh_button.configure(state="disabled")
        self.status.configure(text="●  Switching" if self.restart_camera else "●  Stopping",
                              text_color=MUTED)
        self._empty_canvas(message)

    def _toggle_camera(self):
        self.restart_camera = False
        if self.worker and self.worker.is_alive():
            self._stop_camera()
        else:
            self.start_camera()

    def start_camera(self):
        if self.closing or self.camera_scan or (self.worker and self.worker.is_alive()):
            return
        device = self.camera_choices.get(self.camera_name.get())
        if device is None:
            self._empty_canvas("Press Refresh cameras and select an available camera.")
            return
        self.restart_camera = False
        self.error = self.live = False
        self._empty_canvas("Preparing hand tracker…\nThe first run may download an 8 MB model.")
        self.status.configure(text="●  Starting", text_color=MUTED)
        self.camera_dropdown.configure(state="normal")
        self.refresh_button.configure(state="disabled")
        self.camera_button.configure(text="Stop camera", state="normal")
        self.worker = CameraWorker(device, self._view_options())
        self.worker.start()

    def _empty_canvas(self, message):
        self._reset_dwell()
        self.quit_dwell.reset()
        self.effects.reset()
        self.last_image = None
        self.canvas.itemconfigure(self.image_item, image="")
        self.photo = None
        self.canvas.itemconfigure(self.message_item, text=message, state="normal")
        self.hand_value.configure(text="No hand")
        self.pose_value.configure(text="—")
        self.fps_value.configure(text="—")
        self.position_value.configure(text="—")
        self.canvas.delete("shape_toolbar")

    def _resize_canvas(self, _event=None):
        self._reset_dwell()
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.canvas.coords(self.image_item, width / 2, height / 2)
        self.canvas.coords(self.message_item, width / 2, height / 2)
        self.canvas.itemconfigure(self.message_item, width=max(100, width - 60))
        self._render_image()

    def _render_image(self):
        if self.last_image is None:
            return
        size = (max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height()))
        fitted = ImageOps.contain(self.last_image, size, Image.Resampling.BILINEAR)
        draw_scene(fitted, self.scene.objects, self.interaction.selected)
        self.effects.draw(fitted, time.monotonic())
        self.photo = ImageTk.PhotoImage(fitted, master=self.canvas)
        self.canvas.itemconfigure(self.image_item, image=self.photo)
        self.canvas.itemconfigure(self.message_item, state="hidden")
        self._draw_shape_toolbar()

    def _reset_dwell(self):
        self.dwell.reset()
        self.interaction.reset_motion()
        self.tip = None
        self.tip_seen = None

    def _shape_layout(self):
        """Keep controls inside the displayed image, including letterboxed views."""
        if self.last_image is None:
            return [], None
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.last_image.size
        scale = min(max(1, width) / iw, max(1, height) / ih)
        fw, fh = int(iw * scale), int(ih * scale)
        left, top = (width - fw) / 2, (height - fh) / 2
        bw = min(48, (fw - 48) / 3)
        bh = min(48, fh * .28)
        gap = 8
        x = left + (fw - (3 * bw + 2 * gap)) / 2
        bottom = top + fh - 12
        buttons = [(name, (x + i * (bw + gap), bottom - bh,
                           x + i * (bw + gap) + bw, bottom))
                   for i, name in enumerate(("Cube", "Sphere", "Pyramid"))]
        tip = None
        if self.tip is not None:
            tip = (left + self.tip[0] * fw, top + self.tip[1] * fh)
        return buttons, tip

    @staticmethod
    def _shape_at(buttons, position):
        if position is not None:
            x, y = position
            for name, (x1, y1, x2, y2) in buttons:
                if x1 <= x <= x2 and y1 <= y <= y2:
                    return name
        return None

    def _click_shape(self, event):
        buttons, _ = self._shape_layout()
        target = self._shape_at(buttons, (event.x, event.y))
        if target is not None:
            self._select_shape(target)
            self._render_image()

    def _click_color_panel(self, event):
        """Mouse fallback for the hand-tracking pinch, same pattern as _click_shape."""
        if self.last_image is None:
            return
        rect = panel_frame_rect(self.last_image.size,
                                (self.canvas.winfo_width(), self.canvas.winfo_height()))
        self.color_panel.pick_now((event.x, event.y), rect)
        self._draw_color_panel()

    def _draw_color_panel(self):
        if self.last_image is None:
            self.canvas.delete("color_panel")
            return
        rect = panel_frame_rect(self.last_image.size,
                                (self.canvas.winfo_width(), self.canvas.winfo_height()))
        color_point = None
        if self.tip is not None:
            left, top, fw, fh = rect
            color_point = (left + self.tip[0] * fw, top + self.tip[1] * fh)
        hover = self.color_panel.hover_target(color_point, rect)
        self.color_panel.draw(self.canvas, rect, hover)

    def _select_shape(self, shape):
        """Create the corresponding object in the shared backend scene."""
        # Start at the center, then fill neighboring positions in camera space.
        row, column = divmod(self.shape_count % 9, 3)
        offsets = (0.0, -1.1, 1.1)
        position = (offsets[column], offsets[row], 4.0)
        event = GestureEvent(GestureType.CREATE_SHAPE, 1.0, shape_type=ShapeType[shape.upper()])
        self.shape_commands.handle(event, spawn_position=position)
        if self.scene.objects:
            set_shape_color(self.scene.objects[-1], self.color_panel.selected_rgb)
        self.shape_count += 1
        self.shape_message = f"{shape} selected · action {self.shape_count}"
        self.shape_message_until = time.monotonic() + 2.0

    def _draw_shape_toolbar(self):
        self.canvas.delete("shape_toolbar")
        buttons, tip = self._shape_layout()
        if not buttons:
            return
        c = self.canvas
        tag = "shape_toolbar"
        x1, y1, _, _ = buttons[0][1]
        x2 = buttons[-1][1][2]
        if self.shape_message:
            c.create_text((x1 + x2) / 2, y1 - 19, text=self.shape_message,
                          fill=TEXT, font=("Helvetica", 11), tags=tag)
        for name, (a, b, d, e) in buttons:
            active = self.dwell.target == name
            color = ACCENT if active else TEXT
            c.create_oval(a, b, d, e, fill=PANEL, outline="", tags=tag)
            cx, cy = (a + d) / 2, (b + e) / 2
            r = min(11, (e - b) * .23)
            if name == "Cube":
                c.create_polygon(cx, cy-r, cx+r, cy-r/2, cx+r, cy+r/2,
                                 cx, cy+r, cx-r, cy+r/2, cx-r, cy-r/2,
                                 fill="", outline=color, width=2, tags=tag)
                c.create_line(cx-r, cy-r/2, cx, cy, cx+r, cy-r/2,
                              fill=color, width=2, tags=tag)
                c.create_line(cx, cy, cx, cy+r, fill=color, width=2, tags=tag)
            elif name == "Sphere":
                c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=color, width=2, tags=tag)
                c.create_oval(cx-r/2, cy-r, cx+r/2, cy+r, outline=color, tags=tag)
                c.create_oval(cx-r, cy-r/3, cx+r, cy+r/3, outline=color, tags=tag)
            else:
                c.create_polygon(cx, cy-r, cx+r, cy+r/2, cx, cy+r,
                                 cx-r, cy+r/2, fill="", outline=color, width=2, tags=tag)
                c.create_line(cx, cy-r, cx, cy+r, fill=color, width=2, tags=tag)
            if active and self.dwell.progress > 0:
                c.create_arc(a + 1, b + 1, d - 1, e - 1, start=90,
                             extent=-359.9 * self.dwell.progress, style="arc",
                             outline=ACCENT, width=2, tags=tag)
        # Keep the aiming point visible above the buttons covering the video.
        if tip is not None and self.cursor.get():
            x, y = tip
            c.create_oval(x-7, y-7, x+7, y+7, outline=ACCENT, width=2, tags=tag)
            c.create_oval(x-2, y-2, x+2, y+2, fill=ACCENT, outline="", tags=tag)

    def _display_frame(self, frame: Frame):
        if not self.live:
            self.live = True
            self.status.configure(text="●  Live", text_color=ACCENT)
        self.last_image = Image.fromarray(frame.rgb)
        now = time.monotonic()
        self.effects.update(frame)
        effect_pose = "6 7" if frame.six_seven is not None else "Cat" if frame.cat is not None else None
        quit_target = (frame.hand if not effect_pose and frame.cursor is not None
                       and frame.gesture == "Middle finger" else None)
        if self.quit_dwell.update(quit_target, now) is not None:
            self.close()
            return
        self.tip = frame.cursor
        self.tip_seen = now if frame.cursor is not None else None
        buttons, tip = self._shape_layout()
        toolbar_target = self._shape_at(buttons, tip)
        if effect_pose:
            self.interaction.reset_motion()
        else:
            destroyed = self.interaction.update(frame, self.scene.objects, self.last_image.size,
                                                now, over_toolbar=toolbar_target is not None)
            for obj in destroyed or ():
                self.effects.explode(shape_center(obj, self.last_image.size), now)
        if (effect_pose or self.interaction.pinching or self.interaction.waiting_for_pinky_down
                or self.interaction.anchor is not None or quit_target is not None):
            toolbar_target = None
        selected_shape = self.dwell.update(toolbar_target, now)
        if selected_shape is not None:
            self._select_shape(selected_shape)
        self._render_image()
        self.hand_value.configure(text="Left + right" if frame.hand_count == 2 else frame.hand)
        self.pose_value.configure(text=effect_pose or frame.gesture)
        self.fps_value.configure(text=f"{frame.fps:.0f}")
        position = "—"
        if frame.cursor is not None:
            position = f"{frame.cursor[0]:.2f} / {frame.cursor[1]:.2f}"
        self.position_value.configure(text=position)
        aim = frame.index_tip or frame.cursor
        color_rect = panel_frame_rect(self.last_image.size,
                                      (self.canvas.winfo_width(), self.canvas.winfo_height()))
        color_point = None
        if aim is not None:
            left, top, fw, fh = color_rect
            color_point = (left + aim[0] * fw, top + aim[1] * fh)
        self.color_panel.update(color_point, now, color_rect)
        self._draw_color_panel()

    def _poll(self):
        if self.closing:
            return
        self._poll_camera_scan()
        if self.shape_message and time.monotonic() >= self.shape_message_until:
            self.shape_message = ""
            self._draw_shape_toolbar()
        if self.tip_seen is not None and time.monotonic() - self.tip_seen > self.dwell.max_gap:
            self.dwell.reset()
            self.tip = self.tip_seen = None
            self._draw_shape_toolbar()
        worker = self.worker
        displayed = False
        if worker:
            # Check before draining events so a just-finished worker cannot
            # disappear between the event drain and the cleanup below.
            ended = not worker.is_alive()
            while True:
                try:
                    kind, message = worker.events.get_nowait()
                except Empty:
                    break
                if kind == "error" and not worker.stop_event.is_set():
                    self.error = True
                    self.status.configure(text="●  Unavailable", text_color="#FFC266")
                    self._empty_canvas(message)
                elif kind == "loading" and not worker.stop_event.is_set():
                    self.canvas.itemconfigure(self.message_item, text=message)
            if not self.error and not worker.stop_event.is_set():
                try:
                    self._display_frame(worker.frames.get_nowait())
                    displayed = True
                    if self.closing:
                        return
                except Empty:
                    pass
            if ended:
                self.worker = None
                self.live = False
                self.camera_dropdown.configure(state="normal" if self.camera_choices else "disabled")
                self.refresh_button.configure(state="normal")
                self.camera_button.configure(text="Start camera", state="normal")
                if self.restart_camera:
                    self.start_camera()
                elif not self.error:
                    self.status.configure(text="●  Stopped", text_color=MUTED)
                    self._empty_canvas("Camera is off.\nPress Start camera to return to your workspace.")
        if self.effects.explosions and not displayed:
            self._render_image()
        self.after(20, self._poll)
        if self.last_image is None:
            self.canvas.delete("color_panel")

    def close(self):
        if self.closing:
            return
        self.closing = True
        if self.worker:
            self.worker.stop()
        self.camera_button.configure(text="Closing…", state="disabled")
        self._close_deadline = time.monotonic() + 3
        self._wait_for_shutdown()

    def _wait_for_shutdown(self):
        # Some drivers hang on unplug. Never block Tk waiting for a camera.
        if self.worker and self.worker.is_alive() and time.monotonic() < self._close_deadline:
            self.after(50, self._wait_for_shutdown)
        else:
            self.destroy()


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    CameraCanvasApp().mainloop()
