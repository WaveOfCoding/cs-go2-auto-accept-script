from utils.grabbers.mss import Grabber
from utils.fps import FPS
import cv2
import numpy as np
import random, os, sys
from utils.nms import non_max_suppression_fast
from utils.cv2 import filter_rectangles, rect_center_dot

from utils.controls.mouse.win32 import MouseControls
from utils.win32 import WinHelper
import keyboard
from playsound import playsound

import multiprocessing

# Import custom (more precise) sleep implementation
from utils.time import sleep

# CONFIG
GAME_WINDOW_TITLE = "Counter-Strike 2"  # aimlab_tb, FallGuys_client, Counter-Strike: Global Offensive - Direct3D 9, etc
ACTIVATION_HOTKEY = "F10"
_show_cv2 = False

# used by the script
game_window_rect = WinHelper.GetWindowRect(GAME_WINDOW_TITLE, (8, 30, 16, 39))  # cut the borders

SOUNDS = {
    "activate": ["waitinghere01", "waitinghere02", "waitinghere03", "waitinghere04"],
    "accept": ["affirmative01", "affirmative02", "affirmative03"],
    "deactivate": ["script_attack_4"],
    "startup": ["the-verkkars", "awol"],
    "cancel": ["suit_denydevice"]
}


def grab_process(q, _activated, _button_was_pressed):
    grabber = Grabber()

    while True:
        # print(_activated)
        if _activated.is_set():
            img = grabber.get_image(
                {"left": int(game_window_rect[0]), "top": int(game_window_rect[1]), "width": int(game_window_rect[2]),
                 "height": int(game_window_rect[3])})

            if img is None:
                continue

            q.put_nowait(img)
            q.join()


def cv2_process(q, _activated, _button_was_pressed):
    global _show_cv2, game_window_rect

    fps = FPS()
    font = cv2.FONT_HERSHEY_SIMPLEX
    mouse = MouseControls()

    # mouse = MouseControls()

    while True:
        if not q.empty() and _activated.is_set():
            img = q.get_nowait()
            q.task_done()

            # DO PROCESSING CODE HERE
            hue_point = 50
            button_color = ((hue_point, 150, 150), (hue_point + 20, 200, 200))  # HSV
            min_target_size = (100, 50)
            max_target_size = (500, 200)

            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, np.array(button_color[0], dtype=np.uint8),
                               np.array(button_color[1], dtype=np.uint8))
            contours, hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            rectangles = []

            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if (w >= min_target_size[0] and h >= min_target_size[1]) \
                        and (w <= max_target_size[0] and h <= max_target_size[1]):
                    rectangles.append((int(x), int(y), int(w), int(h)))

            if not rectangles:
                continue

            # cv stuff
            if _show_cv2:
                for rect in rectangles:
                    x, y, w, h = rect
                    cv2.rectangle(img, (x, y), (x + w, y + h), [255, 0, 0], 6)
                    img = cv2.putText(img, f"{(x + w, y + h)}", (x, y - 10), font,
                                      .5, (0, 255, 0), 1, cv2.LINE_AA)

            # Apply NMS
            rectangles = np.array(non_max_suppression_fast(np.array(rectangles), overlapThresh=0.3))

            # Filter rectangles (join intersections)
            rectangles = filter_rectangles(rectangles.tolist())

            # Select only one rectangle and get it's click dot
            dot = rect_center_dot(rectangles[0])

            # move mouse
            mouse.move(*dot)

            # accept (+little delay)
            play_random_sound("accept")

            # click
            mouse.hold_mouse()
            sleep(0.001)
            mouse.release_mouse()
            sleep(0.001)

            # sleep some
            _button_was_pressed.set()
            sleep(10)

            # deactivate, cuz game found
            # switch_active_state(0, 0)

            if _show_cv2:
                img = cv2.putText(img, f"{fps():.2f}", (20, 120), font,
                                  1.7, (0, 255, 0), 7, cv2.LINE_AA)

                img = cv2.resize(img, (1280, 720))
                cv2.imshow("Captured & Processed image", img)
                cv2.waitKey(1)


def play_random_sound(action):
    cdir = os.path.dirname(os.path.abspath(sys.argv[0]))
    soundfilepath = "{}\sounds\{}.wav".format(cdir, random.choice(SOUNDS[action]))
    playsound(soundfilepath)


def switch_active_state():
    if _activated.is_set():
        # DEACTIVATE
        _activated.clear()

        print("AUTO-ACCEPT DEACTIVATED")
        if _button_was_pressed.is_set():
            play_random_sound("deactivate")
            _button_was_pressed.clear()
        else:
            play_random_sound("cancel")
    else:
        # ACTIVATE
        _activated.set()

        print("AUTO-ACCEPT ACTIVATED")
        play_random_sound("activate")


if __name__ == "__main__":
    print("Starting AUTO-ACCEPT bot by Priler ...")
    print(f"Press {ACTIVATION_HOTKEY} to activate/deactivate the bot.")
    # play_random_sound("startup")

    q = multiprocessing.JoinableQueue()
    _activated = multiprocessing.Event()
    _button_was_pressed = multiprocessing.Event()

    p1 = multiprocessing.Process(target=grab_process, args=(q, _activated, _button_was_pressed))
    p2 = multiprocessing.Process(target=cv2_process, args=(q, _activated, _button_was_pressed))

    p1.start()
    p2.start()

    while True:
        keyboard.wait(ACTIVATION_HOTKEY)
        switch_active_state()
